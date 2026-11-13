"""Tests for CLI helpers that encode a policy."""

from __future__ import annotations

from pathlib import Path

import json

import pytest

from evo_bench.cli import _cache_or_none, _load


def test_one_trial_keeps_the_cache():
    cache = Path("runs/cache.jsonl")
    assert _cache_or_none(cache, 1) == cache


def test_repeated_trials_drop_the_cache(capsys):
    # A replay would return the same answer for every trial and report perfect
    # reliability, which is the opposite of what a trial measures.
    assert _cache_or_none(Path("runs/cache.jsonl"), 3) is None
    assert "disables the response cache" in capsys.readouterr().out


def test_no_cache_stays_none():
    assert _cache_or_none(None, 5) is None


def write_corpus(path, splits):
    rows = [
        {"id": f"t{index}", "prompt": "p", "acceptance": "true", "split": split}
        for index, split in enumerate(splits)
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def test_load_filters_by_split(tmp_path):
    corpus = write_corpus(tmp_path / "tasks.jsonl", ["train", "train", "holdout"])

    assert [task.id for task in _load(tmp_path, corpus, "train")] == ["t0", "t1"]
    assert [task.id for task in _load(tmp_path, corpus, "holdout")] == ["t2"]
    assert len(_load(tmp_path, corpus, "all")) == 3
    assert len(_load(tmp_path, corpus, None)) == 3


def test_load_rejects_an_empty_split(tmp_path):
    corpus = write_corpus(tmp_path / "tasks.jsonl", ["train"])
    with pytest.raises(SystemExit, match="no tasks in split"):
        _load(tmp_path, corpus, "holdout")
