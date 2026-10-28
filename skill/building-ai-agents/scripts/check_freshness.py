#!/usr/bin/env python3
"""Live freshness check for the building-ai-agents skill.

Looks up what the skill's snapshot cannot know: the latest releases of the
agent SDKs and protocol packages, the latest MCP / A2A / OTel GenAI spec
releases, and (when API keys are present) the model IDs each vendor serves
right now. Compares everything against references/snapshot.json so the
caller sees what changed since the skill was last verified.

Standard library only. Read-only network calls; API keys, when set, are sent
only to their own vendor's API in headers, never in URLs, and never printed.

Usage:
    python check_freshness.py                 # markdown report vs snapshot
    python check_freshness.py --json          # machine-readable
    python check_freshness.py --no-models     # skip vendor model listing
    python check_freshness.py --write-snapshot references/snapshot.json
    python check_freshness.py --no-models --audit mcp==2.3.0 npm:@openai/agents@0.21.0
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

TIMEOUT = 12
UA = {"User-Agent": "building-ai-agents-freshness/1.0"}

# What to track. Keep keys stable: snapshot.json is keyed by them.
PYPI = {
    "anthropic": "Anthropic Python SDK",
    "claude-agent-sdk": "Claude Agent SDK (Python)",
    "openai": "OpenAI Python SDK",
    "openai-agents": "OpenAI Agents SDK (Python)",
    "google-genai": "Google Gen AI SDK (Python)",
    "google-adk": "Google Agent Development Kit",
    "agent-framework": "Microsoft Agent Framework (Python)",
    "langgraph": "LangGraph",
    "deepagents": "LangChain Deep Agents",
    "mcp": "MCP Python SDK",
    "a2a-sdk": "A2A Python SDK",
    "inspect-ai": "UK AISI Inspect",
    "ragas": "RAGAS",
    "docling": "Docling",
    "langfuse": "Langfuse SDK",
    "opentelemetry-sdk": "OpenTelemetry SDK (Python)",
}
NPM = {
    "@anthropic-ai/sdk": "Anthropic TypeScript SDK",
    "@anthropic-ai/claude-agent-sdk": "Claude Agent SDK (TypeScript)",
    "openai": "OpenAI TypeScript SDK",
    "@openai/agents": "OpenAI Agents SDK (TypeScript)",
    "@google/genai": "Google Gen AI SDK (TypeScript)",
    "@modelcontextprotocol/sdk": "MCP TypeScript SDK",
    "@a2a-js/sdk": "A2A TypeScript SDK",
    "@langchain/langgraph": "LangGraph.js",
    "promptfoo": "promptfoo",
}
GITHUB = {
    "modelcontextprotocol/modelcontextprotocol": "MCP specification",
    "a2aproject/A2A": "A2A protocol",
    "open-telemetry/semantic-conventions-genai": "OTel GenAI semantic conventions",
    "open-telemetry/semantic-conventions": "OTel semantic conventions",
    "sierra-research/tau2-bench": "tau2-bench",
}


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)


def pypi(pkg):
    data = get_json(f"https://pypi.org/pypi/{pkg}/json")
    ver = data["info"]["version"]
    files = data.get("releases", {}).get(ver) or []
    released = files[0]["upload_time"][:10] if files else ""
    return ver, released


def npm(pkg):
    data = get_json(f"https://registry.npmjs.org/{pkg.replace('/', '%2F')}")
    ver = data["dist-tags"]["latest"]
    return ver, (data.get("time", {}).get(ver) or "")[:10]


def github(repo):
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    try:
        rel = get_json(f"https://api.github.com/repos/{repo}/releases/latest", headers)
        return rel.get("tag_name") or rel.get("name"), (rel.get("published_at") or "")[:10]
    except urllib.error.HTTPError as err:
        if err.code in (403, 429):
            raise RuntimeError("GitHub API rate limit; set GITHUB_TOKEN or retry later") from None
        if err.code != 404:
            raise
    tags = get_json(f"https://api.github.com/repos/{repo}/tags?per_page=1", headers)
    return (tags[0]["name"], "") if tags else ("no release", "")


def mcp_latest_spec():
    """The spec site redirects /specification/latest to the current dated revision."""
    req = urllib.request.Request("https://modelcontextprotocol.io/specification/latest", headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        final = resp.geturl()
    parts = [p for p in final.split("/") if len(p) == 10 and p[4] == "-" and p[7] == "-"]
    return (parts[0] if parts else final), ""


def models():
    """Model IDs each vendor serves now. Skips vendors whose key is not set."""
    out = {}
    if os.environ.get("ANTHROPIC_API_KEY"):
        data = get_json(
            "https://api.anthropic.com/v1/models?limit=100",
            {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
        )
        out["anthropic"] = [m["id"] for m in data.get("data", [])]
    if os.environ.get("OPENAI_API_KEY"):
        data = get_json(
            "https://api.openai.com/v1/models",
            {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        )
        out["openai"] = sorted(m["id"] for m in data.get("data", []))
    gkey = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gkey:
        data = get_json(
            "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
            {"x-goog-api-key": gkey},
        )
        out["google"] = [m["name"].removeprefix("models/") for m in data.get("models", [])]
    return out


def audit(specs):
    """Known advisories for pinned versions, from the OSV database.

    Each spec is `name==version` for PyPI or `npm:name@version` for npm.
    """
    rows = []
    for spec in specs:
        if spec.startswith("npm:"):
            name, _, version = spec[4:].rpartition("@")
            ecosystem = "npm"
        else:
            name, _, version = spec.partition("==")
            ecosystem = "PyPI"
        body = json.dumps({"package": {"name": name, "ecosystem": ecosystem},
                           "version": version}).encode()
        req = urllib.request.Request("https://api.osv.dev/v1/query", data=body,
                                     headers={**UA, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                vulns = json.load(resp).get("vulns", [])
            # OSV lists one vulnerability under several ids (GHSA, PYSEC, CVE); keep the first.
            seen, unique = set(), []
            for v in vulns:
                ids = {v["id"], *v.get("aliases", [])}
                if ids & seen:
                    continue
                seen |= ids
                unique.append({"id": v["id"], "aliases": v.get("aliases", []),
                               "summary": v.get("summary", "")})
            rows.append({"spec": spec, "advisories": unique})
        except Exception as err:
            rows.append({"spec": spec, "error": f"{type(err).__name__}: {err}"[:120]})
    return rows


def collect(with_models):
    jobs = [("pypi", k, PYPI[k], pypi) for k in PYPI]
    jobs += [("npm", k, NPM[k], npm) for k in NPM]
    jobs += [("github", k, GITHUB[k], github) for k in GITHUB]
    jobs.append(("spec", "mcp-spec", "MCP spec (latest revision)", lambda _: mcp_latest_spec()))

    def run(job):
        source, key, label, fn = job
        try:
            ver, released = fn(key)
            return {"source": source, "key": key, "label": label, "version": ver, "released": released}
        except Exception as err:  # report, never crash the whole check
            return {"source": source, "key": key, "label": label, "version": None,
                    "released": "", "error": f"{type(err).__name__}: {err}"[:120]}

    with ThreadPoolExecutor(max_workers=12) as pool:
        rows = list(pool.map(run, jobs))
    result = {"checked": date.today().isoformat(), "items": rows}
    if with_models:
        try:
            result["models"] = models()
        except Exception as err:
            result["models_error"] = f"{type(err).__name__}: {err}"[:160]
    return result


def compare(result, snapshot):
    snap = {f"{i['source']}:{i['key']}": i.get("version") for i in snapshot.get("items", [])}
    for row in result["items"]:
        old = snap.get(f"{row['source']}:{row['key']}")
        if row.get("version") is None:
            row["status"] = "unreachable"
        elif old is None:
            row["status"] = "new"
        elif old != row["version"]:
            row["status"] = f"changed (was {old})"
        else:
            row["status"] = "same"
    return result


def to_markdown(result, snapshot_date):
    lines = [
        f"# Freshness check, {result['checked']}",
        "",
        f"Compared with the skill snapshot of {snapshot_date or 'unknown date'}.",
        "",
        "| Component | Source | Latest | Released | vs snapshot |",
        "| --- | --- | --- | --- | --- |",
    ]
    order = {"spec": 0, "github": 1, "pypi": 2, "npm": 3}
    for row in sorted(result["items"], key=lambda r: (order[r["source"]], r["label"])):
        latest = row["version"] or f"unreachable ({row.get('error', '')})"
        lines.append(f"| {row['label']} | {row['source']}:{row['key']} | {latest} | "
                     f"{row['released']} | {row.get('status', '')} |")
    lines.append("")
    if "models" in result:
        if not result["models"]:
            lines.append("Model listing skipped: no ANTHROPIC_API_KEY, OPENAI_API_KEY or "
                         "GEMINI_API_KEY in the environment. Check vendor model pages instead.")
        for vendor, ids in result["models"].items():
            lines.append(f"**{vendor} models ({len(ids)}):** " + ", ".join(ids))
    if result.get("models_error"):
        lines.append(f"Model listing failed: {result['models_error']}")
    for row in result.get("audit", []):
        if "error" in row:
            lines.append(f"**Advisories for {row['spec']}:** lookup failed ({row['error']})")
            continue
        lines.append(f"**Advisories for {row['spec']}:** {len(row['advisories'])} known (OSV)")
        lines += [f"- {a['id']} {' '.join(a['aliases'])}: {a['summary']}" for a in row["advisories"]]
    changed = [r for r in result["items"] if str(r.get("status", "")).startswith("changed")]
    lines += ["", f"{len(changed)} component(s) changed since the snapshot. "
              "Read their changelogs before relying on the skill's defaults for them."]
    return "\n".join(lines)


def main():
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    ap.add_argument("--no-models", action="store_true", help="skip vendor model listing")
    ap.add_argument("--snapshot", default=str(here / "references" / "snapshot.json"))
    ap.add_argument("--write-snapshot", metavar="PATH", help="save this check as the new snapshot")
    ap.add_argument("--audit", nargs="+", metavar="SPEC",
                    help="check pinned versions for advisories: name==ver (PyPI) or npm:name@ver")
    args = ap.parse_args()

    result = collect(with_models=not args.no_models)
    if args.audit:
        result["audit"] = audit(args.audit)
    snap_path = Path(args.snapshot)
    snapshot = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.exists() else {}
    compare(result, snapshot)

    if args.write_snapshot:
        keep = {"checked": result["checked"],
                "items": [{k: r[k] for k in ("source", "key", "label", "version", "released")}
                          for r in result["items"] if r.get("version")]}
        Path(args.write_snapshot).write_text(json.dumps(keep, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(to_markdown(result, snapshot.get("checked")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
