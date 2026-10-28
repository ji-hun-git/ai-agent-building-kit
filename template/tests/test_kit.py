import json
import os
import tempfile
import unittest

from kit import (Agent, Call, Doc, Index, NeedsApproval, Pending, Policy, Reply, Scripted, Session, Tool,
                 Toolbox, Tracer, User, anyone, bundle, own_records, role)
from kit.agent import _to_anthropic, _to_openai
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


if __name__ == "__main__":
    unittest.main()
