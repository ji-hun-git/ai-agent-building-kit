#!/usr/bin/env python3
"""Generate polished figures for AI Agent Building Kit (CC BY 4.0)."""
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# Palette — deep slate + electric teal / violet accents
C = {
    "bg": "#0B1220",
    "panel": "#121A2B",
    "panel2": "#172235",
    "ink": "#E8EEF8",
    "muted": "#93A0B8",
    "teal": "#2DD4BF",
    "teal_d": "#0F766E",
    "violet": "#A78BFA",
    "violet_d": "#6D28D9",
    "coral": "#FB7185",
    "amber": "#FBBF24",
    "blue": "#60A5FA",
    "line": "#2A364F",
    "white": "#FFFFFF",
    "ok": "#34D399",
    "warn": "#F59E0B",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": C["line"],
    "text.color": C["ink"],
    "figure.facecolor": C["bg"],
    "axes.facecolor": C["panel"],
    "savefig.facecolor": C["bg"],
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.25,
})


def rounded(ax, xy, w, h, fc, ec=None, lw=1.2, r=0.03, alpha=1.0, z=2):
    box = FancyBboxPatch(
        xy, w, h,
        boxstyle=f"round,pad=0.012,rounding_size={r}",
        linewidth=lw, facecolor=fc, edgecolor=ec or fc, alpha=alpha, zorder=z,
    )
    ax.add_patch(box)
    return box


def arrow(ax, p1, p2, color=None, lw=1.6, style="-|>", rad=0.0):
    color = color or C["teal"]
    a = FancyArrowPatch(
        p1, p2, arrowstyle=style, mutation_scale=12,
        linewidth=lw, color=color, connectionstyle=f"arc3,rad={rad}",
        zorder=3,
    )
    ax.add_patch(a)


def save(fig, name):
    png = OUT / f"{name}.png"
    svg = OUT / f"{name}.svg"
    fig.savefig(png, dpi=220)
    fig.savefig(svg)
    plt.close(fig)
    print("wrote", png.name, svg.name)


# ── 1. Skill workflow ───────────────────────────────────────────
def fig_skill_workflow():
    fig, ax = plt.subplots(figsize=(13, 6.2))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 6.2)
    ax.axis("off")

    ax.text(0.5, 5.75, "building-ai-agents · Skill Workflow", fontsize=18, fontweight="bold")
    ax.text(0.5, 5.35, "Always start with a live freshness check · then build in failure-closing order",
            fontsize=10, color=C["muted"])

    steps = [
        ("0", "Freshness", "Versions · advisories\nmodel lineup · lock"),
        ("1", "Frame", "Buy vs build\nspec the job"),
        ("2", "Simplify", "Simplest architecture\nthat can work"),
        ("3", "Eval first", "Cases before code\nrelease criteria"),
        ("4", "Build layers", "10 layers in order\nnon-negotiables"),
        ("5", "Threat model", "Injection · authz\nsandbox · logs"),
        ("6", "Ship gate", "Required evals\nrollback triggers"),
        ("7", "Handoff", "Runbooks · owners\nobservability"),
    ]
    cols = [C["amber"], C["violet"], C["blue"], C["teal"], C["teal"],
            C["coral"], C["ok"], C["violet"]]

    for i, ((n, title, body), col) in enumerate(zip(steps, cols)):
        x = 0.35 + (i % 4) * 3.15
        y = 3.35 if i < 4 else 0.45
        rounded(ax, (x, y), 2.95, 1.7, C["panel2"], ec=col, lw=1.8, r=0.1)
        ax.add_patch(Circle((x + 0.35, y + 1.3), 0.22, color=col, zorder=4))
        ax.text(x + 0.35, y + 1.3, n, ha="center", va="center", fontsize=9,
                fontweight="bold", color=C["bg"], zorder=5)
        ax.text(x + 0.7, y + 1.3, title, va="center", fontsize=12, fontweight="bold")
        ax.text(x + 0.25, y + 0.45, body, va="center", fontsize=8.5, color=C["muted"],
                linespacing=1.35)
        if i < 3:
            arrow(ax, (x + 2.95, y + 0.85), (x + 3.15, y + 0.85), C["line"], lw=1.2)
        elif i == 3:
            # down to next row start visually
            pass
        elif 4 <= i < 7:
            arrow(ax, (x + 2.95, y + 0.85), (x + 3.15, y + 0.85), C["line"], lw=1.2)

    # connector from step3 to step4
    arrow(ax, (11.7, 3.35), (11.7, 2.3), C["line"], lw=1.2)
    arrow(ax, (11.7, 2.3), (0.9, 2.3), C["line"], lw=1.2, style="-")
    arrow(ax, (0.9, 2.3), (0.9, 2.15), C["line"], lw=1.2)

    save(fig, "skill_workflow")


# ── 2. Eval benchmark chart (pass counts from the graded runs) ────
def fig_eval_results():
    # Pass counts from the graded runs
    # Round 1: with 18/19, without 14/19
    # Round 2: with 24/26, without 22/26
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2))
    fig.suptitle("Skill eval results (graded expectations)", fontsize=16, fontweight="bold",
                 color=C["ink"], y=0.98)
    fig.text(0.5, 0.91, "Graded runs, same tasks with and without the skill · snapshot 2026-10-27",
             ha="center", fontsize=9, color=C["muted"])

    data = [
        ("Round 1  ·  3 tasks", ["SDK choice", "HR design", "Legacy review"],
         [4, 6, 8], [3, 3, 8], [5, 6, 8]),
        ("Round 2  ·  4 tasks", ["SDK choice", "Stale snapshot", "HR design", "Legacy review"],
         [4, 5, 5, 10], [2, 5, 5, 10], [5, 5, 6, 10]),
    ]

    for ax, (title, labels, with_s, without_s, totals) in zip(axes, data):
        ax.set_facecolor(C["panel"])
        for spine in ax.spines.values():
            spine.set_color(C["line"])
        ax.tick_params(colors=C["muted"])
        ax.yaxis.label.set_color(C["muted"])
        ax.set_title(title, fontsize=12, fontweight="bold", color=C["ink"], pad=10)

        x = np.arange(len(labels))
        w = 0.35
        b1 = ax.bar(x - w / 2, with_s, w, label="With skill", color=C["teal"], edgecolor=C["teal_d"])
        b2 = ax.bar(x + w / 2, without_s, w, label="Without skill", color=C["violet"],
                    edgecolor=C["violet_d"], alpha=0.9)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8.5, color=C["muted"])
        ax.set_ylabel("Expectations passed", fontsize=9)
        ax.set_ylim(0, max(totals) + 2.5)
        ax.axhline(0, color=C["line"], lw=0.8)
        ax.legend(facecolor=C["panel2"], edgecolor=C["line"], labelcolor=C["ink"], fontsize=8)

        for bars, vals, tots in ((b1, with_s, totals), (b2, without_s, totals)):
            for bar, v, t in zip(bars, vals, tots):
                ax.text(bar.get_x() + bar.get_width() / 2, v + 0.15, f"{v}/{t}",
                        ha="center", va="bottom", fontsize=7.5, color=C["ink"])

        # total annotation
        tw, tn = sum(with_s), sum(totals)
        u_w, u_n = sum(without_s), sum(totals)
        ax.text(0.98, 0.02, f"Total  with {tw}/{tn}   without {u_w}/{u_n}",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5,
                color=C["muted"])

    save(fig, "eval_benchmark")


if __name__ == "__main__":
    fig_skill_workflow()
    fig_eval_results()
    print("done →", OUT)
