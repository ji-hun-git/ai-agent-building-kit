"""Draws the README hero: the ten layers of a production agent, at request time and at change time.

    python scripts/make_hero.py

Writes docs/figures/hero.svg, then renders docs/figures/hero.png at 2x with headless Chrome or Edge
(set CHROME to the browser's path if it is not found). The small numbers are the layer numbers
used in the README, the guide and the template.
"""

import html
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "figures"
W, H = 1400, 1400
FONT = "Inter, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

INK, BODY = "#1b1b19", "#5d5d58"
LINE, ARROW, PANEL, STRIP = "#c9c9c2", "#b2b2aa", "#e2e2dc", "#efefeb"
BLUE, BLUE_BG, RED = "#2f6fde", "#e9f0fc", "#cf3a2f"

out = []


def text(x, y, s, size=15, weight=400, color=INK, anchor="middle"):
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
               f'fill="{color}" text-anchor="{anchor}">{html.escape(s)}</text>')


def rect(x, y, w, h, stroke=LINE, fill="#fff", width=1.4, r=8):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')


def box(x, y, w, h, title, sub=(), n=None, stroke=LINE, fill="#fff", width=1.4):
    rect(x, y, w, h, stroke, fill, width)
    sub = [sub] if isinstance(sub, str) else list(sub or ())
    top = y + h / 2 - 11 * len(sub) + 6
    text(x + w / 2, top, title, 16, 600)
    for i, line in enumerate(sub):
        text(x + w / 2, top + 22 + 20 * i, line, 14, color=BODY)
    if n is not None:
        text(x + w - 14, y + 24, str(n), 14, color=BODY, anchor="end")


def path(points, dashed=False, head=True):
    d = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(points))
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    end = ' marker-end="url(#head)"' if head else ""
    out.append(f'<path d="{d}" fill="none" stroke="{ARROW}" stroke-width="1.6"{dash}{end}/>')


def panel(x, y, w, h, label, n=None):
    rect(x, y, w, h, PANEL, "#fff", 1.4, 12)
    text(x + 24, y + 34, label, 17, 600, anchor="start")
    if n is not None:
        text(x + w - 24, y + 34, str(n), 15, color=BODY, anchor="end")


def column(x, y, w, items, gap=24):
    """Stacks boxes top to bottom with arrows between them; returns each box's (top, bottom)."""
    spans = []
    for title, sub, n in items:
        h = 58 if sub else 46
        box(x, y, w, h, title, sub, n)
        if spans:
            path([(x + w / 2, spans[-1][1]), (x + w / 2, y - 1)])
        spans.append((y, y + h))
        y += h + gap
    return spans


