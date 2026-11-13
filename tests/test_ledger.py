"""Tests for the append-only ledger."""

from __future__ import annotations

import json

import pytest

from evo_bench.ledger import FIELDS, append, make_row, read, totals


def base_row(**overrides):
    values = {
        "run_id": "run-1",
        "task_id": "task-1",
        "harness": "tau",
        "harness_version": "0.4.11",
        "model": "provider/model",
        "cost": 0.42,
        "score": 1.0,
    }
    values.update(overrides)
    return make_row(**values)


def test_make_row_fills_every_field():
    row = base_row()
    assert set(row) == set(FIELDS)
    assert row["turns"] is None


def test_make_row_rejects_unknown_fields():
    with pytest.raises(ValueError, match="unknown ledger fields"):
        make_row(run_id="r", task_id="t", harness="h", harness_version="1", model="m", cost=0, score=0, cust="x")


def test_make_row_rejects_missing_required_fields():
    with pytest.raises(ValueError, match="missing required"):
        make_row(run_id="r", task_id="t")


def test_append_creates_the_file_and_keeps_order(tmp_path):
    path = tmp_path / "nested" / "runs.jsonl"
    append(path, base_row(run_id="a"))
    append(path, base_row(run_id="b", score=0.0))

    rows = list(read(path))
    assert [row["run_id"] for row in rows] == ["a", "b"]


def test_append_never_rewrites_history(tmp_path):
    path = tmp_path / "runs.jsonl"
    append(path, base_row(run_id="a", score=0.0))
    first = path.read_text(encoding="utf-8")

    append(path, base_row(run_id="a", score=1.0, grader_version="2"))
    text = path.read_text(encoding="utf-8")

    assert text.startswith(first)
    assert len(list(read(path))) == 2


def test_totals_counts_cost_and_wins(tmp_path):
    path = tmp_path / "runs.jsonl"
    append(path, base_row(run_id="a", cost=1.0, score=1.0))
    append(path, base_row(run_id="b", cost=3.0, score=0.0))

    summary = totals(path)
    assert summary["runs"] == 2
    assert summary["cost"] == pytest.approx(4.0)
    assert summary["wins"] == 1
    assert summary["cost_per_win"] == pytest.approx(4.0)


def test_totals_of_an_absent_ledger_is_empty(tmp_path):
    summary = totals(tmp_path / "absent.jsonl")
    assert summary["runs"] == 0
    assert summary["wins"] == 0


def test_rows_are_json_objects_on_one_line(tmp_path):
    path = tmp_path / "runs.jsonl"
    append(path, base_row())
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["run_id"] == "run-1"
