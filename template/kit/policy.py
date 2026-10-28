"""Authorization and session risk, decided by code outside the model.

The model proposes tool calls. This module decides whether they run.

1. Delegated authority. A call runs only if the *user* may make it. The agent
   has no rights of its own, so a confused or manipulated model can never do
   more than the person it is acting for.
2. The lethal trifecta. A session that has read private data *and* seen
   untrusted content (documents, email, web pages, tool output) may not use an
   outbound channel unless a person approves that specific call. Any two of the
   three are fine; all three is how data gets exfiltrated by prompt injection.
"""

from dataclasses import dataclass
from collections.abc import Callable

Rule = Callable[["User", dict], bool]


@dataclass(frozen=True)
class User:
    id: str
    roles: frozenset = frozenset()

    def has(self, role: str) -> bool:
        return role in self.roles


class Policy:
    """Tool name -> rule. Tools without a rule are denied."""

    def __init__(self):
        self.rules: dict[str, Rule] = {}
        self.visibility: dict[str, Rule] = {}

    def allow(self, tool: str, rule: Rule, visible: Rule | None = None) -> "Policy":
        """`visible` decides whether the tool appears in a user's tool list at all. It defaults to
        the rule itself checked with no arguments, which hides tools whose rule depends on arguments
        (only_values, for one); pass visible=anyone for those."""
        self.rules[tool] = rule
        if visible:
            self.visibility[tool] = visible
        return self

    def visible(self, user: "User", tool: str) -> bool:
        if tool not in self.rules:
            return False
        return self.visibility.get(tool, self.rules[tool])(user, {})

    def check(self, user: User, tool: str, args: dict) -> tuple[bool, str]:
        rule = self.rules.get(tool)
        if rule is None:
            return False, f"no policy covers '{tool}', so it is denied by default"
        if rule(user, args):
            return True, ""
        return False, f"user '{user.id}' is not allowed to call '{tool}' with these arguments"


# Rules. Each is a plain function of (user, args), so they are easy to test and audit.

def anyone(user: User, args: dict) -> bool:
    return True


def role(*names: str) -> Rule:
    return lambda user, args: any(user.has(n) for n in names)


def own_records(field: str = "employee_id", unless: str | None = None) -> Rule:
    """The user may only touch their own records (omitted field means themselves)."""
    def rule(user: User, args: dict) -> bool:
        if unless and user.has(unless):
            return True
        return args.get(field, user.id) == user.id
    return rule


def only_values(field: str, allowed: set) -> Rule:
    return lambda user, args: args.get(field) in allowed


@dataclass
class Taint:
    """What a session has been exposed to so far. Set by tools, read by the toolbox."""
    private: bool = False    # has read data not everyone may see
    untrusted: bool = False  # has read text written by someone other than the user

    def blocks(self, outbound: bool) -> bool:
        return outbound and self.private and self.untrusted
