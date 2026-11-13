"""Tests for the resolution arithmetic."""

from __future__ import annotations

import pytest

from evo_bench.planning import (
    half_width,
    independent_effect,
    paired_effect,
    report,
    resolution,
    tasks_for,
)


def test_half_width_shrinks_as_tasks_grow():
    assert half_width(500, 0.8) < half_width(50, 0.8)
    assert half_width(5000, 0.8) < half_width(500, 0.8)


def test_half_width_is_about_three_points_at_fifteen_hundred_tasks():
    assert half_width(1537, 0.8) == pytest.approx(0.02, abs=0.001)


def test_independent_effect_needs_tens_of_points_on_a_small_corpus():
    assert independent_effect(12, 0.8) > 0.4


def test_independent_effect_is_seven_points_on_five_hundred_tasks():
    assert independent_effect(500, 0.8) == pytest.approx(0.07, abs=0.005)


def test_paired_effect_cannot_exceed_the_discordant_share():
    # Only tasks the variants disagree on can move the result.
    assert paired_effect(10_000, 0.1) <= 0.1


def test_paired_effect_is_cheaper_than_independent():
    assert paired_effect(200, 0.2) < independent_effect(200, 0.8)


def test_paired_effect_rejects_impossible_inputs():
    with pytest.raises(ValueError):
        paired_effect(0, 0.1)
    with pytest.raises(ValueError):
        paired_effect(10, 0)


def test_resolution_reports_the_expected_discordant_count():
    result = resolution(12, rate=0.8, discordant=0.1)
    assert result.discordant_tasks == pytest.approx(1.2)


def test_tasks_for_matches_the_published_numbers():
    needed = tasks_for(0.02, rate=0.8, discordant=0.1)
    assert needed["independent"] == pytest.approx(6279, abs=5)
    assert needed["paired"] == pytest.approx(1960, abs=5)


def test_tasks_for_shrinks_with_a_larger_effect():
    assert tasks_for(0.10)["independent"] < tasks_for(0.02)["independent"]


def test_tasks_for_rejects_a_zero_effect():
    with pytest.raises(ValueError):
        tasks_for(0.0)


def test_report_warns_about_a_corpus_that_is_too_small():
    text = report(resolution(12))
    assert "too small" in text
    assert "six" in text


def test_report_is_quiet_about_a_large_corpus():
    text = report(resolution(2000))
    assert "too small" not in text

def test_a_twelve_task_corpus_cannot_reach_significance_by_pairing():
    result = resolution(12, rate=0.8, discordant=0.1)
    assert result.paired_achievable is False
    assert "not achievable" in report(result)


def test_a_large_corpus_can_reach_significance_by_pairing():
    assert resolution(2000, rate=0.8, discordant=0.1).paired_achievable is True
