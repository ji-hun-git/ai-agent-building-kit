"""Release bundle: what changes behaviour, hashed into one version.

The system prompt, the model, the tools and the retrieval index (its text and its
permissions) are hashed here; pass everything else that changes what the agent
does as settings: guard and lockdown settings, effort, a policy version, a
tool-code version. If the version changes, the eval gate must pass against the
new version before it ships. A prompt edit is a release, not a typo fix.

Pass the Tool objects themselves, not only their schemas: a tool that turns from
a read into a write, stops asking for approval or starts sending data out has
the same schema, and must still be a new release.
"""

import hashlib

from .context import dumps


def _entry(tool) -> dict:
    if hasattr(tool, "schema"):  # a Tool: its safety flags are behaviour too
        return {**tool.schema(), "safety": {"kind": tool.kind, "approval": tool.approval, "private": tool.private,
                                            "untrusted": tool.untrusted, "outbound": tool.outbound}}
    return tool  # a schema dict, as older callers pass


def bundle(system: str, model: str, tools: list, index_version: str = "", **settings) -> dict:
    entries = [_entry(t) for t in tools]
    content = {"system": system, "model": model, "tools": entries, "index": index_version, "settings": settings}
    return {"version": hashlib.sha256(dumps(content).encode()).hexdigest()[:12],
            "model": model, "index": index_version, "settings": settings,
            "tools": [t["name"] for t in entries]}
