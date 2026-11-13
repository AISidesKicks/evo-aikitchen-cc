"""Report formatting helpers."""

from __future__ import annotations

from calc.core import mean, sum_scores


def format_percent(ratio: float) -> str:
    return f"{ratio}%"


def summarise(scores: list[float | None]) -> dict[str, float]:
    return {"mean": mean([s for s in scores if s is not None]), "total": sum_scores(scores)}