def draw():
    text(40, 54, "Every request crosses the controls. Every change crosses the gate.", 28, 700, anchor="start")
    text(40, 86, "The ten layers of a production AI agent in 2026. Small numbers are the layers "
                 "in the guide and the template.", 16, color=BODY, anchor="start")

    # Request time
    panel(40, 110, 1320, 1014, "Request time")
    cx, cw = 470, 460
    center = [
        (170, 70, "User (principal)", "OAuth-delegated · the agent acts as this user", 6),
        (276, 70, "Input guards", "Injection classifier · retrieved text marked untrusted", 7),
        (382, 70, "Prompt cache", "Frozen prefix · cache keyed by user and release", 8),
    ]
    for y, h, title, sub, n in center:
        box(cx, y, cw, h, title, sub, n)
        path([(700, y + h), (700, y + h + 35)])

    rect(cx, 488, cw, 328)
    text(cx + 30, 522, "Agent harness", 17, 600, anchor="start")
    text(cx + cw - 30, 522, "the model proposes, code disposes", 14, color=BODY, anchor="end")
    for y, title, sub, n in [
        (542, "Context", "Versioned prompt · sorted tools · append-only history", 2),
        (632, "Model + loop", "Pinned snapshot · routed by difficulty · step cap", 1),
        (722, "Memory", "Compaction · old tool results cleared, restorable", 5),
    ]:
        box(cx + 30, y, cw - 60, 68, title, sub, n)

    path([(700, 816), (700, 851)])
    box(cx, 852, cw, 70, "Output guard", "Cites a source or abstains · PII redacted", 7)
    path([(700, 922), (700, 957)])
    box(cx, 958, cw, 56, "User-visible answer")

    panel(68, 440, 340, 428, "Knowledge (retrieval)", 3)
    left = column(98, 490, 280, [
        ("Documents + ACLs", None, None),
        ("Contextual chunks", "structure-aware, title > heading", None),
        ("Hybrid index", "BM25 + dense, fused by RRF", None),
        ("Filter, then rank", "ACL first; abstain when unsure", None),
    ])
    text(238, 816, "returns cited passages, marked untrusted", 14, color=BODY)
    mid = sum(left[-1]) / 2
    path([(378, mid), (cx - 1, mid)])

    panel(992, 440, 340, 428, "Tools (MCP)", 4)
    right = column(1022, 490, 280, [
        ("Policy check", "the user's own permissions", 6),
        ("Lethal-trifecta rule", "private + untrusted + outbound → ask", 7),
        ("Approval + ledger", "writes wait for a person, run once", None),
        ("MCP servers", None, None),
        ("HR · Jira · Slack", None, None),
    ])
    mid = sum(right[0]) / 2
    path([(cx + cw, mid), (1021, mid)])

    rect(68, 1046, 1264, 50, LINE, STRIP)
    text(700, 1077, "Traces on every step above: OpenTelemetry GenAI spans with the release version; "
                    "content capture off by default", 16)
    text(1310, 1077, "9", 15, color=BODY, anchor="end")

    # Change time
    panel(40, 1152, 1320, 220, "Change time", 10)
    steps = [
        ("Change", ["Prompt, model, tools,", "index or settings"]),
        ("Release bundle", ["One hash over all of them,", "stamped on every trace"]),
        ("Eval gate", ["pass^k on every case;", "regression and safety at 100%"]),
        ("Ships", ["Next version goes live;", "the last one stays for rollback"]),
    ]
    xs = [68 + i * 326 for i in range(4)]
    for i, (title, sub) in enumerate(steps):
        gate = title == "Eval gate"
        box(xs[i], 1206, 286, 86, title, sub,
            stroke=BLUE if gate else LINE, fill=BLUE_BG if gate else "#fff", width=2 if gate else 1.4)
        if i:
            path([(xs[i - 1] + 286, 1249), (xs[i] - 1, 1249)])

    path([(xs[0] + 143, 1292), (xs[0] + 143, 1322), (xs[3] + 143, 1322), (xs[3] + 143, 1294)], dashed=True)
    out.append(f'<circle cx="700" cy="1322" r="11" fill="#fff" stroke="{RED}" stroke-width="1.8"/>'
               f'<path d="M694,1316 L706,1328 M706,1316 L694,1328" stroke="{RED}" stroke-width="1.8"/>')
    text(700, 1356, "No skip path: a prompt edit is a release", 14, 500, RED)


def svg():
    draw()
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'font-family="{FONT}">'
            f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto"><path d="M0,1 L9,5 L0,9 z" fill="{ARROW}"/></marker></defs>'
            f'<rect width="{W}" height="{H}" fill="#fff"/>' + "".join(out) + "</svg>\n")


def browser():
    found = [os.environ.get("CHROME"), shutil.which("chrome"), shutil.which("google-chrome"),
             shutil.which("chromium"), shutil.which("msedge"),
             r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    return next((p for p in found if p and Path(p).exists()), None)


def render(source, png):
    exe = browser()
    if not exe:
        print("no Chrome or Edge found; wrote the SVG only")
        return
    page = ('<!doctype html><meta charset="utf-8"><link rel="stylesheet" '
            'href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=block">'
            '<style>html,body{margin:0;background:#fff}</style>' + source)
    with tempfile.TemporaryDirectory() as tmp:
        index = Path(tmp) / "hero.html"
        index.write_text(page, encoding="utf-8")
        subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--user-data-dir={Path(tmp) / 'profile'}", "--force-device-scale-factor=2",
                        f"--window-size={W},{H}", "--virtual-time-budget=10000",
                        f"--screenshot={png}", index.as_uri()], check=True, capture_output=True)
    print("wrote", png.name)


if __name__ == "__main__":
    source = svg()
    (OUT / "hero.svg").write_text(source, encoding="utf-8")
    print("wrote hero.svg")
    render(source, OUT / "hero.png")
