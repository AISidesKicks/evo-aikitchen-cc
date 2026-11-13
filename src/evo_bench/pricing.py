"""Model pricing, so the ledger has a real cost column.

Tau reports tokens and deliberately leaves cost unset, because it has no
per-model price table. That is the right call for a harness and the wrong answer
for a ledger: a campaign whose cost is always zero cannot be decided on cost.

Prices are configuration, not code. They live in a TOML file, they carry the date
and the source they were read from, and they can be refreshed because model
prices move.
"""

from __future__ import annotations

import json
import tomllib
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Mapping

USD_PER_MILLION = 1_000_000.0

OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"


@dataclass(frozen=True, slots=True)
class Price:
    """USD per million tokens."""

    input: float
    output: float
    cache_read: float = 0.0
    cache_write: float = 0.0


@dataclass(slots=True)
class PriceBook:
    """A set of prices with the provenance of where they came from."""

    prices: dict[str, Price] = field(default_factory=dict)
    source: str = ""
    read_on: str = ""

    def price_for(self, model: str) -> Price | None:
        return self.prices.get(model)

    def cost(
        self,
        model: str,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> float | None:
        """Cost in USD, or None when the model has no price."""
        price = self.price_for(model)
        if price is None:
            return None
        return (
            input_tokens * price.input
            + output_tokens * price.output
            + cache_read * price.cache_read
            + cache_write * price.cache_write
        ) / USD_PER_MILLION


def load_prices(path: str | Path) -> PriceBook:
    """Load a price book from TOML."""
    target = Path(path)
    if not target.is_file():
        return PriceBook()

    data = tomllib.loads(target.read_text(encoding="utf-8"))
    prices: dict[str, Price] = {}
    for model, values in (data.get("models") or {}).items():
        prices[model] = Price(
            input=float(values.get("input", 0.0)),
            output=float(values.get("output", 0.0)),
            cache_read=float(values.get("cache_read", 0.0)),
            cache_write=float(values.get("cache_write", 0.0)),
        )
    return PriceBook(
        prices=prices,
        source=str(data.get("source", "")),
        read_on=str(data.get("read_on", "")),
    )


def render_prices(book: PriceBook, *, source: str, read_on: str) -> str:
    """Render a price book as TOML, sorted by model id."""
    lines = [
        "# Model prices, in USD per million tokens.",
        f"# Read from {source} on {read_on}.",
        "# Refresh with: python -m evo_bench prices --refresh",
        f'source = "{source}"',
        f'read_on = "{read_on}"',
        "",
    ]
    for model in sorted(book.prices):
        price = book.prices[model]
        lines.append(f'[models."{model}"]')
        lines.append(f"input = {price.input}")
        lines.append(f"output = {price.output}")
        if price.cache_read:
            lines.append(f"cache_read = {price.cache_read}")
        if price.cache_write:
            lines.append(f"cache_write = {price.cache_write}")
        lines.append("")
    return "\n".join(lines)


def fetch_openrouter_prices(
    *, url: str = OPENROUTER_MODELS, timeout: float = 30.0
) -> PriceBook:
    """Read current prices from OpenRouter's public model list.

    OpenRouter quotes USD per token as a string, so the conversion to per-million
    is explicit rather than assumed.
    """
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    prices: dict[str, Price] = {}
    for entry in payload.get("data", []):
        model = entry.get("id")
        pricing = entry.get("pricing") or {}
        if not model or not pricing:
            continue
        try:
            prices[model] = Price(
                input=float(pricing.get("prompt", 0)) * USD_PER_MILLION,
                output=float(pricing.get("completion", 0)) * USD_PER_MILLION,
                cache_read=float(pricing.get("input_cache_read", 0) or 0) * USD_PER_MILLION,
                cache_write=float(pricing.get("input_cache_write", 0) or 0) * USD_PER_MILLION,
            )
        except (TypeError, ValueError):
            continue

    return PriceBook(prices=prices, source=url, read_on=date.today().isoformat())


def write_prices(path: str | Path, book: PriceBook) -> Path:
    """Write a price book to TOML."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_prices(book, source=book.source or "unknown", read_on=book.read_on or "unknown"),
        encoding="utf-8",
    )
    return target


def costs_from_rows(rows: list[Mapping[str, object]]) -> bool:
    """Whether any row carries a non-zero cost."""
    return any(float(row.get("cost") or 0.0) > 0 for row in rows)
