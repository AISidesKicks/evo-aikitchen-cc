"""Tests for task card loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evo_bench.tasks import class_counts, load_tasks

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "benchmarks" / "tasks.example.jsonl"


def write_corpus(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def test_example_corpus_loads():
    tasks = load_tasks(EXAMPLE)
    assert len(tasks) == 2
    assert tasks[0].id == "example-bugfix-001"
    assert tasks[0].budget_usd == 2.0
    assert tasks[1].task_class == "feature"


def test_unknown_fields_are_preserved(tmp_path):
    corpus = write_corpus(
        tmp_path / "tasks.jsonl",
        [{"id": "a", "prompt": "p", "acceptance": "true", "owner": "team-x"}],
    )
    task = load_tasks(corpus)[0]
    assert task.extra == {"owner": "team-x"}


def test_missing_required_field_is_rejected(tmp_path):
    corpus = write_corpus(tmp_path / "tasks.jsonl", [{"id": "a", "prompt": "p"}])
    with pytest.raises(ValueError, match="acceptance"):
        load_tasks(corpus)


def test_duplicate_ids_are_rejected(tmp_path):
    corpus = write_corpus(
        tmp_path / "tasks.jsonl",
        [
            {"id": "a", "prompt": "p", "acceptance": "true"},
            {"id": "a", "prompt": "q", "acceptance": "true"},
        ],
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_tasks(corpus)


def test_invalid_json_reports_the_line(tmp_path):
    path = tmp_path / "tasks.jsonl"
    path.write_text(
        '{"id": "a", "prompt": "p", "acceptance": "true"}\nnot json\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=":2:"):
        load_tasks(path)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_tasks(tmp_path / "absent.jsonl")


def test_comments_and_blank_lines_are_skipped(tmp_path):
    path = tmp_path / "tasks.jsonl"
    path.write_text(
        '// a comment\n\n{"id": "a", "prompt": "p", "acceptance": "true"}\n',
        encoding="utf-8",
    )
    assert len(load_tasks(path)) == 1


def test_class_counts_are_sorted():
    class Task:
        def __init__(self, name: str) -> None:
            self.task_class = name

    counts = class_counts([Task("feature"), Task("bugfix"), Task("feature")])
    assert list(counts) == ["bugfix", "feature"]
    assert counts["feature"] == 2
