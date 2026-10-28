import json
import os
import tempfile
import unittest
from unittest import mock

from kit import (Agent, Anthropic, Call, Doc, Embeddings, Index, NeedsApproval, OpenAIResponses, Pending, Policy,
                 Reply, Reranker, Scripted, Session, Tool, Toolbox, Tracer, User, anyone, bundle, own_records, role)
from kit import evals, only_values, OpenAICompatible
from kit.agent import _to_anthropic, _to_openai, _to_responses
from kit.context import fingerprint

ALICE = User("alice", frozenset({"employee"}))
HR = User("hana", frozenset({"employee", "hr"}))


def toolbox(**extra) -> Toolbox:
    policy = Policy().allow("read", anyone).allow("write", anyone).allow("send", anyone).allow("boom", anyone)
    tb = Toolbox(policy, max_chars=50)
    tb.add(
        Tool("read", "reads", {"x": {"type": "string"}}, fn=lambda user, x="": f"read {x}"),
        Tool("write", "writes", {"x": {"type": "string"}}, fn=lambda user, x: f"wrote {x}", kind="write", required=("x",)),
        Tool("send", "sends out", {}, fn=lambda user: "sent", kind="write", approval=False, outbound=True),
        Tool("boom", "fails", {}, fn=lambda user: 1 / 0),
    )
    return tb


def session(tb: Toolbox, user: User = ALICE) -> Session:
    return Session(system="sys", tools=tb.schemas(user))


class TestPolicy(unittest.TestCase):
    def test_unknown_tool_is_denied_by_default(self):
        ok, why = Policy().check(ALICE, "anything", {})
        self.assertFalse(ok)
        self.assertIn("denied by default", why)

    def test_own_records(self):
        rule = own_records(unless="hr")
        self.assertTrue(rule(ALICE, {}))
        self.assertTrue(rule(ALICE, {"employee_id": "alice"}))
        self.assertFalse(rule(ALICE, {"employee_id": "ceo"}))
        self.assertTrue(rule(HR, {"employee_id": "ceo"}))

    def test_role(self):
        self.assertFalse(role("hr")(ALICE, {}))
        self.assertTrue(role("hr")(HR, {}))


class TestToolbox(unittest.TestCase):
    def test_read_runs_and_write_asks(self):
        tb = toolbox()
        s = session(tb)
        self.assertEqual(tb.execute(Call("1", "read", {"x": "a"}), ALICE, s).content, "read a")
        with self.assertRaises(NeedsApproval):
            tb.execute(Call("2", "write", {"x": "a"}), ALICE, s)
        self.assertEqual(tb.execute(Call("2", "write", {"x": "a"}), ALICE, s, approved=True).content, "wrote a")

    def test_writes_run_once(self):
        tb = toolbox()
        s = session(tb)
        tb.execute(Call("1", "write", {"x": "a"}), ALICE, s, approved=True)
        again = tb.execute(Call("2", "write", {"x": "a"}), ALICE, s, approved=True)
        self.assertIn("not repeated", again.content)
        self.assertEqual(len(s.ledger), 1)

    def test_denied_unknown_missing_and_failing_calls_become_sentences(self):
        tb = toolbox()
        s = session(tb)
        tb.policy.rules.pop("read")
        self.assertIn("Denied", tb.execute(Call("1", "read", {}), ALICE, s).content)
        self.assertIn("Unknown tool", tb.execute(Call("2", "nope", {}), ALICE, s).content)
        self.assertIn("Missing required", tb.execute(Call("3", "write", {}), ALICE, s, approved=True).content)
        failed = tb.execute(Call("4", "boom", {}), ALICE, s)
        self.assertTrue(failed.is_error)
        self.assertIn("boom failed", failed.content)

    def test_long_results_are_truncated(self):
        tb = toolbox()
        out = tb.execute(Call("1", "read", {"x": "y" * 200}), ALICE, session(tb)).content
        self.assertIn("[truncated at 50 characters", out)

    def test_trifecta_blocks_outbound_only_when_private_and_untrusted(self):
        tb = toolbox()
        s = session(tb)
        s.taint.private = True
        self.assertEqual(tb.execute(Call("1", "send", {}), ALICE, s).content, "sent")
        s.ledger.clear()
        s.taint.untrusted = True
        with self.assertRaises(NeedsApproval) as e:
            tb.execute(Call("2", "send", {}), ALICE, s)
        self.assertIn("private data and untrusted content", e.exception.reason)

    def test_irreversible_always_asks(self):
        with self.assertRaises(AssertionError):
            Tool("pay", "pays", {}, fn=lambda user: "", kind="irreversible", approval=False)

    def test_schemas_are_sorted_and_filtered(self):
        tb = toolbox()
        tb.policy.allow("write", role("hr"))
        names = [t["name"] for t in tb.schemas(ALICE)]
        self.assertEqual(names, sorted(names))
        self.assertNotIn("write", names)


