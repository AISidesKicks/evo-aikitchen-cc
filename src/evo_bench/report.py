"""A self-contained HTML report for a ledger.

Every campaign should produce an artifact a human can read without a terminal,
a database or a running service. This module writes one: a single HTML file with
inline CSS, no JavaScript and no external assets, so it can be attached to a pull
request, committed as a receipt, or opened from a scratch directory.

The report shows what the ledger knows: pass rate with an interval, cost, and the
paired difference against the baseline. It does not invent a verdict. Verdicts
belong to the gate, which applies a policy that was written down first.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from evo_bench.compare import compare, trials_per_task
from evo_bench.stats import wilson_interval

CSS = """
:root { color-scheme: light dark; }
body { font: 15px/1.5 ui-sans-serif, system-ui, sans-serif; margin: 2rem auto; max-width: 60rem; padding: 0 1rem; }
h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
h2 { font-size: 1.1rem; margin-top: 2rem; }
p.meta { opacity: 0.7; margin-top: 0; }
table { border-collapse: collapse; width: 100%; margin-top: 0.5rem; }
th, td { text-align: left; padding: 0.35rem 0.6rem; border-bottom: 1px solid color-mix(in srgb, currentColor 20%, transparent); }
th { font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.03em; opacity: 0.75; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.pass { color: #1a7f37; font-weight: 600; }
.fail { color: #b42318; font-weight: 600; }
.note { font-size: 0.9rem; opacity: 0.75; }
code { font-family: ui-monospace, monospace; font-size: 0.9em; }
"""


@dataclass(frozen=True, slots=True)
class VariantStats:
    """One row of the summary table."""

    name: str
    passes: int
    tasks: int
    low: float
    high: float
    cost: float
    delta: float = 0.0
    p_value: float = 1.0

    @property
    def rate(self) -> float:
        return self.passes / self.tasks if self.tasks else 0.0


def _variant_order(rows: Sequence[Mapping[str, object]], baseline: str | None) -> list[str]:
    seen: list[str] = []
    for row in rows:
        name = str(row.get("variant") or "baseline")
        if name not in seen:
            seen.append(name)
    if baseline and baseline in seen:
        seen.remove(baseline)
        seen.insert(0, baseline)
    return seen


def _matrix(
    rows: Sequence[Mapping[str, object]], variants: Sequence[str]
) -> tuple[list[str], dict[tuple[str, str], float]]:
    """Build the pass matrix, aggregating repeated trials as pass^k.

    A cell is a pass only when every trial for that task passed, so the report
    answers the reliability question and not the luck question.
    """
    tasks: list[str] = []
    seen: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        task_id = str(row["task_id"])
        variant = str(row.get("variant") or "baseline")
        if task_id not in tasks:
            tasks.append(task_id)
        seen.setdefault((variant, task_id), []).append(float(row.get("score") or 0.0))
    cells = {
        key: 1.0 if all(score >= 1.0 for score in scores) else 0.0
        for key, scores in seen.items()
    }
    return tasks, cells


def summarise(
    rows: Sequence[Mapping[str, object]], *, baseline: str | None = None
) -> list[VariantStats]:
    variants = _variant_order(rows, baseline)
    tasks, cells = _matrix(rows, variants)
    stats: list[VariantStats] = []

    for name in variants:
        scores = [cells.get((name, task), 0.0) for task in tasks]
        passes = sum(1 for score in scores if score >= 1.0)
        low, high = wilson_interval(passes, len(tasks)) if tasks else (0.0, 0.0)
        cost = sum(
            float(row.get("cost") or 0.0)
            for row in rows
            if str(row.get("variant") or "baseline") == name
        )
        delta = 0.0
        p_value = 1.0
        if baseline and name != baseline:
            paired = compare(
                [row for row in rows if str(row.get("variant") or "baseline") == baseline],
                [row for row in rows if str(row.get("variant") or "baseline") == name],
            )
            delta = paired.delta
            p_value = paired.p_value
        stats.append(
            VariantStats(
                name=name,
                passes=passes,
                tasks=len(tasks),
                low=low,
                high=high,
                cost=cost,
                delta=delta,
                p_value=p_value,
            )
        )
    return stats


def _summary_table(stats: Iterable[VariantStats], baseline: str | None) -> str:
    head = (
        "<tr><th>Variant</th><th class=\"num\">Pass</th><th class=\"num\">Rate</th>"
        "<th class=\"num\">95% CI</th><th class=\"num\">Cost</th>"
        "<th class=\"num\">Delta</th><th class=\"num\">p</th></tr>"
    )
    body = []
    for item in stats:
        delta = "-" if item.name == baseline else f"{item.delta:+.1%}"
        p_value = "-" if item.name == baseline else f"{item.p_value:.3f}"
        body.append(
            "<tr>"
            f"<td>{escape(item.name)}</td>"
            f"<td class=\"num\">{item.passes}/{item.tasks}</td>"
            f"<td class=\"num\">{item.rate:.1%}</td>"
            f"<td class=\"num\">{item.low:.1%} to {item.high:.1%}</td>"
            f"<td class=\"num\">${item.cost:.4f}</td>"
            f"<td class=\"num\">{delta}</td>"
            f"<td class=\"num\">{p_value}</td>"
            "</tr>"
        )
    return f"<table>{head}{''.join(body)}</table>"


def _matrix_table(
    tasks: Sequence[str], variants: Sequence[str], cells: Mapping[tuple[str, str], float]
) -> str:
    head = "<tr><th>Task</th>" + "".join(f"<th class=\"num\">{escape(v)}</th>" for v in variants) + "</tr>"
    rows = []
    for task in tasks:
        cells_html = []
        for variant in variants:
            score = cells.get((variant, task))
            if score is None:
                cells_html.append("<td class=\"num\">-</td>")
            elif score >= 1.0:
                cells_html.append("<td class=\"num pass\">pass</td>")
            else:
                cells_html.append("<td class=\"num fail\">fail</td>")
        rows.append(f"<tr><td><code>{escape(task)}</code></td>{''.join(cells_html)}</tr>")
    return f"<table>{head}{''.join(rows)}</table>"


def build_report(
    rows: Sequence[Mapping[str, object]],
    *,
    title: str = "EVO bench report",
    baseline: str | None = None,
    source: str = "",
) -> str:
    """Render a ledger as one self-contained HTML page."""
    rows = list(rows)
    variants = _variant_order(rows, baseline)
    tasks, cells = _matrix(rows, variants)
    stats = summarise(rows, baseline=baseline)
    spend = sum(float(row.get("cost") or 0.0) for row in rows)
    models = sorted({str(row.get("model")) for row in rows if row.get("model")})
    harnesses = sorted(
        {f"{row.get('harness')} {row.get('harness_version')}" for row in rows if row.get("harness")}
    )
    dates = sorted({str(row.get("date"))[:10] for row in rows if row.get("date")})

    trials = trials_per_task(rows)
    meta = [
        f"{len(rows)} runs",
        f"{len(tasks)} tasks",
        f"pass^{trials} aggregation",
        f"{len(variants)} variants",
        f"${spend:.4f}",
    ]
    if dates:
        meta.append(f"{dates[0]} to {dates[-1]}" if len(dates) > 1 else dates[0])
    if models:
        meta.append(", ".join(models))
    if harnesses:
        meta.append(", ".join(harnesses))

    source_line = (
        f"<p class=\"note\">Ledger: <code>{escape(source)}</code></p>" if source else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<h1>{escape(title)}</h1>
<p class="meta">{escape(" | ".join(meta))}</p>
{source_line}
<h2>Variants</h2>
{_summary_table(stats, baseline)}
<p class="note">Delta and p are paired against <code>{escape(baseline or "-")}</code> using an exact
McNemar test. A verdict comes from <code>evo_bench gate</code>, which also applies a cost and holdout policy.</p>

<h2>Per task</h2>
{_matrix_table(tasks, variants, cells)}

<h2>How to read this</h2>
<p class="note">The pass rate has a 95% Wilson interval. If the interval is wider than the effect you
care about, the corpus is too small for that decision, and more tasks are cheaper than more arguments.
A p value above 0.05 means the difference is inside the noise, whatever the headline percentage says.</p>
</body>
</html>
"""


def write_report(
    path: str | Path,
    rows: Sequence[Mapping[str, object]],
    *,
    title: str = "EVO bench report",
    baseline: str | None = None,
    source: str = "",
) -> str:
    """Write the report and return the path as a string."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        build_report(rows, title=title, baseline=baseline, source=source), encoding="utf-8"
    )
    return str(target)
