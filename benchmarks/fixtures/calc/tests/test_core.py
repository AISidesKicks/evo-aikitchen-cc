"""Acceptance tests for the calc fixture.

These tests describe the intended behaviour. Several of them fail on the
starting code on purpose: each failing test is one bench task.

The two feature tests import inside the function so that a missing function is a
test failure rather than a collection error for the whole module.
"""

from __future__ import annotations

import pytest

from calc.core import add, divide, mean, multiply, subtract, sum_scores


def test_add() -> None:
    assert add(2, 3) == 5


def test_subtract() -> None:
    assert subtract(5, 3) == 2


def test_multiply() -> None:
    assert multiply(4, 3) == 12


def test_divide_by_zero() -> None:
    with pytest.raises(ValueError, match="division by zero"):
        divide(1, 0)


def test_mean_of_empty_list() -> None:
    with pytest.raises(ValueError, match="empty"):
        mean([])


def test_sum_scores_skips_none() -> None:
    assert sum_scores([1.0, None, 3.0]) == 4.0


def test_mod() -> None:
    from calc.core import mod

    assert mod(7, 3) == 1
    assert mod(-7, 3) == 2


def test_clamp() -> None:
    from calc.core import clamp

    assert clamp(5, 0, 10) == 5
    assert clamp(-1, 0, 10) == 0
    assert clamp(11, 0, 10) == 10
    with pytest.raises(ValueError):
        clamp(1, 10, 0)