class TestRetrieval(unittest.TestCase):
    docs = [
        Doc("leave", "Leave policy", "# Leave policy\n\n## Annual leave\n\nEmployees get 15 days of annual leave."),
        Doc("bands", "Pay bands", "# Pay bands\n\n## Executives\n\nThe CEO is in band P9.", frozenset({"hr"})),
    ]

    def test_chunks_carry_title_and_heading(self):
        c = Index(self.docs).chunks[0]
        self.assertEqual((c.title, c.heading), ("Leave policy", "Annual leave"))
        self.assertTrue(c.body.startswith("Leave policy > Annual leave"))

    def test_acl_filters_before_ranking(self):
        index = Index(self.docs)
        self.assertEqual(index.search("CEO band executives", ALICE), [])
        self.assertEqual(index.search("CEO band executives", HR)[0][0].doc_id, "bands")

    def test_abstains_on_weak_match(self):
        self.assertEqual(Index(self.docs).search("pets policy office rules", ALICE), [])

    def test_dense_fusion(self):
        embed = lambda text: [text.lower().count("leave"), text.lower().count("ceo")]
        hits = Index(self.docs, embed=embed).search("annual leave days", HR)
        self.assertEqual(hits[0][0].doc_id, "leave")

    def test_chunks_without_a_query_term_are_not_returned(self):
        hits = Index(self.docs).search("annual leave days", HR)
        self.assertEqual([c.doc_id for c, _ in hits], ["leave"])

    def test_situate_adds_context_and_changes_the_version(self):
        plain = Index(self.docs)
        situated = Index(self.docs, situate=lambda doc, c: f"From the {doc.title.lower()}, covering time off.")
        self.assertIn("covering time off", situated.chunks[0].body)
        self.assertNotEqual(plain.version, situated.version)
        self.assertEqual(situated.search("time off", ALICE)[0][0].doc_id, "leave")

    def test_rerank_reorders_and_min_score_abstains(self):
        rerank = lambda query, texts: [0.9 if "P9" in t else 0.1 for t in texts]
        index = Index(self.docs, rerank=rerank, min_score=0.5)
        self.assertEqual(index.search("leave and bands", HR)[0][0].doc_id, "bands")
        self.assertEqual(index.search("leave and bands", ALICE), [])  # only the low-scored chunk is visible

    def test_adapters_read_the_common_response_shapes(self):
        shapes = [{"results": [{"index": 1, "relevance_score": 0.8}, {"index": 0, "relevance_score": 0.2}]},  # Cohere, Jina, vLLM
                  {"data": [{"index": 1, "relevance_score": 0.8}, {"index": 0, "relevance_score": 0.2}]},     # Voyage
                  [{"index": 1, "score": 0.8}, {"index": 0, "score": 0.2}]]                                  # TEI
        for shape in shapes:
            with mock.patch("kit.retrieval.post", return_value=shape):
                self.assertEqual(Reranker("m", "http://x/rerank")("q", ["a", "b"]), [0.2, 0.8])
        with mock.patch("kit.retrieval.post", return_value={"data": [{"index": 0, "embedding": [0.1, 0.2]}]}) as post:
            self.assertEqual(Embeddings("m", "http://x/v1")("hello"), [0.1, 0.2])
            self.assertEqual(post.call_args[0][0], "http://x/v1/embeddings")


