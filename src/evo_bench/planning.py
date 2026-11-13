"""Corpus planning: what a bench can and cannot resolve.

The arithmetic is boring and the consequence is not. Twelve tasks at an 80 percent
pass rate have a 95 percent interval of roughly plus or minus 23 points, and two
independent arms need a difference of about 45 points before the comparison is
worth running. Most harness changes are worth two to five points.

This module answers the question before the money is spent: given this corpus and
this policy, what is the smallest effect that could possibly be promoted?
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from evo_bench.stats import Z_ALPHA, Z_POWER


@dataclass(frozen=True, slots=True)
class Resolution:
    """What a corpus of this size can resolve."""

    tasks: int
    rate: float
    half_width: float
    independent_effect: float
    paired_effect: float
    discordant: float
    discordant_tasks: float = 0.0
    paired_achievable: bool = True

    def as_dict(self) -> dict[str, float | int]:
        return {
            "tasks": self.tasks,
            "rate": self.rate,
            "half_width": self.half_width,
            "independent_effect": self.independent_effect,
            "paired_effect": self.paired_effect,
            "discordant": self.discordant,
        }


def half_width(tasks: int, rate: float) -> float:
    """Half-width of the 95 percent interval for one proportion."""
    if tasks <= 0:
        raise ValueError("tasks must be positive")
    return Z_ALPHA * math.sqrt(rate * (1 - rate) / tasks)


def independent_effect(tasks: int, rate: float) -> float:
    """Smallest difference detectable between two independent arms."""
    if tasks <= 0:
        raise ValueError("tasks must be positive")
    return (Z_ALPHA + Z_POWER) * math.sqrt(2 * rate * (1 - rate) / tasks)


def paired_effect(tasks: int, discordant: float, rate: float = 0.8) -> float:
    """Smallest difference detectable with a paired design.

    ``discordant`` is the share of tasks where the two variants disagree. Pairing
    is cheaper because the agreed tasks cancel, but it cannot beat the discordant
    share: if only 10 percent of tasks can differ, no effect above 10 points is
    expressible, however many tasks you add.

    The answer is found by bisection against the sample-size formula, because the
    formula cannot be inverted in closed form without pretending the discordant
    share is independent of the effect.
    """
    if tasks <= 0:
        raise ValueError("tasks must be positive")
    if not 0 < discordant <= 1:
        raise ValueError("discordant must be between 0 and 1")

    low, high = 1e-4, discordant
    for _ in range(60):
        middle = (low + high) / 2
        if tasks_for(middle, rate=rate, discordant=discordant)["paired"] <= tasks:
            high = middle
        else:
            low = middle
    return high


def resolution(tasks: int, *, rate: float = 0.8, discordant: float = 0.1) -> Resolution:
    """Summarise what a corpus can resolve."""
    return Resolution(
        tasks=tasks,
        rate=rate,
        half_width=half_width(tasks, rate),
        independent_effect=independent_effect(tasks, rate),
        paired_effect=paired_effect(tasks, discordant, rate),
        discordant=discordant,
        discordant_tasks=tasks * discordant,
        paired_achievable=tasks_for(discordant, rate=rate, discordant=discordant)["paired"]
        <= tasks,
    )


def tasks_for(effect: float, *, rate: float = 0.8, discordant: float = 0.1) -> dict[str, int]:
    """Tasks needed per arm to resolve ``effect``, independent and paired."""
    if not 0 < effect < 1:
        raise ValueError("effect must be between 0 and 1")

    independent = math.ceil(
        2 * (Z_ALPHA + Z_POWER) ** 2 * rate * (1 - rate) / effect**2
    )
    # Paired: n = (z_a * sqrt(psi) + z_b * sqrt(psi - d^2))^2 / d^2, where psi is
    # the share of tasks the variants disagree on. An effect larger than psi is
    # not expressible, because the agreed tasks cannot move.
    paired = math.ceil(
        (
            Z_ALPHA * math.sqrt(discordant)
            + Z_POWER * math.sqrt(max(discordant - effect**2, 0.0))
        )
        ** 2
        / effect**2
    )
    return {"independent": independent, "paired": paired}


def report(resolution_result: Resolution) -> str:
    """Render the resolution as a short text block."""
    item = resolution_result
    lines = [
        f"tasks                 {item.tasks}",
        f"assumed pass rate     {item.rate:.0%}",
        f"95% half-width        {item.half_width:.1%}",
        f"independent effect    {item.independent_effect:.1%}",
        (
            f"paired effect         {item.paired_effect:.1%} "
            f"({item.discordant_tasks:.1f} discordant tasks expected)"
            if item.paired_achievable
            else "paired effect         not achievable: even a "
            f"{item.discordant:.0%} effect needs "
            f"{tasks_for(item.discordant, rate=item.rate, discordant=item.discordant)['paired']} tasks"
        ),
    ]
    if item.discordant_tasks < 6:
        lines.append("")
        lines.append(
            "A paired design needs about six one-sided discordant tasks before an exact"
        )
        lines.append(
            "McNemar test can reach p < 0.05 at all. This corpus is too small for a"
        )
        lines.append("promotion, whatever the pass rates say.")
    if item.independent_effect > 0.15:
        lines.append("")
        lines.append(
            "Independent comparison is coarser than most prompt-level changes. Pair the"
        )
        lines.append("variants on the same tasks before trusting a delta.")
    return "\n".join(lines)
