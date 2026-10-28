"""Draws every figure in docs/figures from code, in one visual system.

    python scripts/make_figures.py              # all figures
    python scripts/make_figures.py hero         # one or more by name

Each figure is an SVG built from a handful of primitives (box, panel, arrow, text), so
diagrams and charts share one type scale, one grey scale and one accent. The SVG is written
next to a 2x PNG rendered by headless Chrome or Edge with the Inter typeface (set CHROME to
the browser's path if it is not found). No Python dependencies.
"""

import html
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "figures"
FONT = "Inter, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

INK, BODY, MUTED = "#1b1b19", "#5d5d58", "#8a8a83"
LINE, ARROW, PANEL, STRIP, GRID = "#c9c9c2", "#b2b2aa", "#e2e2dc", "#efefeb", "#e6e6e1"
BLUE, BLUE_BG, ORANGE, RED = "#2f6fde", "#e9f0fc", "#eb6834", "#cf3a2f"


class Canvas:
    def __init__(self, w: int, h: int):
        self.w, self.h, self.parts = w, h, []

    def text(self, x, y, s, size=15, weight=400, color=INK, anchor="middle"):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
                          f'fill="{color}" text-anchor="{anchor}">{html.escape(s)}</text>')

    def rect(self, x, y, w, h, stroke=LINE, fill="#fff", width=1.4, r=8):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
                          f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

    def circle(self, x, y, r, fill, ring="#fff"):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{ring}" stroke-width="2"/>')

    def line(self, x1, y1, x2, y2, color=GRID, width=1):
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"/>')

    def box(self, x, y, w, h, title, sub=(), n=None, accent=False):
        self.rect(x, y, w, h, BLUE if accent else LINE, BLUE_BG if accent else "#fff", 2 if accent else 1.4)
        sub = [sub] if isinstance(sub, str) else list(sub or ())
        top = y + h / 2 - 11 * len(sub) + 6
        self.text(x + w / 2, top, title, 16, 600)
        for i, line in enumerate(sub):
            self.text(x + w / 2, top + 22 + 20 * i, line, 14, color=BODY)
        if n is not None:
            self.text(x + w - 14, y + 24, str(n), 14, color=BODY, anchor="end")

    def arrow(self, points, dashed=False, head=True, color=ARROW):
        d = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(points))
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        end = f' marker-end="url(#head-{color[1:]})"' if head else ""
        self.parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6"{dash}{end}/>')

    def panel(self, x, y, w, h, label, n=None):
        self.rect(x, y, w, h, PANEL, "#fff", 1.4, 12)
        self.text(x + 24, y + 34, label, 17, 600, anchor="start")
        if n is not None:
            self.text(x + w - 24, y + 34, str(n), 15, color=BODY, anchor="end")

    def column(self, x, y, w, items, gap=24):
        """Boxes stacked top to bottom with arrows between; returns each box's (top, bottom)."""
        spans = []
        for title, sub, n in items:
            h = 58 if sub else 46
            self.box(x, y, w, h, title, sub, n)
            if spans:
                self.arrow([(x + w / 2, spans[-1][1]), (x + w / 2, y - 1)])
            spans.append((y, y + h))
            y += h + gap
        return spans

    def header(self, title, subtitle):
        self.text(40, 54, title, 28, 700, anchor="start")
        self.text(40, 86, subtitle, 16, color=BODY, anchor="start")

    def svg(self) -> str:
        markers = "".join(
            f'<marker id="head-{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto"><path d="M0,1 L9,5 L0,9 z" fill="{c}"/></marker>' for c in (ARROW, RED))
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" font-family="{FONT}"><defs>{markers}</defs>'
                f'<rect width="{self.w}" height="{self.h}" fill="#fff"/>' + "".join(self.parts) + "</svg>\n")


# ---------------------------------------------------------------- diagrams

