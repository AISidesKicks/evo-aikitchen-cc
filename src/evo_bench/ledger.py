"""Append-only run ledger.

One row per run. The ledger is the join key between the bench, production and
finance, so the schema is deliberately flat and the writer never rewrites
history: a re-scored run appends a new row with a new grader version.

The reducer that fills these rows lives outside the harness, so a harness
upgrade cannot silently change the schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

REQUIRED_FIELDS = (
    "run_id",
    "task_id",
    "harness",
    "harness_version",
    "model",
    "cost",
    "score",
)

FIELDS = (
    "run_id",
    "date",
    "task_id",
    "task_class",
    "split",
    "harness",
    "harness_version",
    "model",
    "provider",
    "tokens_in",
    "tokens_out",
    "cache_read",
    "cache_write",
    "cost",
    "wall_clock",
    "turns",
    "tool_calls",
    "exit_reason",
    "score",
    "partial_score",
    "grader_version",
    "human_rework",
)


def make_row(**values: Any) -> dict[str, Any]:
    """Build a ledger row, filling absent fields with None and rejecting typos."""
    unknown = set(values) - set(FIELDS)
    if unknown:
        raise ValueError(f"unknown ledger fields: {', '.join(sorted(unknown))}")
    missing = [name for name in REQUIRED_FIELDS if values.get(name) in (None, "")]
    if missing:
        raise ValueError(f"missing required ledger fields: {', '.join(missing)}")
    return {name: values.get(name) for name in FIELDS}


def append(path: str | Path, row: dict[str, Any]) -> None:
    """Append one row to a JSONL ledger, creating the file if needed."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def read(path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield ledger rows in file order."""
    target = Path(path)
    if not target.exists():
        return
    with target.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                yield json.loads(text)


def totals(path: str | Path) -> dict[str, float]:
    """Sum cost and count runs and successes, for a quick campaign check."""
    runs = 0
    cost = 0.0
    wins = 0
    for row in read(path):
        runs += 1
        cost += float(row.get("cost") or 0.0)
        if float(row.get("score") or 0.0) >= 1.0:
            wins += 1
    return {
        "runs": runs,
        "cost": cost,
        "wins": wins,
        "cost_per_win": (cost / wins) if wins else float("nan"),
    }
