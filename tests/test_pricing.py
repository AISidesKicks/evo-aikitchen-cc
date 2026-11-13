"""Tests for the price book and the trace writer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evo_bench.pricing import (
    Price,
    PriceBook,
    fetch_openrouter_prices,
    load_prices,
    render_prices,
    write_prices,
)
from evo_bench.runner import RunResult, write_trace
from evo_bench.grader import Grade


def test_cost_uses_per_million_tokens():
    book = PriceBook(prices={"m": Price(input=1.0, output=2.0)})
    cost = book.cost("m", input_tokens=1_000_000, output_tokens=1_000_000)

    assert cost == pytest.approx(3.0)


def test_cost_scales_with_small_token_counts():
    book = PriceBook(prices={"m": Price(input=0.5, output=0.5)})
    cost = book.cost("m", input_tokens=10_000, output_tokens=0)

    assert cost == pytest.approx(0.005)


def test_cost_is_none_for_an_unpriced_model():
    assert PriceBook().cost("unknown", input_tokens=10) is None


def test_cache_tokens_are_priced_separately():
    book = PriceBook(prices={"m": Price(input=1.0, output=1.0, cache_read=0.1)})
    cost = book.cost("m", cache_read=1_000_000)

    assert cost == pytest.approx(0.1)


def test_round_trip_through_toml(tmp_path):
    book = PriceBook(
        prices={"a/b": Price(input=0.1, output=0.2, cache_read=0.01)},
        source="test",
        read_on="2026-11-13",
    )
    path = write_prices(tmp_path / "prices.toml", book)
    loaded = load_prices(path)

    assert loaded.prices["a/b"] == Price(input=0.1, output=0.2, cache_read=0.01)
    assert loaded.read_on == "2026-11-13"
    assert loaded.source == "test"


def test_missing_price_file_is_an_empty_book(tmp_path):
    book = load_prices(tmp_path / "absent.toml")
    assert book.prices == {}


def test_render_sorts_models():
    book = PriceBook(prices={"z": Price(1, 1), "a": Price(1, 1)})
    text = render_prices(book, source="s", read_on="d")

    assert text.index('"a"') < text.index('"z"')


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None


def test_fetch_converts_per_token_to_per_million(monkeypatch):
    payload = {
        "data": [
            {
                "id": "vendor/model",
                "pricing": {"prompt": "0.0000005", "completion": "0.000002"},
            },
            {"id": "vendor/free", "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "vendor/broken", "pricing": {"prompt": "not-a-number"}},
        ]
    }
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda request, timeout=0: FakeResponse(payload)
    )

    book = fetch_openrouter_prices()

    assert book.prices["vendor/model"].input == pytest.approx(0.5)
    assert book.prices["vendor/model"].output == pytest.approx(2.0)
    assert "vendor/free" in book.prices
    assert "vendor/broken" not in book.prices
    assert book.read_on


def test_write_trace_creates_one_line_per_message(tmp_path):
    result = RunResult(
        task_id="t1",
        mode="agent",
        grade=Grade(score=1.0, exit_code=0, output=""),
        cost=0.0,
        turns=1,
        tool_calls=0,
        wall_clock=0.1,
        run_id="t1-abc123",
        trace=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": []}],
    )

    path = write_trace(result, tmp_path / "traces")
    lines = path.read_text(encoding="utf-8").splitlines()

    assert path.name == "t1-abc123.jsonl"
    assert len(lines) == 2
    assert json.loads(lines[0])["role"] == "user"
