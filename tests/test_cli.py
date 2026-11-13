"""Tests for CLI helpers that encode a policy."""

from __future__ import annotations

from pathlib import Path

from evo_bench.cli import _cache_or_none


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
