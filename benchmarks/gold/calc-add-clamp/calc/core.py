"""Small arithmetic helpers used by the report module."""

from __future__ import annotations


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    return a / b


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def sum_scores(scores: list[float | None]) -> float:
    return sum(scores)


def clamp(value: float, low: float, high: float) -> float:
    if low > high:
        raise ValueError("low must not exceed high")
    return max(low, min(value, high))
