"""The promotion gate.

A comparison produces numbers. The gate turns numbers into a decision, using a
policy that is written down before the campaign starts. That ordering is the
whole point: a rule invented after seeing the result is not a rule.

The default policy is deliberately strict. It refuses to promote on fewer than
20 paired tasks, it demands a significant paired difference, it caps the cost
increase, and it rejects any regression on the holdout split.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from evo_bench.compare import Paired, compare

PROMOTE = "promote"
REJECT = "reject"
INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class Policy:
    """The decision rule, fixed before the campaign."""

    alpha: float = 0.05
    min_tasks: int = 20
    min_effect: float = 0.0
    max_cost_increase: float = 0.20
    holdout_tolerance: float = 0.0

    def __post_init__(self) -> None:
        if not 0 < self.alpha < 1:
            raise ValueError("alpha must be between 0 and 1")
        if self.min_tasks < 1:
            raise ValueError("min_tasks must be at least 1")
        if self.max_cost_increase < 0:
            raise ValueError("max_cost_increase must be non-negative")


@dataclass(frozen=True, slots=True)
class Decision:
    """The gate's answer, with the reasons that produced it."""

    verdict: str
    reasons: tuple[str, ...]
    paired: Paired
    holdout: Paired | None = None
    # NaN means the ratio was never computed, because a rule fired first.
    cost_ratio: float = float("nan")

    @property
    def promoted(self) -> bool:
        return self.verdict == PROMOTE


def _split_rows(
    rows: Iterable[Mapping[str, object]], split: str
) -> list[Mapping[str, object]]:
    return [row for row in rows if str(row.get("split") or "train") == split]