class TestContext(unittest.TestCase):
    def test_history_is_append_only(self):
        s = Session(system="s", tools=[])
        s.append({"role": "user", "content": "hi"})
        with self.assertRaises(AttributeError):
            s.messages.append({})  # a tuple: no editing through the view

    def test_prefix_is_stable_and_sensitive(self):
        tools = [{"name": "a", "input_schema": {"properties": {"y": 1, "x": 2}}}]
        same = [{"input_schema": {"properties": {"x": 2, "y": 1}}, "name": "a"}]
        self.assertEqual(fingerprint("s", tools), fingerprint("s", same))
        self.assertNotEqual(fingerprint("s", tools), fingerprint("s ", tools))

    def test_clearing_leaves_a_reload_pointer(self):
        s = Session(system="s", tools=[])
        for i in range(3):
            s.append({"role": "tool", "id": str(i), "name": "read", "args": {"x": i}, "content": "big", "is_error": False})
        self.assertEqual(s.clear_old_tool_results(keep_last=1), 2)
        self.assertIn('call read with {"x":0} to reload', s.messages[0]["content"])
        self.assertEqual(s.messages[2]["content"], "big")


class TestTraceAndRelease(unittest.TestCase):
    def test_content_is_dropped_unless_captured(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.jsonl")
            t = Tracer(path, release="r1")
            with t.span("chat", **{"content.output": "secret", "gen_ai.request.model": "m"}):
                pass
            with open(path, encoding="utf-8") as f:
                line = json.loads(f.read())
        self.assertNotIn("content.output", line)
        self.assertEqual((line["release.version"], line["gen_ai.operation.name"]), ("r1", "chat"))
        captured = Tracer(capture=True)
        with captured.span("chat", **{"content.output": "visible"}):
            pass
        self.assertEqual(captured.spans[0]["content.output"], "visible")

    def test_any_behaviour_change_is_a_new_version(self):
        base = bundle("prompt", "model-a", [{"name": "t"}], "idx1")["version"]
        self.assertEqual(base, bundle("prompt", "model-a", [{"name": "t"}], "idx1")["version"])
        for changed in (bundle("prompt!", "model-a", [{"name": "t"}], "idx1"),
                        bundle("prompt", "model-b", [{"name": "t"}], "idx1"),
                        bundle("prompt", "model-a", [{"name": "u"}], "idx1"),
                        bundle("prompt", "model-a", [{"name": "t"}], "idx2"),
                        bundle("prompt", "model-a", [{"name": "t"}], "idx1", effort="high")):
            self.assertNotEqual(base, changed["version"])


class TestAgent(unittest.TestCase):
    def test_loop_pauses_for_approval_and_resumes(self):
        tb = toolbox()
        model = Scripted([Reply(calls=[Call("c1", "read", {"x": "a"}), Call("c2", "write", {"x": "b"})]),
                          Reply("done")])
        agent = Agent(model, "sys", tb)
        s = agent.start(ALICE)
        out = agent.run(s, ALICE, "go")
        self.assertIsInstance(out, Pending)
        self.assertEqual(out.call.name, "write")
        self.assertEqual(agent.resume(s, ALICE, approved=True), "done")
        self.assertEqual([m["content"] for m in s.messages if m["role"] == "tool"], ["read a", "wrote b"])
        self.assertEqual(s.prefix, agent.start(ALICE).prefix)

    def test_step_limit(self):
        model = Scripted([Reply(calls=[Call(str(i), "read", {})]) for i in range(10)])
        out = Agent(model, "sys", toolbox(), max_steps=3).run(Session("sys", []), ALICE, "loop")
        self.assertIn("too many steps", out)

    def test_adapters_keep_tool_results_paired(self):
        msgs = [{"role": "user", "content": "q"},
                {"role": "assistant", "content": "", "calls": [{"id": "a", "name": "t", "args": {}},
                                                               {"id": "b", "name": "t", "args": {"k": 1}}]},
                {"role": "tool", "id": "a", "name": "t", "args": {}, "content": "1", "is_error": False},
                {"role": "tool", "id": "b", "name": "t", "args": {"k": 1}, "content": "2", "is_error": False}]
        anth = _to_anthropic(msgs)
        self.assertEqual(len(anth), 3)
        self.assertEqual([b["tool_use_id"] for b in anth[2]["content"]], ["a", "b"])
        oai = _to_openai(msgs)
        self.assertEqual(oai[1]["tool_calls"][1]["function"]["arguments"], '{"k":1}')
        self.assertEqual([m["tool_call_id"] for m in oai[2:]], ["a", "b"])
        resp = _to_responses(msgs)
        self.assertEqual([i["type"] for i in resp[1:]], ["function_call"] * 2 + ["function_call_output"] * 2)

    def run_twice(self, model, first, second):
        """One tool call, then an answer; returns the request bodies the adapter sent."""
        tb = Toolbox(Policy().allow("look", anyone)).add(Tool("look", "looks", {}, fn=lambda user: "seen"))
        agent = Agent(model, "sys", tb)
        with mock.patch("kit.agent.post", side_effect=[first, second]) as post:
            out = agent.run(agent.start(ALICE), ALICE, "go")
        return out, [c.args[2] for c in post.call_args_list], post.call_args_list[0].args[1]

    def test_anthropic_sends_thinking_blocks_back_unchanged(self):
        turn = [{"type": "thinking", "thinking": "", "signature": "sig"},
                {"type": "tool_use", "id": "t1", "name": "look", "input": {}}]
        out, bodies, headers = self.run_twice(
            Anthropic("m", api_key="k"),
            {"content": turn, "stop_reason": "tool_use", "usage": {}},
            {"content": [{"type": "text", "text": "done"}], "stop_reason": "end_turn", "usage": {}})
        self.assertEqual(out, "done")
        self.assertEqual(bodies[1]["messages"][1], {"role": "assistant", "content": turn})
        self.assertEqual(bodies[1]["messages"][2]["content"][0]["tool_use_id"], "t1")
        self.assertEqual(headers["anthropic-version"], "2026-10-21")
        self.assertNotIn("temperature", bodies[0])

    def test_responses_sends_reasoning_and_calls_back_in_order(self):
        items = [{"type": "reasoning", "id": "rs_1", "encrypted_content": "e"},
                 {"type": "function_call", "id": "fc_1", "call_id": "c1", "name": "look", "arguments": "{}"}]
        answer = {"output": [{"type": "message", "role": "assistant",
                              "content": [{"type": "output_text", "text": "done"}]}], "usage": {}}
        out, bodies, _ = self.run_twice(OpenAIResponses("m", api_key="k"), {"output": items, "usage": {}}, answer)
        self.assertEqual(out, "done")
        self.assertEqual(bodies[0]["tools"][0]["name"], "look")
        self.assertFalse(bodies[0]["store"])
        self.assertEqual(bodies[1]["input"][1:], items + [{"type": "function_call_output", "call_id": "c1",
                                                           "output": "seen"}])


class TestEdges(unittest.TestCase):
    """Edge cases that once left the harness in a bad state."""

    def approvals_agent(self, replies, **kwargs):
        policy = Policy().allow("pay", anyone)
        tb = Toolbox(policy).add(Tool("pay", "pays", {"n": {"type": "integer"}}, kind="irreversible",
                                      fn=lambda user, n=0: f"paid {n}"))
        return Agent(Scripted(replies), "sys", tb, **kwargs)

    def test_moving_on_declines_what_was_waiting(self):
        agent = self.approvals_agent([Reply(calls=[Call("1", "pay", {"n": 1})]), Reply("ok"), Reply("ok")])
        session = agent.start(ALICE)
        self.assertIsInstance(agent.run(session, ALICE, "pay"), Pending)
        agent.run(session, ALICE, "never mind")
        self.assertIsNone(session.pending)
        self.assertEqual(session.ledger, {})
        declined = [m for m in session.messages if m["role"] == "tool"]
        self.assertEqual(len(declined), 1)
        self.assertTrue(declined[0]["is_error"])

    def test_step_limit_counts_across_approvals(self):
        replies = [Reply(calls=[Call(str(i), "pay", {"n": i})]) for i in range(50)]
        agent = self.approvals_agent(replies, max_steps=3)
        session = agent.start(ALICE)
        out = agent.run(session, ALICE, "pay forever")
        for _ in range(10):
            if not isinstance(out, Pending):
                break
            out = agent.resume(session, ALICE, approved=True)
        self.assertIn("too many steps", out)
        self.assertEqual(len(session.ledger), 3)
        calls = [c["id"] for m in session.messages if m["role"] == "assistant" for c in m["calls"]]
        results = [m["id"] for m in session.messages if m["role"] == "tool"]
        self.assertEqual(calls, results)  # every call has its result, so the history stays valid

    def test_tools_gated_by_arguments_can_still_be_listed(self):
        policy = (Policy().allow("post", only_values("channel", {"@me"}))
                  .allow("send", only_values("channel", {"@me"}), visible=anyone))
        tb = Toolbox(policy).add(Tool("post", "posts", {}, fn=lambda user: ""), Tool("send", "sends", {}, fn=lambda user: ""))
        self.assertEqual([t["name"] for t in tb.schemas(ALICE)], ["send"])

    def test_clearing_keeps_errors(self):
        s = Session(system="s", tools=[])
        s.append({"role": "tool", "id": "1", "name": "request_leave", "args": {}, "content": "The user declined.",
                  "is_error": True})
        s.append({"role": "tool", "id": "2", "name": "read", "args": {}, "content": "long", "is_error": False})
        self.assertEqual(s.clear_old_tool_results(keep_last=0), 1)
        self.assertEqual(s.messages[0]["content"], "The user declined.")

    def test_adapters_survive_bad_json_and_no_tools(self):
        bad = {"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "c", "function": {"name": "look", "arguments": "{not json"}}]}}]}
        with mock.patch("kit.agent.post", return_value=bad) as post:
            reply = OpenAICompatible("m", "http://x/v1")("sys", [{"role": "user", "content": "q"}], [])
        self.assertEqual(reply.calls[0].args, {})
        self.assertNotIn("tools", post.call_args.args[2])
        self.assertEqual(_to_anthropic([{"role": "user", "content": "q"},
                                        {"role": "assistant", "content": "", "calls": []}]),
                         [{"role": "user", "content": "q"}])

    def test_retrieval_handles_particles_paraphrases_and_permissions(self):
        ko = Index([Doc("l", "연차 규정", "# 연차 규정\n\n## 연차\n\n연차는 매년 15일입니다.")])
        self.assertEqual(ko.search("연차가 며칠이에요?", ALICE)[0][0].doc_id, "l")
        docs = [Doc("l", "Leave", "# Leave\n\n## Annual\n\nEmployees get 15 days of annual leave."),
                Doc("i", "IT", "# IT\n\n## Passwords\n\nReset passwords at the desk.")]
        embed = lambda t: [1.0, 0.0] if ("leave" in t.lower() or "vacation" in t.lower()) else [0.0, 1.0]
        hits = Index(docs, embed=embed, min_similarity=0.5).search("how much vacation", ALICE)
        self.assertEqual([c.doc_id for c, _ in hits], ["l"])
        self.assertNotEqual(Index([Doc("d", "t", "x")]).version, Index([Doc("d", "t", "x", frozenset({"hr"}))]).version)

    def test_gate_rejects_unknown_suites_and_empty_runs(self):
        with self.assertRaises(ValueError):
            evals.run(lambda: None, [{"id": "x", "suite": "Safety", "user": {"id": "u"}, "turns": [], "expect": {}}])
        self.assertEqual(evals.run(lambda: None, []), (False, []))


class TestErrors(unittest.TestCase):
    def test_provider_errors_read_as_sentences(self):
        import io
        import urllib.error
        from kit.net import APIError, key, post
        body = io.BytesIO(b'{"error": {"message": "model not found"}}')
        err = urllib.error.HTTPError("http://x", 404, "Not Found", {}, body)
        with mock.patch("urllib.request.urlopen", side_effect=err), self.assertRaises(APIError) as caught:
            post("http://x", {}, {})
        self.assertIn("404", str(caught.exception))
        self.assertIn("model not found", str(caught.exception))
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(APIError) as caught:
            key("ANTHROPIC_API_KEY")
        self.assertIn("ANTHROPIC_API_KEY", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
