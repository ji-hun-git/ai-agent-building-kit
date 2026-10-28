"""Acme People Assistant: an HR agent that answers from policy documents and files leave.

It is the agent from the guide's story, built so that each failure in that story
is closed by code rather than by prompt:

    "I'm ChatGPT"                      versioned system prompt + identity eval
    invented leave policy              retrieval with citations, abstains when nothing matches
    intern reads the CEO's pay band    the user's own permissions, checked per call and per document
    instructions hidden in a document  a manipulated model still cannot send private data out
    instructions nobody can see        the guard strips invisible characters at ingestion
    an answer that phones home         the guard removes remote images and links from answers
    a card number pasted into chat     the guard redacts it before the model sees it
    a request to threaten someone      a moderation classifier refuses it before the model runs
    duplicate or unwanted leave        approval before filing, idempotent writes
    "nobody knows why"                 traces with the release version
    a prompt edit skips the evals      bundle version (prompt, model, tools, index, guard) + eval gate
"""

import hashlib
import re
from pathlib import Path

from kit import (Agent, Doc, Guard, Index, Policy, Tool, Toolbox, Tracer, anyone, bundle, load_prompt,
                 search_tool)

from .stand_in import StandIn, StandInModerator

HERE = Path(__file__).parent
BALANCES = {"u-intern": 7, "u-hr": 12}
PAY_BANDS = {"ceo": "P9", "u-intern": "P2", "u-hr": "P5"}


def load_docs(folder: Path) -> list[Doc]:
    """Markdown files; a first line `<!-- acl: role ... -->` restricts a file to those roles.
    An ACL line anywhere else, or one that does not parse, is an error: failing open would
    publish a restricted document."""
    docs = []
    for path in sorted(folder.glob("*.md")):
        text = path.read_text(encoding="utf-8-sig")  # -sig: a byte-order mark must not hide the ACL line
        acl = frozenset({"*"})
        header = re.match(r"<!--\s*acl:\s*([\w\s-]+?)\s*-->[ \t]*\r?\n", text)
        if header:
            acl, text = frozenset(header.group(1).split()), text[header.end():]
        elif re.search(r"<!--\s*acl\b", text, re.I):
            raise ValueError(f"{path.name}: an ACL line must be the first line, as <!-- acl: role -->")
        title = text.lstrip("# ").splitlines()[0]
        docs.append(Doc(path.stem, title, text, acl))
    return docs


def request_leave(user, start: str, end: str, kind: str = "annual") -> str:
    ref = hashlib.sha256(f"{user.id}{start}{end}{kind}".encode()).hexdigest()[:6].upper()
    return f"Leave request LR-{ref} submitted: {kind} leave from {start} to {end}. Your manager will review it."


def tools(index: Index) -> list[Tool]:
    return [
        search_tool(index, "search_policies", "Acme HR policies"),
        Tool("get_leave_balance", "Days of annual leave the user has left.", {},
             fn=lambda user: BALANCES.get(user.id, 15), private=True),
        Tool("get_compensation", "Pay band of the user, or of anyone if the user works in HR.",
             {"employee_id": {"type": "string", "description": "'me', or an employee id such as 'ceo'"}},
             fn=lambda user, employee_id="me": PAY_BANDS.get(user.id if employee_id == "me" else employee_id.lower(), "unknown"),
             private=True),
        Tool("request_leave", "File a leave request for the user. The user is asked to confirm first.",
             {"start": {"type": "string", "format": "date"}, "end": {"type": "string", "format": "date"},
              "kind": {"type": "string", "enum": ["annual", "sick"]}},
             fn=request_leave, kind="write", required=("start", "end")),
        # A message to the user themself is not outbound: the data stays with the person it belongs to.
        Tool("notify_me", "Send the user a direct message, e.g. a confirmation.",
             {"text": {"type": "string"}}, fn=lambda user, text: f"Sent to @{user.id}.",
             kind="write", approval=False, required=("text",)),
        Tool("post_message", "Post to a Slack channel the user may post in.",
             {"channel": {"type": "string"}, "text": {"type": "string"}},
             fn=lambda user, channel, text: f"Posted to {channel}.",
             kind="write", approval=False, outbound=True, required=("channel", "text")),
    ]


def policy() -> Policy:
    return (Policy()
            .allow("search_policies", anyone)
            .allow("get_leave_balance", anyone)
            .allow("get_compensation", lambda u, a: u.has("hr") or a.get("employee_id", "me") in ("me", u.id))
            .allow("request_leave", anyone)
            .allow("notify_me", anyone)
            .allow("post_message", lambda u, a: a.get("channel", "@me") in ({"@me", "#hr-team"} if u.has("hr") else {"@me"})))


def build(model=None, model_id: str = "stand-in", tracer: Tracer | None = None, guarded: bool = True) -> Agent:
    """guarded=False drops the guard and lockdown, to show what they stop (see tests/test_hr.py)."""
    guard = Guard(classify=StandInModerator()) if guarded else None
    docs = load_docs(HERE / "docs")
    index = Index(guard.documents(docs) if guard else docs)
    toolbox = Toolbox(policy(), lockdown=guarded).add(*tools(index))
    system = load_prompt(HERE / "prompt.md")
    release = bundle(system, model_id, [t.schema() for t in toolbox.tools.values()], index.version,
                     guard=guard.settings if guard else None, lockdown=toolbox.lockdown)
    tracer = tracer or Tracer(release=release["version"])
    return Agent(model or StandIn(), system, toolbox, tracer, model_id=model_id, guard=guard)
