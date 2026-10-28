"""Context: a stable prefix and an append-only history.

Provider prompt caches reuse the longest unchanged prefix of a request, and some
models now reject a history that was edited after the fact. So:

- the system prompt and the tool list are fixed when a session starts,
- everything is serialized deterministically (sorted keys, no timestamps),
- history is only ever appended to.

The one sanctioned rewrite is clearing old tool results when the context gets
long. It leaves a pointer behind, so the agent can fetch the data again.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field

from .policy import Taint


def dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def fingerprint(system: str, tools: list[dict]) -> str:
    """Hash of the cacheable prefix. If it changes mid-session, the cache is gone."""
    return hashlib.sha256(dumps([system, tools]).encode()).hexdigest()[:16]


@dataclass
class Session:
    system: str
    tools: list[dict]
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    taint: Taint = field(default_factory=Taint)
    ledger: dict = field(default_factory=dict)  # idempotency key -> result of a write
    pending: dict | None = None                  # a tool call waiting for a person
    steps: int = 0                               # model calls since the user last spoke
    _messages: list = field(default_factory=list)

    def __post_init__(self):
        self.prefix = fingerprint(self.system, self.tools)

    @property
    def messages(self) -> tuple:
        return tuple(self._messages)  # read-only view; use append()

    def append(self, message: dict) -> None:
        self._messages.append(message)

    def clear_old_tool_results(self, keep_last: int = 6) -> int:
        """Replace all but the last `keep_last` tool results with a reload pointer.

        This edits history. Models that bind their reasoning to the exact history (Claude's
        preserved thinking, for accounts created from 2026-08-31) drop or reject the reasoning
        after an edited turn; with them, use the provider's own context editing or compaction."""
        tool_idx = [i for i, m in enumerate(self._messages) if m["role"] == "tool"]
        cleared = 0
        for i in tool_idx[:-keep_last] if keep_last else tool_idx:
            m = self._messages[i]
            if m.get("cleared") or m.get("is_error"):  # errors are short, and reloading a refusal misleads
                continue
            pointer = f"[cleared to save context; call {m['name']} with {dumps(m['args'])} to reload]"
            self._messages[i] = {**m, "content": pointer, "cleared": True}
            cleared += 1
        return cleared


def load_prompt(path) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read().strip()
