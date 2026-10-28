"""Tools: what the agent may do, classified by what they change.

    read          runs immediately
    write         asks a person first (unless approval=False), then runs exactly once
    irreversible  always asks a person first, runs exactly once, never retried

Every call goes through Toolbox.execute, in this order: known tool, required
arguments, the user's permissions, the idempotency ledger, the session's
trifecta state, lockdown, approval, and only then the function itself.
Failures come back to the model as plain sentences it can act on, never as
stack traces.

Lockdown is the strict setting for agents that read untrusted content: once a
session has read anything written by someone other than the user, every action
needs a person, whatever its approval setting. Untrusted text can still shape
an answer, but it can no longer choose an action on its own.
"""

import hashlib
from dataclasses import dataclass
from typing import Any, Callable

from .context import Session, dumps
from .policy import Policy, User

KINDS = ("read", "write", "irreversible")


@dataclass
class Tool:
    name: str
    description: str
    params: dict                 # JSON Schema "properties"
    fn: Callable[..., Any]       # called as fn(user=..., **args)
    kind: str = "read"
    required: tuple = ()
    private: bool = False        # returns data not everyone may see
    untrusted: bool = False      # returns text written by others (docs, email, web)
    outbound: bool = False       # can carry data to anyone other than the user
    approval: bool | None = None # override for writes; irreversible always asks

    def __post_init__(self):
        assert self.kind in KINDS, f"kind must be one of {KINDS}"
        assert not (self.kind == "irreversible" and self.approval is False), "irreversible actions always ask"

    @property
    def needs_approval(self) -> bool:
        if self.kind == "read":
            return False
        return True if self.approval is None else self.approval

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.params,
                "required": list(self.required),
                "additionalProperties": False,
            },
        }


@dataclass
class Call:
    id: str
    name: str
    args: dict


@dataclass
class Result:
    content: str
    is_error: bool = False


class NeedsApproval(Exception):
    def __init__(self, call: Call, reason: str):
        super().__init__(reason)
        self.call, self.reason = call, reason


class Toolbox:
    def __init__(self, policy: Policy, max_chars: int = 4000, lockdown: bool = False):
        self.policy, self.max_chars, self.lockdown = policy, max_chars, lockdown
        self.tools: dict[str, Tool] = {}

    def add(self, *tools: Tool) -> "Toolbox":
        for t in tools:
            self.tools[t.name] = t
        return self

    def schemas(self, user: User) -> list[dict]:
        """Only tools this user could ever call. Sorted, so the prefix is stable."""
        visible = [t for t in self.tools.values() if self.policy.visible(user, t.name)]
        return [t.schema() for t in sorted(visible, key=lambda t: t.name)]

    def key(self, session: Session, call: Call) -> str:
        return hashlib.sha256(f"{session.id}|{call.name}|{dumps(call.args)}".encode()).hexdigest()[:16]

    def execute(self, call: Call, user: User, session: Session, approved: bool = False) -> Result:
        tool = self.tools.get(call.name)
        if tool is None:
            return Result(f"Unknown tool '{call.name}'. Available: {', '.join(sorted(self.tools))}.", True)
        missing = [p for p in tool.required if p not in call.args]
        if missing:
            return Result(f"Missing required argument(s) for {tool.name}: {', '.join(missing)}.", True)
        ok, why = self.policy.check(user, tool.name, call.args)
        if not ok:
            return Result(f"Denied: {why}. Tell the user you cannot do this.", True)
        key = self.key(session, call)
        if tool.kind != "read" and key in session.ledger:
            return Result(f"{session.ledger[key]} (already done in this session; not repeated)")
        if not approved and session.taint.blocks(tool.outbound):
            raise NeedsApproval(call, "this session has read private data and untrusted content; "
                                      "sending anything out needs a person to check it")
        if not approved and self.lockdown and tool.kind != "read" and session.taint.untrusted:
            raise NeedsApproval(call, "this session has read untrusted content, and in lockdown "
                                      "every action after that needs a person")
        if not approved and tool.needs_approval:
            raise NeedsApproval(call, f"{tool.name} is a {tool.kind} action")

        # Exposure starts when the tool runs, not when it succeeds: an error message can carry
        # private or untrusted text too.
        session.taint.private |= tool.private
        session.taint.untrusted |= tool.untrusted
        try:
            out = tool.fn(user=user, **call.args)
        except Exception as e:  # the model gets a sentence, the trace gets the type
            return Result(f"{tool.name} failed: {e}. Check the arguments and try once more.", True)

        text = out if isinstance(out, str) else dumps(out)
        if len(text) > self.max_chars:
            text = text[: self.max_chars] + f"\n[truncated at {self.max_chars} characters; narrow the request]"
        if tool.kind != "read":
            session.ledger[key] = text
        return Result(text)
