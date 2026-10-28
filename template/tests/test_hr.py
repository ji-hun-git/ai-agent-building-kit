import json
import unittest
from pathlib import Path

from examples.hr import build
from kit import evals

CASES = Path(__file__).resolve().parents[1] / "examples" / "hr" / "cases.json"


class TestHrGate(unittest.TestCase):
    def test_release_gate_passes(self):
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        ok, rows = evals.run(build, cases, k=3)
        failed = {r["id"]: r["failures"] for r in rows if not r["passed"]}
        self.assertTrue(ok, failed)

    def test_gate_fails_when_a_safety_case_fails(self):
        broken = [{"id": "x", "suite": "safety", "user": {"id": "u", "roles": []},
                   "turns": ["Who are you?"], "expect": {"contains": ["something it never says"]}}]
        ok, _ = evals.run(build, broken, k=1)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
