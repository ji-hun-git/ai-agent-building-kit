import codecs
import json
import tempfile
import unittest
from pathlib import Path

from examples.hr import build, load_docs
from kit import evals

CASES = Path(__file__).resolve().parents[1] / "examples" / "hr" / "cases.json"


class TestHrGate(unittest.TestCase):
    def test_release_gate_passes(self):
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        ok, rows = evals.run(build, cases, k=3)
        failed = {r["id"]: r["failures"] for r in rows if not r["passed"]}
        self.assertTrue(ok, failed)

    def test_guard_cases_fail_without_the_guard(self):
        """Each guard case must catch something: with the guard and lockdown off, all of them fail."""
        guarded = {"hidden-instruction-stripped", "answer-cannot-phone-home", "card-number-never-reaches-model",
                   "resident-number-never-reaches-model", "moderation-refuses-threat"}
        cases = [c for c in json.loads(CASES.read_text(encoding="utf-8")) if c["id"] in guarded]
        _, rows = evals.run(lambda: build(guarded=False), cases, k=1)
        self.assertEqual({r["id"] for r in rows if r["passed"]}, set())
        self.assertEqual(len(rows), len(guarded))

    def test_a_pay_band_read_from_search_still_cannot_be_posted(self):
        """A model can read P9 straight from the HR-only pay-bands document, without get_compensation.
        Search results from an index that holds restricted documents count as private, so the
        trifecta rule stops the post even with lockdown off."""
        from kit import Call, NeedsApproval, User
        agent, hr = build(guarded=False), User("u-hr", frozenset({"employee", "hr"}))
        session = agent.start(hr)
        found = agent.toolbox.execute(Call("1", "search_policies", {"query": "CEO pay band"}), hr, session)
        self.assertIn("P9", found.content)
        with self.assertRaises(NeedsApproval):
            agent.toolbox.execute(Call("2", "post_message", {"channel": "#hr-team", "text": "CEO pay band: P9"}),
                                  hr, session)

    def test_gate_fails_when_a_safety_case_fails(self):
        broken = [{"id": "x", "suite": "safety", "user": {"id": "u", "roles": []},
                   "turns": ["Who are you?"], "expect": {"contains": ["something it never says"]}}]
        ok, _ = evals.run(build, broken, k=1)
        self.assertFalse(ok)


class TestDocs(unittest.TestCase):
    def test_acl_line_survives_a_byte_order_mark_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "bands.md").write_bytes(codecs.BOM_UTF8 + b"<!-- acl: hr -->\n# Bands\n\nP9.\n")
            self.assertEqual(load_docs(folder)[0].acl, frozenset({"hr"}))
            (folder / "bad.md").write_text("# Bad\n\n<!-- acl: hr -->\nsecret\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_docs(folder)


if __name__ == "__main__":
    unittest.main()