def hero() -> Canvas:
    """README: the ten layers at request time and change time."""
    c = Canvas(1400, 1400)
    c.header("Every request crosses the controls. Every change crosses the gate.",
             "The ten layers of a production AI agent in 2026. Small numbers are the layers in the guide and the template.")
    c.panel(40, 110, 1320, 1014, "Request time")
    cx, cw = 470, 460
    for y, h, title, sub, n in [
        (170, 70, "User (principal)", "OAuth-delegated · the agent acts as this user", 6),
        (276, 70, "Input guard", "Hidden text stripped · secrets and IDs redacted · moderation", 7),
        (382, 70, "Prompt cache", "Frozen prefix · cache keyed by user and release", 8),
    ]:
        c.box(cx, y, cw, h, title, sub, n)
        c.arrow([(700, y + h), (700, y + h + 35)])
    c.rect(cx, 488, cw, 328)
    c.text(cx + 30, 522, "Agent harness", 17, 600, anchor="start")
    c.text(cx + cw - 30, 522, "the model proposes, code disposes", 14, color=BODY, anchor="end")
    for y, title, sub, n in [
        (542, "Context", "Versioned prompt · sorted tools · append-only history", 2),
        (632, "Model + loop", "Pinned snapshot · routed by difficulty · step cap", 1),
        (722, "Memory", "Compaction · old tool results cleared, restorable", 5),
    ]:
        c.box(cx + 30, y, cw - 60, 68, title, sub, n)
    c.arrow([(700, 816), (700, 851)])
    c.box(cx, 852, cw, 70, "Output guard", "Cites or abstains · no remote images · IDs redacted", 7)
    c.arrow([(700, 922), (700, 957)])
    c.box(cx, 958, cw, 56, "User-visible answer")

    c.panel(68, 440, 340, 428, "Knowledge (retrieval)", 3)
    left = c.column(98, 490, 280, [
        ("Documents + ACLs", None, None),
        ("Contextual chunks", "structure-aware, title > heading", None),
        ("Hybrid index", "BM25 + dense, fused by RRF", None),
        ("Filter, rerank, cite", "ACL first; abstain below the bar", None),
    ])
    c.text(238, 816, "returns cited passages, marked untrusted", 14, color=BODY)
    mid = sum(left[-1]) / 2
    c.arrow([(378, mid), (cx - 1, mid)])

    c.panel(992, 440, 340, 428, "Tools (MCP)", 4)
    right = c.column(1022, 490, 280, [
        ("Policy check", "the user's own permissions", 6),
        ("Lethal-trifecta rule", "private + untrusted + outbound → ask", 7),
        ("Approval + lockdown", "a person decides; writes run once", None),
        ("MCP servers", None, None),
        ("HR · Jira · Slack", None, None),
    ])
    mid = sum(right[0]) / 2
    c.arrow([(cx + cw, mid), (1021, mid)])

    c.rect(68, 1046, 1264, 50, LINE, STRIP)
    c.text(700, 1077, "Traces on every step above: OpenTelemetry GenAI spans with the release version; "
                      "content capture off by default", 16)
    c.text(1310, 1077, "9", 15, color=BODY, anchor="end")

    c.panel(40, 1152, 1320, 220, "Change time", 10)
    steps = [("Change", ["Prompt, model, tools,", "index or settings"]),
             ("Release bundle", ["One hash over all of them,", "stamped on every trace"]),
             ("Eval gate", ["pass^k on every case;", "regression and safety at 100%"]),
             ("Ships", ["Next version goes live;", "the last one stays for rollback"])]
    xs = [68 + i * 326 for i in range(4)]
    for i, (title, sub) in enumerate(steps):
        c.box(xs[i], 1206, 286, 86, title, sub, accent=title == "Eval gate")
        if i:
            c.arrow([(xs[i - 1] + 286, 1249), (xs[i] - 1, 1249)])
    c.arrow([(xs[0] + 143, 1292), (xs[0] + 143, 1322), (xs[3] + 143, 1322), (xs[3] + 143, 1294)], dashed=True)
    c.parts.append(f'<circle cx="700" cy="1322" r="11" fill="#fff" stroke="{RED}" stroke-width="1.8"/>'
                   f'<path d="M694,1316 L706,1328 M706,1316 L694,1328" stroke="{RED}" stroke-width="1.8"/>')
    c.text(700, 1356, "No skip path: a prompt edit is a release", 14, 500, RED)
    return c


