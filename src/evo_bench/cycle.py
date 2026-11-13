"""A search cycle: run a baseline and a set of candidates, then gate each one.

This is the mechanical core of the self-improving loop. It does not invent
variants. Someone, or something, writes a variant directory; the cycle measures
it fairly, applies the promotion policy, and writes a summary a human can read.

The budget cap is enforced between runs, not after the campaign. A cycle that
would exceed the cap stops and says so, which is the difference between a budget
and a report.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from evo_bench.gate import Decision, Policy, evaluate, report as gate_report
from evo_bench.ledger import append
from evo_bench.pricing import PriceBook
from evo_bench.runner import RunResult, run_task, write_trace
from evo_bench.tasks import Task
from evo_bench.variants import Variant


@dataclass(slots=True)
class CycleResult:
    """Everything one cycle produced."""

    cycle_id: str
    ledger: Path
    rows: list[dict] = field(default_factory=list)
    decisions: dict[str, Decision] = field(default_factory=dict)
    spend: float = 0.0
    aborted: bool = False
    aborted_reason: str = ""

    def by_variant(self, name: str) -> list[dict]:
        return [row for row in self.rows if row.get("variant") == name]


async def run_cycle(
    tasks: Sequence[Task],
    *,
    baseline: Variant,
    candidates: Sequence[Variant],
    provider,
    model: str,
    ledger: Path,
    workdir_for: Callable[[], Path],
    policy: Policy | None = None,
    max_usd: float | None = None,
    timeout: float = 300.0,
    base: str | Path | None = None,
    max_turns: int | None = None,
    trace_dir: str | Path | None = None,
    prices: PriceBook | None = None,
    trials: int = 1,
    deadline: float | None = None,
) -> CycleResult:
    """Run the baseline and every candidate, then gate each candidate."""
    cycle_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result = CycleResult(cycle_id=cycle_id, ledger=ledger)
    rules = policy or Policy()

    variants = [baseline, *candidates]
    for variant in variants:
        for trial in range(trials):
            for task in tasks:
                if max_usd is not None and result.spend >= max_usd:
                    result.aborted = True
                    result.aborted_reason = (
                        f"spend {result.spend:.2f} reached the cap {max_usd:.2f}"
                    )
                    break

                run: RunResult = await run_task(
                    task,
                    mode="agent",
                    provider=provider,
                    model=model,
                    workdir=workdir_for(),
                    base=base,
                    timeout=timeout,
                    variant=variant,
                    variant_name=variant.name,
                    max_turns=max_turns,
                    prices=prices,
                    trial=trial,
                    deadline=deadline,
                )
                if trace_dir is not None:
                    write_trace(run, trace_dir)
                append(ledger, run.row)
                result.rows.append(run.row)
                result.spend += float(run.row.get("cost") or 0.0)

            if result.aborted:
                break
        if result.aborted:
            break

    baseline_rows = result.by_variant(baseline.name)
    for variant in candidates:
        candidate_rows = result.by_variant(variant.name)
        if not candidate_rows:
            continue
        result.decisions[variant.name] = evaluate(
            baseline_rows, candidate_rows, policy=rules
        )

    return result


def summary(result: CycleResult, *, baseline: str = "baseline") -> str:
    """Render a cycle as a markdown report."""
    lines = [
        f"# Cycle {result.cycle_id}",
        "",
        f"- baseline variant: `{baseline}`",
        f"- runs: {len(result.rows)}",
        f"- spend: {result.spend:.4f}",
        f"- ledger: `{result.ledger}`",
    ]
    if result.aborted:
        lines.append(f"- aborted: {result.aborted_reason}")
    lines.append("")

    if not result.decisions:
        lines.append("No candidate produced a decision.")
        return "\n".join(lines) + "\n"

    for name, decision in result.decisions.items():
        lines.append(f"## {name}")
        lines.append("")
        lines.append("```")
        lines.append(gate_report(decision, label_a=baseline, label_b=name))
        lines.append("```")
        lines.append("")

    promoted = [name for name, d in result.decisions.items() if d.promoted]
    lines.append("## Outcome")
    lines.append("")
    if promoted:
        lines.append(f"Promoted: {', '.join(promoted)}")
        lines.append("")
        lines.append("A promotion is a diff plus a score. Review the variant files, commit them,")
        lines.append("and re-run the cycle to confirm the gain survives a fresh set of seeds.")
    else:
        lines.append("Nothing promoted. That is a result too: the candidates did not beat the")
        lines.append("policy, and the ledger says by how much.")
    return "\n".join(lines) + "\n"


def write_summary(result: CycleResult, path: str | Path, *, baseline: str = "baseline") -> Path:
    """Write the markdown summary next to the ledger."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(summary(result, baseline=baseline), encoding="utf-8")
    return target


def elapsed(started: float) -> float:
    """Seconds since a ``time.monotonic()`` mark, for callers that want it."""
    return time.monotonic() - started
