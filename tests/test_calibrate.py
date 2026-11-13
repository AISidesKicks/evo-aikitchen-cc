"""Tests for turn-budget calibration."""

from __future__ import annotations

import json
from pathlib import Path

from evo_bench.calibrate import apply, report, summarise


def rows() -> list[dict]:
    return [
        {"task_id": "easy", "turns": 10, "exit_reason": "graded"},
        {"task_id": "easy", "turns": 12, "exit_reason": "graded"},
        {"task_id": "hard", "turns": 40, "exit_reason": "max_turns"},
        {"task_id": "hard", "turns": 38, "exit_reason": "max_turns"},
    ]


def test_summarise_uses_median_for_finished_tasks():
    items = {item.task_id: item for item in summarise(rows())}
    # Median 11 with 1.5 headroom rounds up to 17.
    assert items["easy"].budget == 17


def test_summarise_uses_the_peak_for_capped_tasks():
    items = {item.task_id: item for item in summarise(rows())}
    # A capped task never finished, so its own cap is the floor of what it needs.
    assert items["hard"].capped == 2
    assert items["hard"].budget == 60


def test_headroom_is_configurable():
    items = {item.task_id: item for item in summarise(rows(), headroom=2.0)}
    assert items["easy"].budget == 22


def test_a_floor_prevents_an_absurdly_small_budget():
    items = summarise([{"task_id": "tiny", "turns": 1, "exit_reason": "graded"}], floor=8)
    assert items[0].budget == 8


def test_apply_rewrites_only_the_budget(tmp_path):
    cards = tmp_path / "tasks.jsonl"
    cards.write_text(
        json.dumps({"id": "easy", "prompt": "p", "acceptance": "true", "budget": {"turns": 20, "usd": 0.1}})
        + "\n",
        encoding="utf-8",
    )
    calibrations = summarise([{"task_id": "easy", "turns": 10, "exit_reason": "graded"}])

    changes = apply(cards, calibrations)

    card = json.loads(cards.read_text(encoding="utf-8").strip())
    assert card["budget"]["turns"] == 15
    assert card["budget"]["usd"] == 0.1
    assert changes == {"easy": 15}


def test_apply_dry_run_leaves_the_file_alone(tmp_path):
    cards = tmp_path / "tasks.jsonl"
    original = json.dumps({"id": "easy", "prompt": "p", "acceptance": "true"}) + "\n"
    cards.write_text(original, encoding="utf-8")

    apply(cards, summarise([{"task_id": "easy", "turns": 10, "exit_reason": "graded"}]), dry_run=True)

    assert cards.read_text(encoding="utf-8") == original


def test_report_mentions_the_budget_range():
    text = report(summarise(rows()))
    assert "budget" in text
    assert "17" in text and "60" in text
