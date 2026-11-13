"""Set each task's turn budget from the turns it actually needs.

A single global budget cannot be fair across a corpus with a bimodal turn
distribution. At 30 turns the easy half is free and the pass rate saturates; at
20 turns the hard half is truncated and 79 percent of runs hit the cap. The
budget belongs to the task, not to the campaign.

Calibration runs the baseline once per task at a generous ceiling, records the
turns used, and writes ``ceil(turns * headroom)`` into the task card. Later
campaigns then inherit a fair budget with no flag to remember.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from evo_bench.tasks import Task


@dataclass(frozen=True, slots=True)
class Calibration:
    """The turns observed for one task, and the budget derived from them."""

    task_id: str
    runs: int
    median_turns: float
    max_turns: int
    capped: int
    budget: int


def summarise(
    rows: list[Mapping[str, object]], *, headroom: float = 1.5, floor: int = 8
) -> list[Calibration]:
    """Turn per-task turn counts into budgets."""
    turns: dict[str, list[int]] = {}
    capped: dict[str, int] = {}
    for row in rows:
        task_id = str(row["task_id"])
        turns.setdefault(task_id, []).append(int(row.get("turns") or 0))
        if str(row.get("exit_reason")) == "max_turns":
            capped[task_id] = capped.get(task_id, 0) + 1

    result: list[Calibration] = []
    for task_id, values in sorted(turns.items()):
        median = statistics.median(values)
        peak = max(values)
        capping = capped.get(task_id, 0)
        # A capped task needs more room than it used, because it never finished.
        basis = peak if capping else median
        budget = max(floor, math.ceil(basis * headroom))
        result.append(
            Calibration(
                task_id=task_id,
                runs=len(values),
                median_turns=median,
                max_turns=peak,
                capped=capping,
                budget=budget,
            )
        )
    return result


def apply(
    tasks_path: str | Path,
    calibrations: list[Calibration],
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Write the budgets back into a task card file. Returns old -> new pairs."""
    path = Path(tasks_path)
    by_id = {item.task_id: item.budget for item in calibrations}
    rows = []
    changes: dict[str, int] = {}

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        card = json.loads(line)
        budget = by_id.get(card["id"])
        if budget is not None:
            current = int((card.get("budget") or {}).get("turns", 0))
            if current != budget:
                changes[card["id"]] = budget
            card.setdefault("budget", {})["turns"] = budget
        rows.append(json.dumps(card))

    if not dry_run:
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return changes


def report(calibrations: list[Calibration]) -> str:
    """Render calibration as a short table."""
    lines = [f"{'task':<44} {'runs':>4} {'median':>6} {'max':>4} {'cap':>3} {'budget':>6}"]
    for item in calibrations:
        lines.append(
            f"{item.task_id[:44]:<44} {item.runs:>4} {item.median_turns:>6.1f} "
            f"{item.max_turns:>4} {item.capped:>3} {item.budget:>6}"
        )
    budgets = [item.budget for item in calibrations]
    if budgets:
        lines.append("")
        lines.append(
            f"{len(budgets)} tasks, budget {min(budgets)} to {max(budgets)}, "
            f"median {statistics.median(budgets):.0f}"
        )
    return "\n".join(lines)
