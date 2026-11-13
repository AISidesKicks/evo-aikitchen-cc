"""Tests for the bench statistics.

The two reference values are the ones used in the evaluation guide: an exact
McNemar test on 14 versus 6 discordant tasks gives p = 0.115, and on 18 versus 6
gives p = 0.023. Those two numbers are the difference between a promotion and a
shrug, so they are worth pinning down.
"""

from __future__ import annotations

import pytest

from evo_bench.stats import (
    mcnemar_exact,
    summarise,
    tasks_per_arm,
    tasks_per_arm_paired,
    wilson_interval,
)


def test_wilson_interval_contains_the_point_estimate():
    low, high = wilson_interval(396, 500)
    assert low < 396 / 500 < high


def test_wilson_interval_matches_the_published_shape():
    # 396 of 500 is the SWE-bench Verified tie from the 2026 audit.
    low, high = wilson_interval(396, 500)
    assert low == pytest.approx(0.7543, abs=5e-4)
    assert high == pytest.approx(0.8253, abs=5e-4)


def test_wilson_interval_stays_inside_the_unit_interval():
    low, high = wilson_interval(0, 10)
    assert low == 0.0
    assert 0.0 < high < 0.5

    low, high = wilson_interval(10, 10)
    assert 0.5 < low < 1.0
    assert high == pytest.approx(1.0)


def test_wilson_interval_rejects_impossible_inputs():
    with pytest.raises(ValueError):
        wilson_interval(1, 0)
    with pytest.raises(ValueError):
        wilson_interval(11, 10)


def test_mcnemar_reference_values_from_the_guide():
    assert mcnemar_exact(14, 6) == pytest.approx(0.1153, abs=5e-4)
    assert mcnemar_exact(18, 6) == pytest.approx(0.0227, abs=5e-4)


def test_mcnemar_is_symmetric():
    assert mcnemar_exact(14, 6) == pytest.approx(mcnemar_exact(6, 14))


def test_mcnemar_with_no_discordant_tasks_is_not_significant():
    assert mcnemar_exact(0, 0) == 1.0


def test_mcnemar_rejects_negative_counts():
    with pytest.raises(ValueError):
        mcnemar_exact(-1, 3)


def test_tasks_per_arm_is_about_six_thousand_for_two_points():
    assert 6_000 < tasks_per_arm(0.02, 0.8) < 6_500


def test_paired_tasks_per_arm_is_about_a_third_of_independent():
    paired = tasks_per_arm_paired(0.02, 0.1)
    assert 1_900 <= paired <= 2_000
    assert paired < tasks_per_arm(0.02, 0.8)


def test_tasks_per_arm_shrinks_as_the_effect_grows():
    assert tasks_per_arm(0.10, 0.8) < tasks_per_arm(0.02, 0.8)


def test_summarise_reports_a_half_width():
    summary = summarise(60, 100)
    assert summary["rate"] == pytest.approx(0.6)
    assert summary["half_width"] == pytest.approx((summary["high"] - summary["low"]) / 2)
