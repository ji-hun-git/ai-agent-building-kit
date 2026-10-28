import itertools
import json
import unittest
from pathlib import Path

from kit import User, evals

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def cases(name: str) -> list:
    return json.loads((EXAMPLES / name / "cases.json").read_text(encoding="utf-8"))


class TestToolLists(unittest.TestCase):
    def test_every_tool_a_case_expects_is_in_that_users_tool_list(self):
        """A real model can only call what it is shown. The stand-ins ignore the tool list, so a rule
        that hides a tool (one over arguments, checked with none) passes every offline gate."""
        import importlib
        for name in ("hr", "support", "research"):
            agent = importlib.import_module(f"examples.{name}").build()
            for case in cases(name):
                user = User(case["user"]["id"], frozenset(case["user"].get("roles", [])))
                shown = {t["name"] for t in agent.toolbox.schemas(user)}
                wanted = set(case["expect"].get("called", [])) | {t for t, n in case["expect"].get("runs", {}).items() if n}
                self.assertLessEqual(wanted, shown, f"{name}/{case['id']}")


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


    def test_refunds_are_positive_and_never_add_up_past_the_order(self):
        from kit import Call, NeedsApproval
        from examples.support import build
        agent, lead = build(), User("u-lead", frozenset({"support", "lead"}))
        session, ids = agent.start(lead), itertools.count()

        def refund(amount):
            return agent.toolbox.execute(Call(str(next(ids)), "refund", {"ticket_id": "T-1", "amount": amount}),
                                         lead, session, approved=True)

        for bad in (-500, 0, float("-inf"), float("nan"), True, "89"):
            out = refund(bad)
            self.assertTrue(out.is_error and out.content.startswith("Denied"), bad)  # the policy refuses
        self.assertTrue(refund(50).ran)
        self.assertTrue(refund(40).is_error)  # 90.00 would pass the 89.00 order
        self.assertTrue(refund(39).ran)       # 89.00 in all
        self.assertTrue(refund(0.01).is_error)
        self.assertIn("already done", refund(39.0).content)  # 39 and 39.0 are the same refund
        with self.assertRaises(NeedsApproval):
            agent.toolbox.execute(Call("x", "refund", {"ticket_id": "T-2", "amount": 5}), lead, session)

    def test_run_once_cases_catch_a_broken_ledger(self):
        """With every call keyed as new, HR files the leave twice and the case fails. A second full
        refund is still refused, by the order's running total: two locks on the money."""
        from unittest import mock

        import examples.hr
        import examples.support
        from kit import Toolbox
        hr = [c for c in json.loads((EXAMPLES / "hr" / "cases.json").read_text(encoding="utf-8"))
              if c["id"] == "write-is-idempotent"]
        support = [c for c in cases("support") if c["id"] == "refund-runs-once"]
        self.assertTrue(evals.run(examples.hr.build, hr)[0])
        with mock.patch.object(Toolbox, "key", lambda self, session, call: call.id):
            self.assertFalse(evals.run(examples.hr.build, hr)[0])
            self.assertTrue(evals.run(examples.support.build, support)[0])


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
