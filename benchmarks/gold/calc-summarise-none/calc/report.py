"""Report formatting helpers."""

from __future__ import annotations

from calc.core import mean, sum_scores


def format_percent(ratio: float) -> str:
    return f"{ratio}%"


def summarise(scores: list[float | None]) -> dict[str, float]:
    present = [score for score in scores if score is not None]
    return {"mean": mean(present), "total": sum_scores(present)}
