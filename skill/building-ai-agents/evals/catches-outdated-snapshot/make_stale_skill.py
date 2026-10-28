"""Build a copy of the building-ai-agents skill whose snapshot is backdated.

Used by the catches-outdated-snapshot case: the with-skill run points at this
copy, so a pass means the skill noticed its own snapshot was stale instead of
trusting it. The older versions below are synthetic test fixtures, chosen only
to be older than any real release on the run date.

Usage: python make_stale_skill.py <skill_dir> <out_dir>
"""

import json
import shutil
import sys
from pathlib import Path

STALE_DATE = "2026-03-02"
OLD_MCP_REVISION = "2025-11-25"
OLD_VERSIONS = {
    "spec:mcp-spec": OLD_MCP_REVISION,
    "github:modelcontextprotocol/modelcontextprotocol": OLD_MCP_REVISION,
    "github:a2aproject/A2A": "v0.3.0",
    "github:open-telemetry/semantic-conventions": "v1.38.0",
    "github:sierra-research/tau2-bench": "v0.2.0",
    "pypi:anthropic": "0.79.0",
    "pypi:claude-agent-sdk": "0.1.31",
    "pypi:openai": "2.15.0",
    "pypi:openai-agents": "0.7.0",
    "pypi:google-genai": "1.60.0",
    "pypi:google-adk": "1.22.0",
    "pypi:agent-framework": "1.0.0b260130",
    "pypi:langgraph": "1.0.7",
    "pypi:deepagents": "0.3.9",
    "pypi:mcp": "1.25.0",
    "pypi:a2a-sdk": "0.3.22",
    "pypi:inspect-ai": "0.3.160",
    "pypi:docling": "2.70.0",
    "pypi:langfuse": "3.12.0",
    "pypi:opentelemetry-sdk": "1.39.1",
    "npm:@anthropic-ai/sdk": "0.72.0",
    "npm:@anthropic-ai/claude-agent-sdk": "0.2.30",
    "npm:openai": "6.16.0",
    "npm:@openai/agents": "0.4.2",
    "npm:@google/genai": "1.38.0",
    "npm:@modelcontextprotocol/sdk": "1.25.3",
    "npm:@a2a-js/sdk": "0.3.8",
    "npm:@langchain/langgraph": "1.1.2",
    "npm:promptfoo": "0.120.10",
}


def main(skill_dir: str, out_dir: str) -> None:
    src, dst = Path(skill_dir), Path(out_dir)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("evals"))

    snap_path = dst / "references" / "snapshot.json"
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    snap["checked"] = STALE_DATE
    for item in snap["items"]:
        old = OLD_VERSIONS.get(f"{item['source']}:{item['key']}")
        if old:
            item["version"], item["released"] = old, ""
    snap_path.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")

    # Text files claim the old verification date and the previous MCP revision as current.
    for md in [dst / "SKILL.md", *sorted((dst / "references").glob("*.md"))]:
        text = md.read_text(encoding="utf-8")
        text = text.replace("2026-10-27", STALE_DATE).replace("2026-07-28", OLD_MCP_REVISION)
        md.write_text(text, encoding="utf-8")
    print(f"stale skill written to {dst} (snapshot {STALE_DATE}, MCP {OLD_MCP_REVISION})")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
