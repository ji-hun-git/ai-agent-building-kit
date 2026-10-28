"""Release bundle: everything that changes behaviour, hashed into one version.

The system prompt, the model, its settings, the tool schemas and the retrieval
index all change what the agent does. Hash them together; if the version
changes, the eval gate must pass against the new version before it ships.
A prompt edit is a release, not a typo fix.
"""

import hashlib

from .context import dumps


def bundle(system: str, model: str, tools: list[dict], index_version: str = "", **settings) -> dict:
    content = {"system": system, "model": model, "tools": tools, "index": index_version, "settings": settings}
    return {"version": hashlib.sha256(dumps(content).encode()).hexdigest()[:12],
            "model": model, "index": index_version, "settings": settings,
            "tools": [t["name"] for t in tools]}
