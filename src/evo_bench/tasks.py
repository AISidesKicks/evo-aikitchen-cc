"""Task corpus: loading and validating task cards.

A task card is the contract between the person who wrote the task and the person
who reads the score. The fields here are the ones from
``mds/evo-benchmark-evals.md``; everything except ``id``, ``prompt`` and
``acceptance`` is optional so a corpus can start small and fill in over time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

REQUIRED_FIELDS = ("id", "prompt", "acceptance")


@dataclass(frozen=True, slots=True)
class Task:
    """One task instance: a prompt, an environment and an acceptance check."""

    id: str
    prompt: str
    acceptance: str
    task_class: str = "unclassified"
    source: str = "unknown"
    fixture: str | None = None
    gold: str | None = None
    repo: str | None = None
    commit: str | None = None
    regression: str | None = None
    budget_turns: int = 20
    budget_usd: float = 2.0
    difficulty: str = "medium"
    contamination: str = "unknown"
    partial: str | None = None
    notes: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _from_mapping(row: dict[str, Any]) -> Task:
    missing = [name for name in REQUIRED_FIELDS if not row.get(name)]
    if missing:
        raise ValueError(f"task is missing required fields: {', '.join(missing)}")

    budget = row.get("budget") or {}
    known = {
        "id",
        "prompt",
        "acceptance",
        "class",
        "source",
        "fixture",
        "gold",
        "repo",
        "commit",
        "regression",
        "budget",
        "difficulty",
        "contamination",
        "partial",
        "notes",
    }

    return Task(
        id=str(row["id"]),
        prompt=str(row["prompt"]),
        acceptance=str(row["acceptance"]),
        task_class=str(row.get("class", "unclassified")),
        source=str(row.get("source", "unknown")),
        fixture=row.get("fixture"),
        gold=row.get("gold"),
        repo=row.get("repo"),
        commit=row.get("commit"),
        regression=row.get("regression"),
        budget_turns=int(budget.get("turns", 20)),
        budget_usd=float(budget.get("usd", 2.0)),
        difficulty=str(row.get("difficulty", "medium")),
        contamination=str(row.get("contamination", "unknown")),
        partial=row.get("partial"),
        notes=row.get("notes"),
        extra={k: v for k, v in row.items() if k not in known},
    )


def load_tasks(path: str | Path) -> list[Task]:
    """Load a JSONL task corpus, rejecting duplicate ids and blank lines."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"no task corpus at {source}")

    tasks: list[Task] = []
    seen: set[str] = set()

    with source.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text or text.startswith("//"):
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as error:
                raise ValueError(f"{source}:{number}: invalid JSON: {error}") from error
            if not isinstance(row, dict):
                raise ValueError(f"{source}:{number}: expected a JSON object")

            task = _from_mapping(row)
            if task.id in seen:
                raise ValueError(f"{source}:{number}: duplicate task id {task.id!r}")
            seen.add(task.id)
            tasks.append(task)

    return tasks


def class_counts(tasks: Iterable[Task]) -> dict[str, int]:
    """Count tasks per class, sorted by class name."""
    counts: dict[str, int] = {}
    for task in tasks:
        counts[task.task_class] = counts.get(task.task_class, 0) + 1
    return dict(sorted(counts.items()))
