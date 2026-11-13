"""Paired comparison of two variants.

The whole point of pairing is that the tasks both variants agree on carry no
information about the difference. So the report leads with the discordant
counts, then the exact McNemar p-value, then the cost. A score delta without
those three numbers is a rumour with a decimal point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from evo_bench.stats import mcnemar_exact, wilson_interval


@dataclass(frozen=True, slots=True)
class Paired:
    """One paired comparison, keyed by task id."""

    both_pass: int
    both_fail: int
    a_only: int
    b_only: int
    cost_a: float
    cost_b: float
    missing: tuple[str, ...] = field(default_factory=tuple)

    @property
    def tasks(self) -> int:
        return self.both_pass + self.both_fail + self.a_only + self.b_only

    @property
    def a_rate(self) -> float:
        return (self.both_pass + self.a_only) / self.tasks if self.tasks else 0.0

    @property
    def b_rate(self) -> float:
        return (self.both_pass + self.b_only) / self.tasks if self.tasks else 0.0

    @property
    def delta(self) -> float:
        return self.b_rate - self.a_rate

    @property
    def p_value(self) -> float:
        return mcnemar_exact(self.b_only, self.a_only)

    @property
    def discordant(self) -> int:
        return self.a_only + self.b_only

    def interval(self) -> tuple[float, float]:
        """Wilson interval for variant B, so the rate has a range."""
        return wilson_interval(self.both_pass + self.b_only, self.tasks)

    def verdict(self, alpha: float = 0.05) -> str:
        if self.discordant == 0:
            return "no difference"
        if self.p_value >= alpha:
            return "inside noise"
        return "B better" if self.b_only > self.a_only else "A better"


def _scores(rows: Iterable[Mapping[str, object]]) -> dict[str, float]:
    """Reduce ledger rows to one score per task.

    Repeated trials aggregate as ``pass^k``: a task counts only when every trial
    passed. That is the conservative reading, and it is the one that matches the
    question a promotion gate asks, which is whether the variant is reliable and
    not whether it can succeed once.
    """
    trials: dict[str, list[float]] = {}
    for row in rows:
        task_id = str(row["task_id"])
        trials.setdefault(task_id, []).append(float(row.get("score") or 0.0))
    return {
        task_id: 1.0 if all(score >= 1.0 for score in scores) else 0.0
        for task_id, scores in trials.items()
    }


def trials_per_task(rows: Iterable[Mapping[str, object]]) -> int:
    """The largest number of runs recorded for one task in a ledger."""
    counts: dict[str, int] = {}
    for row in rows:
        task_id = str(row["task_id"])
        counts[task_id] = counts.get(task_id, 0) + 1
    return max(counts.values(), default=0)


def compare(
    rows_a: Iterable[Mapping[str, object]],
    rows_b: Iterable[Mapping[str, object]],
) -> Paired:
    """Compare variant A against variant B on the tasks they share."""
    a = _scores(rows_a)
    b = _scores(rows_b)

    shared = sorted(set(a) & set(b))
    missing = tuple(sorted(set(a) ^ set(b)))

    both_pass = both_fail = a_only = b_only = 0
    for task_id in shared:
        passed_a = a[task_id] >= 1.0
        passed_b = b[task_id] >= 1.0
        if passed_a and passed_b:
            both_pass += 1
        elif passed_a:
            a_only += 1
        elif passed_b:
            b_only += 1
        else:
            both_fail += 1

    return Paired(
        both_pass=both_pass,
        both_fail=both_fail,
        a_only=a_only,
        b_only=b_only,
        cost_a=sum(float(row.get("cost") or 0.0) for row in rows_a),
        cost_b=sum(float(row.get("cost") or 0.0) for row in rows_b),
        missing=missing,
    )


def report(paired: Paired, *, label_a: str = "A", label_b: str = "B") -> str:
    """Render a paired comparison as a small text table."""
    low, high = paired.interval()
    lines = [
        f"tasks          {paired.tasks}",
        f"both pass      {paired.both_pass}",
        f"both fail      {paired.both_fail}",
        f"{label_a} only        {paired.a_only}",
        f"{label_b} only        {paired.b_only}",
        f"{label_a} rate        {paired.a_rate:.1%}",
        f"{label_b} rate        {paired.b_rate:.1%} (95% CI {low:.1%} to {high:.1%})",
        f"delta          {paired.delta:+.1%}",
        f"mcnemar p      {paired.p_value:.4f}",
        f"cost           {paired.cost_a:.2f} -> {paired.cost_b:.2f}",
        f"verdict        {paired.verdict()}",
    ]
    if paired.missing:
        lines.append(f"unpaired       {', '.join(paired.missing)}")
    return "\n".join(lines)
