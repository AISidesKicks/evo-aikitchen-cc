#!/usr/bin/env python3
"""Generate the presentation charts from the campaign ledgers.

Standard library only, no build step. Every number comes from `runs/*.jsonl` or
from the planning module, so the charts cannot drift from the data.

    pixi run python scripts/charts.py

Writes SVG into docs/assets/. Re-run it after a campaign; a chart you cannot
regenerate is a screenshot, and screenshots rot.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
OUT = ROOT / "docs" / "assets"

sys.path.insert(0, str(ROOT / "src"))

from evo_bench.planning import independent_effect  # noqa: E402

WIDTH = 760
HEIGHT = 380
PAD_LEFT = 64
PAD_BOTTOM = 62
PAD_TOP = 58
PAD_RIGHT = 24

INK = "#1f2937"
MUTED = "#6b7280"
GRID = "#e5e7eb"
BASE = "#2563eb"
CANDIDATE = "#f59e0b"
WARN = "#b42318"


@dataclass(frozen=True)
class Campaign:
    label: str
    path: str
    baseline: str
    candidate: str
    flaw: str


CAMPAIGNS = (
    Campaign("12 turns", "click.jsonl", "baseline", "strict", "every run truncated"),
    Campaign("30 turns", "click30.jsonl", "baseline", "strict", "no difference"),
    Campaign("20 turns", "click24b.jsonl", "baseline", "traceback-first", "79% capped"),
    Campaign("calibrated", "clickfair.jsonl", "baseline", "traceback-first", "saturated"),
)


def load(name: str) -> list[dict]:
    path = RUNS / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rate(rows: list[dict], variant: str) -> float:
    selected = [row for row in rows if row.get("variant") == variant]
    if not selected:
        return 0.0
    return sum(1 for row in selected if float(row.get("score") or 0) >= 1) / len(selected)


def capped(rows: list[dict]) -> float | None:
    if not rows:
        return None
    flagged = [
        row for row in rows if row.get("exit_reason") in ("max_turns", "deadline")
    ]
    return len(flagged) / len(rows)


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def frame(title: str, subtitle: str = "") -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="100%" role="img" aria-label="{escape(title)}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        f'<text x="{PAD_LEFT}" y="26" font-family="ui-sans-serif, system-ui, sans-serif" '
        f'font-size="17" font-weight="600" fill="{INK}">{escape(title)}</text>',
    ] + (
        [
            f'<text x="{PAD_LEFT}" y="44" font-family="ui-sans-serif, system-ui, sans-serif" '
            f'font-size="12" fill="{MUTED}">{escape(subtitle)}</text>'
        ]
        if subtitle
        else []
    )


def y_axis(max_value: float, label: str) -> list[str]:
    parts = []
    height = HEIGHT - PAD_TOP - PAD_BOTTOM - (12 if label else 0)
    for step in range(5):
        value = max_value * step / 4
        y = PAD_TOP + (12 if label else 0) + height * (1 - step / 4)
        parts.append(
            f'<line x1="{PAD_LEFT}" y1="{y:.1f}" x2="{WIDTH - PAD_RIGHT}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        text = f"{value:.0%}" if max_value <= 1 else f"{value:.0f}"
        parts.append(
            f'<text x="{PAD_LEFT - 10}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" '
            f'fill="{MUTED}">{text}</text>'
        )
    return parts


def campaign_chart() -> str:
    rows = [(c, load(c.path)) for c in CAMPAIGNS]
    parts = frame(
        "Four campaigns, four ways a benchmark lied",
        "share of tasks passed, per arm. Same question every time, different failure each time.",
    )
    parts += y_axis(1.0, "pass")
    plot_left = PAD_LEFT + 8
    plot_width = WIDTH - PAD_LEFT - PAD_RIGHT - 8
    group = plot_width / len(rows)
    height = HEIGHT - PAD_TOP - PAD_BOTTOM - 12

    for index, (campaign, data) in enumerate(rows):
        left = plot_left + group * index
        bar_width = group * 0.26
        for offset, (variant, colour) in enumerate(
            ((campaign.baseline, BASE), (campaign.candidate, CANDIDATE))
        ):
            value = rate(data, variant)
            bar_height = height * value
            x = left + group * 0.22 + offset * (bar_width + 6)
            y = PAD_TOP + 12 + height - bar_height
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
                f'height="{bar_height:.1f}" fill="{colour}" rx="2"/>'
            )
            parts.append(
                f'<text x="{x + bar_width / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" '
                f'font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" '
                f'font-weight="600" fill="{INK}">{value:.0%}</text>'
            )

        parts.append(
            f'<text x="{left + group / 2:.1f}" y="{HEIGHT - PAD_BOTTOM + 18}" '
            f'text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" '
            f'font-size="12" font-weight="600" fill="{INK}">{escape(campaign.label)}</text>'
        )
        parts.append(
            f'<text x="{left + group / 2:.1f}" y="{HEIGHT - PAD_BOTTOM + 34}" '
            f'text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" '
            f'font-size="11" fill="{WARN}">{escape(campaign.flaw)}</text>'
        )

    # The candidate changes name between campaigns, so the legend stays generic.
    for offset, (label, colour) in enumerate((("baseline", BASE), ("candidate", CANDIDATE))):
        x = WIDTH - PAD_RIGHT - 190 + offset * 95
        parts.append(f'<rect x="{x}" y="18" width="10" height="10" fill="{colour}" rx="2"/>')
        parts.append(
            f'<text x="{x + 15}" y="27" font-family="ui-sans-serif, system-ui, sans-serif" '
            f'font-size="11" fill="{MUTED}">{escape(label)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def capped_chart() -> str:
    measured = [
        ("30 turns", capped(load("click30.jsonl"))),
        ("20 turns", capped(load("click24b.jsonl"))),
        ("calibrated", capped(load("clickfair.jsonl"))),
    ]
    parts = frame(
        "Truncation, and the rule that catches it",
        "share of runs that stopped short, at the turn cap or the wall clock",
    )
    parts += y_axis(1.0, "capped")
    plot_left = PAD_LEFT + 8
    plot_width = WIDTH - PAD_LEFT - PAD_RIGHT - 8
    group = plot_width / len(measured)
    height = HEIGHT - PAD_TOP - PAD_BOTTOM - 12

    for index, (label, value) in enumerate(measured):
        share = 0.0 if value is None else value
        left = plot_left + group * index
        bar_width = group * 0.4
        bar_height = height * share
        x = left + group * 0.3
        y = PAD_TOP + 12 + height - bar_height
        colour = WARN if share > 0.5 else BASE
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
            f'height="{bar_height:.1f}" fill="{colour}" rx="2"/>'
        )
        parts.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" '
            f'font-family="ui-sans-serif, system-ui, sans-serif" font-size="12" '
            f'font-weight="600" fill="{INK}">{share:.0%}</text>'
        )
        parts.append(
            f'<text x="{left + group / 2:.1f}" y="{HEIGHT - PAD_BOTTOM + 18}" '
            f'text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" '
            f'font-size="12" fill="{INK}">{escape(label)}</text>'
        )

    parts.append(
        f'<text x="{PAD_LEFT}" y="{HEIGHT - 12}" font-family="ui-sans-serif, system-ui, sans-serif" '
        f'font-size="11" fill="{MUTED}">Above 50 percent the gate refuses to decide, '
        f"because the comparison would measure turn efficiency, not quality.</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


def resolution_chart() -> str:
    parts = frame(
        "What a corpus of this size can detect",
        "smallest difference detectable between two independent arms, at an 80% pass rate",
    )
    max_tasks = 400
    max_effect = 0.45
    plot_left = PAD_LEFT
    plot_width = WIDTH - PAD_LEFT - PAD_RIGHT
    height = HEIGHT - PAD_TOP - PAD_BOTTOM
    base_y = PAD_TOP + height

    for step in range(5):
        value = max_effect * step / 4
        y = base_y - height * value / max_effect
        parts.append(
            f'<line x1="{plot_left}" y1="{y:.1f}" x2="{WIDTH - PAD_RIGHT}" y2="{y:.1f}" '
            f'stroke="{GRID}"/>'
        )
        parts.append(
            f'<text x="{plot_left - 10}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" '
            f'fill="{MUTED}">{value:.0%}</text>'
        )

    points = []
    for tasks in range(5, max_tasks + 1, 5):
        effect = min(independent_effect(tasks, 0.8), max_effect)
        x = plot_left + plot_width * tasks / max_tasks
        y = base_y - height * effect / max_effect
        points.append(f"{x:.1f},{y:.1f}")

    parts.append(
        f'<polyline points="{" ".join(points)}" fill="none" stroke="{BASE}" stroke-width="2.5"/>'
    )

    for tasks, label in ((24, "24 tasks"), (67, "67 tasks"), (252, "252 tasks")):
        effect = min(independent_effect(tasks, 0.8), max_effect)
        x = plot_left + plot_width * tasks / max_tasks
        y = base_y - height * effect / max_effect
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{WARN}"/>')
        parts.append(
            f'<text x="{x + 8:.1f}" y="{y - 8:.1f}" font-family="ui-sans-serif, system-ui, sans-serif" '
            f'font-size="11" font-weight="600" fill="{INK}">{label}</text>'
        )

    for tick in (0, 100, 200, 300, 400):
        x = plot_left + plot_width * tick / max_tasks
        parts.append(
            f'<text x="{x:.1f}" y="{base_y + 18}" text-anchor="middle" '
            f'font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" '
            f'fill="{MUTED}">{tick}</text>'
        )

    parts.append(
        f'<text x="{plot_left}" y="{HEIGHT - 14}" font-family="ui-sans-serif, system-ui, sans-serif" '
        f'font-size="11" fill="{MUTED}">tasks per arm</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    charts = {
        "campaigns.svg": campaign_chart(),
        "capped.svg": capped_chart(),
        "resolution.svg": resolution_chart(),
    }
    for name, svg in charts.items():
        (OUT / name).write_text(svg, encoding="utf-8")
        print(f"wrote {OUT / name} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
