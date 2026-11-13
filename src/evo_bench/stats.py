"""Statistics for the bench.

Two functions carry most of the weight: a Wilson interval for a single
proportion, and an exact McNemar test for a paired comparison. Both are
stdlib-only on purpose, because a bench that needs a scientific stack to report
an interval is a bench that will not report one.

The rule these implement is the resolution rule from
``mds/evo-benchmark-evals.md``: never claim an effect smaller than the interval
the task set can resolve.
"""

from __future__ import annotations

import math

# Two-sided 95 percent and 80 percent power, as normal quantiles.
Z_ALPHA = 1.959963984540054
Z_POWER = 0.8416212335729143


def wilson_interval(successes: int, n: int, z: float = Z_ALPHA) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Preferred over the normal approximation because it stays inside 0 and 1 and
    behaves sanely at small n and at proportions near the edges.
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= successes <= n:
        raise ValueError("successes must be between 0 and n")

    p = successes / n
    denominator = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def mcnemar_exact(wins: int, losses: int) -> float:
    """Two-sided exact McNemar p-value.

    ``wins`` and ``losses`` are the discordant counts: tasks where exactly one
    of the two variants succeeded. Tasks where both pass or both fail carry no
    information about the difference and must not be passed here.

    This is an exact binomial test at p = 0.5, so it is valid at the small
    discordant counts a weekly bench produces, where the chi-square
    approximation is not.
    """
    if wins < 0 or losses < 0:
        raise ValueError("counts must be non-negative")

    n = wins + losses
    if n == 0:
        return 1.0

    tail = sum(math.comb(n, i) for i in range(min(wins, losses) + 1)) / 2**n
    return min(1.0, 2 * tail)


def tasks_per_arm(effect: float, p: float = 0.8) -> int:
    """Tasks needed per arm for an independent two-proportion comparison.

    ``effect`` is the absolute difference in success rate you want to detect,
    as a fraction. At p = 0.8 and effect = 0.02 this returns about 6,280, which
    is why small effects on public benchmarks are so expensive to establish.
    """
    if not 0 < effect < 1:
        raise ValueError("effect must be between 0 and 1")
    if not 0 < p < 1:
        raise ValueError("p must be between 0 and 1")

    n = 2 * (Z_ALPHA + Z_POWER) ** 2 * p * (1 - p) / effect**2
    return math.ceil(n)


def tasks_per_arm_paired(effect: float, discordant: float = 0.1) -> int:
    """Tasks needed per arm for a paired comparison.

    ``discordant`` is the share of tasks where the two variants disagree. Paired
    designs are cheaper because the agreed tasks cancel; at a discordant share
    of 0.1 and an effect of 0.02 this returns about 1,960, against about 6,280
    for independent samples.
    """
    if not 0 < effect < 1:
        raise ValueError("effect must be between 0 and 1")
    if not 0 < discordant < 1:
        raise ValueError("discordant must be between 0 and 1")
    if effect > discordant:
        raise ValueError("effect cannot exceed the discordant share")

    psi = discordant
    numerator = (Z_ALPHA * math.sqrt(psi) + Z_POWER * math.sqrt(psi - effect**2)) ** 2
    return math.ceil(numerator / effect**2)


def summarise(successes: int, n: int) -> dict[str, float | int]:
    """A report-ready summary of one proportion."""
    low, high = wilson_interval(successes, n)
    return {
        "successes": successes,
        "tasks": n,
        "rate": successes / n if n else 0.0,
        "low": low,
        "high": high,
        "half_width": (high - low) / 2,
    }