def ontology_planes() -> Canvas:
    """guide/ontology.md: the architecture the video arrives at, one failure at a time."""
    c = Canvas(1400, 1330)
    c.header("Every query crosses the controls; every change must cross the gate",
             "The architecture in the video, built one failure at a time. Small numbers are the steps in which each part appeared.")
    c.panel(40, 110, 1320, 942, "Request time")
    cx, cw = 470, 460
    for y, h, title, sub, n in [
        (170, 70, "Employee (principal)", "Identity passed via OAuth", 4),
        (276, 86, "Input guards", ["Input classifier", "Jailbreak detection"], 5),
        (398, 70, "Semantic cache", "Repeat query → stored answer", 6),
    ]:
        c.box(cx, y, cw, h, title, sub, n)
        c.arrow([(700, y + h), (700, y + h + 35)])
    c.rect(cx, 504, cw, 240)
    c.text(cx + 30, 538, "Company AI agent", 17, 600, anchor="start")
    c.box(cx + 30, 558, cw - 60, 68, "System prompt", "Name · persona · tone", 1)
    c.box(cx + 30, 646, cw - 60, 68, "Model router", "Simple → small, hard → frontier", 6)
    c.arrow([(700, 744), (700, 779)])
    c.box(cx, 780, cw, 70, "Output guard", "PII redaction: SALARY [REDACTED]", 5)
    c.arrow([(700, 850), (700, 885)])
    c.box(cx, 886, cw, 56, "User-visible output")

    c.panel(68, 490, 340, 300, "Knowledge (RAG)", 2)
    left = c.column(98, 540, 280, [("Policy documents", None, None), ("Chunk + embed", None, None),
                                   ("Vector database", None, None)])
    c.text(238, 764, "returns retrieved context", 14, color=BODY)
    mid = sum(left[-1]) / 2
    c.arrow([(378, mid), (cx - 1, mid)])

    c.panel(992, 490, 340, 300, "Capability (MCP)", 3)
    right = c.column(1022, 540, 280, [("RBAC check", "Caller's OAuth role", 4), ("MCP servers", None, None),
                                      ("HR · Jira · Slack", None, None)])
    mid = sum(right[0]) / 2
    c.arrow([(cx + cw, mid), (1021, mid)])

    c.rect(68, 974, 1264, 50, LINE, STRIP)
    c.text(700, 1005, "Observability: tool-call traces and prompt logs on every step above", 16)
    c.text(1310, 1005, "7", 15, color=BODY, anchor="end")

    c.panel(40, 1080, 1320, 222, "Change time (steps 7–8)")
    steps = [("Change", ["System prompt, model,", "index, tools"]),
             ("Evaluation suite", ["Cases from every", "past failure"]),
             ("Release gate", ["Ships only on pass;", "no skip path"]),
             ("Agent above", ["Next version", "goes live"])]
    xs = [68 + i * 326 for i in range(4)]
    for i, (title, sub) in enumerate(steps):
        c.box(xs[i], 1134, 286, 86, title, sub, accent=title == "Release gate")
        if i:
            c.arrow([(xs[i - 1] + 286, 1177), (xs[i] - 1, 1177)])
    c.arrow([(xs[0] + 143, 1220), (xs[0] + 143, 1250), (xs[3] + 143, 1250), (xs[3] + 143, 1222)],
            dashed=True, color=RED)
    c.text(700, 1282, "What happened: evals skipped → “I'm ChatGPT” (identity regression)", 14, 500, RED)
    return c


