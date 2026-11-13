"""Acceptance tests for report formatting."""

from __future__ import annotations

from calc.report import format_percent, summarise


def test_format_percent() -> None:
    assert format_percent(0.5) == "50.0%"
    assert format_percent(0.125) == "12.5%"


def test_summarise_ignores_missing_scores() -> None:
    summary = summarise([2.0, None, 4.0])
    assert summary["mean"] == 3.0
    assert summary["total"] == 6.0
