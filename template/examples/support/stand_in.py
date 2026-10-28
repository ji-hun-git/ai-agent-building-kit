"""A rule-based stand-in for a model, gullible on purpose: it acts on whatever a ticket asks for.

That keeps the example offline and deterministic, and keeps the evals honest: they show the
harness containing a model that does the wrong thing. Swap in a real model with --model.
"""

import re

from kit import Call, Reply

from ..hr.stand_in import as_read


class StandIn:
    def __init__(self):
        self.n = 0

    def _call(self, name: str, **args) -> Reply:
        self.n += 1
        return Reply(calls=[Call(f"call_{self.n}", name, args)])

    def __call__(self, system, messages, tools) -> Reply:
        messages = [{**m, "content": as_read(m["content"] or "")} for m in messages]
        if messages[-1]["role"] == "tool":
            return self._after(messages)
        return self._route(system, messages[-1]["content"])

    def _route(self, system: str, text: str) -> Reply:
        if "who are you" in text.lower():
            return Reply(f"I'm {re.search(r'You are ([^,.]+)', system).group(1)}. I help you work customer tickets.")
        found = re.search(r"\bT-\d+\b", text, re.I)
        if not found:
            return Reply("Which ticket? Give me its number, like T-1.")
        ticket_id = found.group(0).upper()
        amount = re.search(r"refund \$?(\d+(?:\.\d+)?)", text, re.I)
        if amount:
            return self._call("refund", ticket_id=ticket_id, amount=float(amount.group(1)))
        return self._call("read_ticket", ticket_id=ticket_id)

    def _after(self, messages) -> Reply:
        r = messages[-1]
        ticket_id = r["args"].get("ticket_id", "")
        if r["is_error"]:
            if "declined" in r["content"]:
                return Reply("OK, I didn't do that.")
            if r["content"].startswith("Denied"):
                return Reply("I can't do that: it is over your refund limit. Please ask a lead.")
            return Reply(f"I couldn't do that: {r['content'].split('. ')[0]}.")
        if r["name"] == "read_ticket":
            if "refund" in r["content"].lower():  # obeys a refund request, wherever it came from
                return self._call("order_status", ticket_id=ticket_id)
            return self._call("reply", ticket_id=ticket_id, text="Thanks for writing in. We're looking into it.")
        if r["name"] == "order_status":
            total = float(re.search(r", (\d+\.\d+),", r["content"]).group(1))
            return self._call("refund", ticket_id=ticket_id, amount=total)
        if r["name"] == "refund":
            done = r["content"].split(" (already done")[0]
            return self._call("reply", ticket_id=ticket_id, text=f"{done} Sorry about the trouble.")
        if r["name"] == "reply":
            refunds = [m["content"] for m in messages if m["role"] == "tool" and m["name"] == "refund" and not m["is_error"]]
            return Reply(" ".join(refunds[-1:] + [r["content"]]))
        return Reply(r["content"])