def skill_workflow() -> Canvas:
    """README: the skill's steps."""
    c = Canvas(1400, 560)
    c.header("Check what is current, then build in the order failures close",
             "The building-ai-agents skill as a coding agent runs it. Step 0 runs every time; the rest scale to the request.")
    steps = [
        ("Freshness check", ["Versions, advisories and model", "lineups, checked live and", "recorded in a stack lock"]),
        ("Frame the job", ["Five real tasks, the data,", "the actions and the risk tier;", "build or buy"]),
        ("Simplest architecture", ["Call → workflow → one agent", "→ sub-agents, climbing only", "when the evals fail"]),
        ("Evals first", ["Cases from the failure", "catalogue, written before", "the code; pass^k"]),
        ("Build the ten layers", ["In order; each one closes", "a failure the layers below", "leave open"]),
        ("Threat model", ["Untrusted inputs, the trifecta", "check, the OWASP map,", "red-team cases"]),
        ("Release through the gate", ["Versioned bundle, required", "evals, then shadow,", "canary and ramp"]),
        ("Hand off", ["Spec, eval plan, threat model,", "stack lock and a log", "of decisions"]),
    ]
    w, h, gap = 305, 150, 30
    for i, (title, sub) in enumerate(steps):
        x, y = 40 + (i % 4) * (w + gap), 130 + (i // 4) * 220
        c.box(x, y, w, h, title, sub, i, accent=i == 0)
        if i % 4:
            c.arrow([(x - gap, y + h / 2), (x - 1, y + h / 2)])
    c.arrow([(40 + 3 * (w + gap) + w / 2, 280), (40 + 3 * (w + gap) + w / 2, 315), (40 + w / 2, 315), (40 + w / 2, 349)])
    return c


def guard_checkpoints() -> Canvas:
    """template README and guide Step 7: where the guard screens text."""
    c = Canvas(1400, 680)
    c.header("Four checkpoints: text is screened wherever it crosses a trust boundary",
             "Rules run first and cannot be argued with; a guard model or a moderation API adds what rules cannot see.")
    A, B, C, D, E = (40, 170), (260, 300), (610, 220), (880, 300), (1230, 130)
    r1, r2, r3 = 130, 320, 500
    c.box(*at(A, r1, 100), "User", "a request")
    c.box(*at(B, r1, 100), "Prompt guard", ["strip hidden characters; redact", "secrets and IDs; moderation"], 7, True)
    c.box(*at(C, r1, 100), "Model", "proposes")
    c.box(*at(D, r1, 100), "Output guard", ["strip and redact; images and", "links only to listed hosts"], 7, True)
    c.box(*at(E, r1, 100), "Answer")
    c.box(*at(A, r2, 100), "Documents", "at ingestion")
    c.box(*at(B, r2, 100), "Data guard", ["hidden characters and markup;", "secrets and IDs; injection flag"], 7, True)
    c.box(*at(C, r2, 100), "Toolbox", ["policy · trifecta", "lockdown · approval · once"], 4)
    c.box(*at(D, r2, 100), "Egress guard", ["refuses hidden text, secrets,", "IDs and unlisted URLs"], 7, True)
    c.box(*at(B, r3, 80), "Read tools", "search · HR system · files")
    c.box(*at(D, r3, 80), "Outbound tools", "post · email · fetch")
    for (x1, w1), (x2, _) in [(A, B), (B, C), (C, D), (D, E)]:
        c.arrow([(x1 + w1, r1 + 50), (x2 - 1, r1 + 50)])
    c.arrow([(A[0] + A[1], r2 + 50), (B[0] - 1, r2 + 50)])
    c.arrow([(C[0] + C[1], r2 + 50), (D[0] - 1, r2 + 50)])
    c.text(C[0] + C[1] + 25, r2 + 40, "out", 13, color=MUTED)
    c.arrow([(760, r1 + 100), (760, r2 - 1)])
    c.text(770, r1 + 145, "tool calls", 13, color=MUTED, anchor="start")
    c.arrow([(520, r2), (520, 280), (690, 280), (690, r1 + 101)])
    c.text(605, 272, "cleaned results", 13, color=MUTED)
    c.arrow([(700, r2 + 100), (700, 460), (500, 460), (500, r3 - 1)])
    c.arrow([(340, r3), (340, r2 + 101)])
    c.arrow([(D[0] + D[1] / 2, r2 + 100), (D[0] + D[1] / 2, r3 - 1)])
    c.text(40, 630, "What the rules guarantee holds whatever the model does. A classifier is one more layer, never the boundary.",
           15, color=BODY, anchor="start")
    return c


def at(col, y, h):
    """(x, y, w, h) for a box in a column given as (x, width)."""
    return col[0], y, col[1], h


# ---------------------------------------------------------------- charts

def skill_evals() -> Canvas:
    """skill/README: graded expectations passed with and without the skill."""
    rows = [
        ("Round 1",),
        ("Pick a model and SDK for 200 tools", 4, 3, 5),
        ("Design an HR assistant", 6, 3, 6),
        ("Modernize a 2024 support agent", 8, 8, 8),
        ("All of round 1", 18, 14, 19),
        ("Round 2: the same tasks, plus a skill copy backdated seven months",),
        ("Pick a model and SDK for 200 tools", 4, 2, 5),
        ("Notice its own outdated snapshot", 5, 5, 5),
        ("Design an HR assistant", 5, 5, 6),
        ("Modernize a 2024 support agent", 10, 10, 10),
        ("All of round 2", 24, 22, 26),
    ]
    x0, x1, top = 560, 1160, 190
    ys, y = [], top
    for row in rows:
        y += 46 if len(row) == 1 else 40
        ys.append(y)
    bottom = ys[-1] + 26
    c = Canvas(1400, bottom + 90)
    c.header("With the skill, the same model passed more of the graded checks",
             "Share of graded expectations passed per task. Same model and web access in both runs.")
    c.circle(48, 134, 7, BLUE)
    c.text(62, 139, "With the skill", 14, color=BODY, anchor="start")
    c.circle(196, 134, 7, ORANGE)
    c.text(210, 139, "Without", 14, color=BODY, anchor="start")
    c.text(1255, 174, "with", 13, color=MUTED, anchor="end")
    c.text(1345, 174, "without", 13, color=MUTED, anchor="end")
    for pct in (0, 25, 50, 75, 100):
        x = x0 + (x1 - x0) * pct / 100
        c.line(x, top, x, bottom)
        c.text(x, bottom + 22, f"{pct}%", 13, color=MUTED)
    for row, y in zip(rows, ys, strict=True):
        if len(row) == 1:
            c.text(40, y + 5, row[0], 15, 600, anchor="start")
            continue
        label, w, wo, n = row
        total = label.startswith("All")
        c.text(56, y + 5, label, 15, 600 if total else 400, INK if total else BODY, anchor="start")
        xw, xo = x0 + (x1 - x0) * w / n, x0 + (x1 - x0) * wo / n
        c.line(xo, y, xw, y, LINE, 2)
        c.circle(xo, y, 7, ORANGE)
        c.circle(xw, y, 7, BLUE)
        c.text(1255, y + 5, f"{w}/{n}", 14, 600 if total else 400, INK, anchor="end")
        c.text(1345, y + 5, f"{wo}/{n}", 14, 600 if total else 400, INK, anchor="end")
    c.text(40, bottom + 66, "Where the dots meet, both runs passed the same share. Round 2 changes to the skill were not re-run.",
           14, color=MUTED, anchor="start")
    return c


def retrieval_failures() -> Canvas:
    """sota/ladders.md and the guide: what contextual chunks and reranking buy."""
    rows = [("Embeddings", 5.7), ("Contextual embeddings", 3.7), ("+ contextual BM25", 2.9), ("+ reranking", 1.9)]
    x0, scale, top, step = 330, 150, 150, 56
    c = Canvas(1400, top + step * len(rows) + 110)
    c.header("Contextual chunks and reranking cut retrieval failures by two thirds",
             "Top-20 retrieval failure rate in Anthropic's contextual-retrieval experiments. Lower is better.")
    bottom = top + step * len(rows)
    for pct in range(0, 7):
        x = x0 + pct * scale
        c.line(x, top - 10, x, bottom)
        c.text(x, bottom + 22, f"{pct}%", 13, color=MUTED)
    for i, (label, value) in enumerate(rows):
        y = top + i * step + 16
        c.text(40, y + 17, label, 15, color=INK if i == len(rows) - 1 else BODY, anchor="start")
        w = value * scale
        c.parts.append(f'<path d="M{x0},{y} H{x0 + w - 4} a4,4 0 0 1 4,4 V{y + 20} a4,4 0 0 1 -4,4 H{x0} Z" fill="{BLUE}"/>')
        c.text(x0 + w + 10, y + 17, f"{value}%", 15, 600, anchor="start")
    c.text(40, bottom + 62, "In the template: contextual chunks are Index(situate=...); reranking is "
                            "Index(rerank=..., min_score=...). Source: anthropic.com/news/contextual-retrieval",
           14, color=MUTED, anchor="start")
    return c


def benchmark() -> Canvas:
    """benchmarks/: the release-gate cases at pass^k for each model, from benchmarks/results/*.json."""
    import json
    results = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((OUT.parent.parent / "benchmarks" / "results").glob("*.json"))]

    def passed(r, example=None):
        rows = [c for c in r["cases"] if example in (None, c["example"])]
        return sum(c["passed"] == c["trials"] for c in rows), len(rows)

    def rank(r):
        p, n = passed(r)
        return (not r["guard"], r["model"] == "stand-in", -p / n)

    results.sort(key=rank)
    guarded = [r for r in results if r["guard"]]
    off = [r for r in results if not r["guard"]]
    trials = sum(c["trials"] for r in guarded for c in r["cases"])
    unsafe = sum(c["unsafe"] for r in guarded for c in r["cases"])
    k = max(r["k"] for r in results)
    # Narrow on purpose: GitHub shows a README image about 880 px wide, so this renders near full size.
    w_, right, x0, x1, top, step = 1120, 1080, 300, 640, 176, 66
    rows_h = step * len(results) + (50 if off else 0)
    c = Canvas(w_, top + rows_h + 120)
    title = f"Guard on: {unsafe} unsafe outcomes in {trials:,} trials."
    if off:
        title += f" Guard off: {sum(c['unsafe'] for r in off for c in r['cases'])} in {sum(c['trials'] for r in off for c in r['cases'])}."
    c.header(title, f"Release-gate cases passed on all {k} trials (pass^{k}), out of {passed(results[0])[1]}. "
                    "Same harness, prompts and policies for every model.")
    for x, label in ((800, "HR"), (885, "Support"), (975, "Research"), (right, "Unsafe")):
        c.text(x, top - 26, label, 14, color=MUTED, anchor="end")
    for pct in (0, 50, 100):
        x = x0 + (x1 - x0) * pct / 100
        c.line(x, top - 12, x, top + rows_h)
        c.text(x, top + rows_h + 24, f"{pct}%", 14, color=MUTED)
    y = top
    for i, r in enumerate(results):
        if not r["guard"] and (i == 0 or results[i - 1]["guard"]):
            c.line(40, y + 12, right, y + 12, LINE)
            c.text(40, y + 40, "The same stand-in with the guard and lockdown removed", 15, 600, BODY, anchor="start")
            y += 50
        mid = y + step / 2
        c.text(40, mid - 2, r["name"].replace(", guard and lockdown off", ""), 18, 600, INK, anchor="start")
        c.text(40, mid + 20, r["api"] if r["api"] != "offline" else "offline, no model", 14, color=MUTED, anchor="start")
        p, n = passed(r)
        color = BLUE if r["guard"] else ORANGE
        c.rect(x0, mid - 8, x1 - x0, 16, STRIP, STRIP, 0, 8)
        c.rect(x0, mid - 8, max((x1 - x0) * p / n, 16), 16, color, color, 0, 8)
        c.text(x1 + 16, mid + 6, f"{p}/{n}", 17, 600, anchor="start")
        for x, example in ((800, "hr"), (885, "support"), (975, "research")):
            ep, en = passed(r, example)
            c.text(x, mid + 6, f"{ep}/{en}", 16, color=BODY, anchor="end")
        bad = sum(case["unsafe"] for case in r["cases"])
        c.text(right, mid + 6, str(bad), 18, 700, RED if bad else INK, anchor="end")
        y += step
    for i, line in enumerate(("Unsafe: a trial of a safety case in which the harm happened: a leaked value, a value the model",
                              "must not see, or a forbidden or repeated write. A miss that only fails the task is not unsafe.")):
        c.text(40, top + rows_h + 66 + 22 * i, line, 15, color=MUTED, anchor="start")
    return c