def _train_rows(rows: Iterable[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Everything that is not the holdout.

    The holdout is a guard, not evidence. Mixing it into the main comparison
    would let a holdout regression hide inside a train improvement.
    """
    return [row for row in rows if str(row.get("split") or "train") != "holdout"]


def truncated_share(rows: Iterable[Mapping[str, object]]) -> float:
    """Share of runs that stopped at the turn cap instead of finishing."""
    rows = list(rows)
    if not rows:
        return 0.0
    capped = sum(1 for row in rows if str(row.get("exit_reason")) == "max_turns")
    return capped / len(rows)


def cost_per_success(paired: Paired, cost: float, wins: int) -> float:
    """Cost divided by successes, or infinity when nothing succeeded."""
    return cost / wins if wins else float("inf")


def evaluate(
    baseline: Iterable[Mapping[str, object]],
    candidate: Iterable[Mapping[str, object]],
    *,
    policy: Policy | None = None,
    use_holdout: bool = True,
) -> Decision:
    """Decide whether the candidate may be promoted over the baseline."""
    rules = policy or Policy()
    baseline_rows = list(baseline)
    candidate_rows = list(candidate)

    paired = compare(_train_rows(baseline_rows), _train_rows(candidate_rows))
    reasons: list[str] = []

    truncated = max(
        truncated_share(_train_rows(baseline_rows)),
        truncated_share(_train_rows(candidate_rows)),
    )
    if truncated > 0.5:
        return Decision(
            verdict=INCONCLUSIVE,
            reasons=(
                f"{truncated:.0%} of runs stopped at the turn cap",
                "raise the budget before reading anything into the difference",
            ),
            paired=paired,
        )

    if paired.tasks < rules.min_tasks:
        return Decision(
            verdict=INCONCLUSIVE,
            reasons=(
                f"only {paired.tasks} paired tasks, the policy needs {rules.min_tasks}",
                "add tasks or accept that this decision is a judgement call",
            ),
            paired=paired,
        )

    if paired.discordant == 0:
        return Decision(
            verdict=INCONCLUSIVE,
            reasons=("the two variants agree on every task",),
            paired=paired,
        )

    if paired.delta < 0 and paired.p_value < rules.alpha:
        return Decision(
            verdict=REJECT,
            reasons=(
                f"candidate is worse by {abs(paired.delta):.1%} with p={paired.p_value:.4f}",
            ),
            paired=paired,
        )

    if paired.p_value >= rules.alpha:
        return Decision(
            verdict=INCONCLUSIVE,
            reasons=(
                f"delta {paired.delta:+.1%} with p={paired.p_value:.4f} is inside noise",
                f"{paired.discordant} discordant tasks, {paired.b_only} for the candidate",
            ),
            paired=paired,
        )

    if paired.delta < rules.min_effect:
        return Decision(
            verdict=INCONCLUSIVE,
            reasons=(
                f"delta {paired.delta:+.1%} is below the minimum effect {rules.min_effect:.1%}",
            ),
            paired=paired,
        )

    a_wins = paired.both_pass + paired.a_only
    b_wins = paired.both_pass + paired.b_only
    base_cost = cost_per_success(paired, paired.cost_a, a_wins)
    candidate_cost = cost_per_success(paired, paired.cost_b, b_wins)
    if math.isinf(base_cost) or math.isinf(candidate_cost):
        # One side has no successes, so the ratio is not defined. Do not reject
        # on a number that does not exist.
        cost_ratio = 1.0
        cost_note = "cost per success not comparable, one side has no successes"
    else:
        cost_ratio = candidate_cost / max(base_cost, 1e-9)
        cost_note = f"cost per success ratio {cost_ratio:.2f}"

    holdout: Paired | None = None
    if use_holdout:
        holdout = compare(
            _split_rows(baseline_rows, "holdout"), _split_rows(candidate_rows, "holdout")
        )
        if holdout.tasks and holdout.delta < -rules.holdout_tolerance:
            reasons.append(
                f"holdout regressed by {abs(holdout.delta):.1%} over {holdout.tasks} tasks"
            )
            return Decision(
                verdict=REJECT,
                reasons=tuple(reasons),
                paired=paired,
                holdout=holdout,
                cost_ratio=cost_ratio,
            )

    if cost_ratio > 1 + rules.max_cost_increase:
        reasons.append(
            f"cost per success rose {(cost_ratio - 1):.0%}, over the "
            f"{rules.max_cost_increase:.0%} limit"
        )
        return Decision(
            verdict=REJECT,
            reasons=tuple(reasons),
            paired=paired,
            holdout=holdout,
            cost_ratio=cost_ratio,
        )

    reasons.append(f"delta {paired.delta:+.1%} with p={paired.p_value:.4f}")
    reasons.append(cost_note)
    if holdout is not None and holdout.tasks:
        reasons.append(
            f"holdout {holdout.delta:+.1%} over {holdout.tasks} tasks"
        )
    return Decision(
        verdict=PROMOTE,
        reasons=tuple(reasons),
        paired=paired,
        holdout=holdout,
        cost_ratio=cost_ratio,
    )


def report(decision: Decision, *, label_a: str = "baseline", label_b: str = "candidate") -> str:
    """Render a decision for a terminal or a commit message."""
    lines = [
        f"verdict        {decision.verdict.upper()}",
        f"{label_a:<14} {decision.paired.a_rate:.1%}",
        f"{label_b:<14} {decision.paired.b_rate:.1%}",
        f"delta          {decision.paired.delta:+.1%}",
        f"mcnemar p      {decision.paired.p_value:.4f}",
        f"discordant     {decision.paired.discordant} "
        f"({decision.paired.a_only} {label_a}, {decision.paired.b_only} {label_b})",
        "cost ratio     "
        + ("-" if math.isnan(decision.cost_ratio) else f"{decision.cost_ratio:.2f}"),
    ]
    if decision.holdout is not None and decision.holdout.tasks:
        lines.append(f"holdout        {decision.holdout.delta:+.1%} over {decision.holdout.tasks} tasks")
    lines.append("reasons:")
    lines.extend(f"  - {reason}" for reason in decision.reasons)
    return "\n".join(lines)
