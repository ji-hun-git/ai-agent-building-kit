import json
import unittest
from pathlib import Path

from kit import User, evals

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def cases(name: str) -> list:
    return json.loads((EXAMPLES / name / "cases.json").read_text(encoding="utf-8"))


class TestSupport(unittest.TestCase):
    def test_release_gate_passes(self):
        from examples.support import build
        ok, rows = evals.run(build, cases("support"), k=3)
        self.assertTrue(ok, {r["id"]: r["failures"] for r in rows if not r["passed"]})

    def test_money_rules_hold_without_the_guard(self):
        """Refund limits, approvals and the order total come from policy and tool shape, not the guard."""
        from examples.support import build
        _, rows = evals.run(lambda: build(guarded=False), cases("support"), k=1)
        self.assertEqual([r["id"] for r in rows if not r["passed"]], ["card-number-never-reaches-model"])


class TestResearch(unittest.TestCase):
    def test_release_gate_passes(self):
        from examples.research import build
        ok, rows = evals.run(build, cases("research"), k=3)
        self.assertTrue(ok, {r["id"]: r["failures"] for r in rows if not r["passed"]})

    def test_researchers_cannot_save(self):
        from examples.research import build
        agent, user = build(), User("u-analyst")
        agent.run(agent.start(user), user, "Where does Acme ship?")
        spans = [s for s in agent.tracer.spans if s.get("gen_ai.tool.name") == "save_brief"]
        researcher = [s for s in spans if "tool.is_error" in s]  # the lead's own save is paused for approval
        self.assertTrue(researcher and all(s["tool.is_error"] for s in researcher))  # the tool does not exist for them
        self.assertEqual([s.get("error.type") for s in spans if s not in researcher], ["NeedsApproval"])

    def test_without_lockdown_a_planted_note_saves_the_brief(self):
        from examples.research import build
        agent, user = build(guarded=False), User("u-analyst")
        self.assertIn("'All good'", agent.run(agent.start(user), user, "Where does Acme ship?"))


if __name__ == "__main__":
    unittest.main()