def social_preview() -> Canvas:
    """The repository's social card (GitHub: Settings, then Social preview)."""
    c = Canvas(1280, 640)
    c.text(80, 190, "AI Agent Building Kit", 64, 700, anchor="start")
    c.text(80, 250, "Why agents fail, and how to build them in 2026", 30, color=BODY, anchor="start")
    layers = ["Model", "Context", "Retrieval", "Tools", "Memory", "Identity", "Security", "Cost", "Traces", "Evals"]
    for i, name in enumerate(layers):
        x, y = 80 + (i % 5) * 228, 320 + (i // 5) * 88
        c.box(x, y, 208, 68, name, n=i + 1, accent=name in ("Security", "Evals"))
    c.text(80, 560, "Guide, lessons, agent template, benchmark, Agent Skill and state of the art", 22,
           color=MUTED, anchor="start")
    return c


FIGURES = {"hero": hero, "ontology-planes": ontology_planes, "skill-workflow": skill_workflow,
           "guard-checkpoints": guard_checkpoints, "skill-evals": skill_evals, "retrieval-failures": retrieval_failures,
           "benchmark": benchmark, "social-preview": social_preview}


# ---------------------------------------------------------------- rendering

def browser():
    found = [os.environ.get("CHROME"), shutil.which("chrome"), shutil.which("google-chrome"),
             shutil.which("chromium"), shutil.which("msedge"),
             r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    return next((p for p in found if p and Path(p).exists()), None)


def render(canvas: Canvas, png: Path, exe: str) -> None:
    page = ('<!doctype html><meta charset="utf-8"><link rel="stylesheet" '
            'href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=block">'
            '<style>html,body{margin:0;background:#fff}</style>' + canvas.svg())
    with tempfile.TemporaryDirectory() as tmp:
        index = Path(tmp) / "figure.html"
        index.write_text(page, encoding="utf-8")
        subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--user-data-dir={Path(tmp) / 'profile'}", "--force-device-scale-factor=2",
                        f"--window-size={canvas.w},{canvas.h}", "--virtual-time-budget=10000",
                        f"--screenshot={png}", index.as_uri()], check=True, capture_output=True)


if __name__ == "__main__":
    names = sys.argv[1:] or list(FIGURES)
    exe = browser()
    for name in names:
        canvas = FIGURES[name]()
        (OUT / f"{name}.svg").write_text(canvas.svg(), encoding="utf-8")
        if exe:
            render(canvas, OUT / f"{name}.png", exe)
        print("wrote", name, "(svg + png)" if exe else "(svg only; no Chrome or Edge found)")
