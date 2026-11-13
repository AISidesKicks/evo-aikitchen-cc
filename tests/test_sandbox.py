"""Tests for the sandbox command line and the paired comparison."""

from __future__ import annotations

from pathlib import Path

import pytest

from evo_bench.compare import compare, report, trials_per_task
from evo_bench.sandbox import Sandbox, SandboxUnavailable


def test_sandbox_argv_isolates_by_default(tmp_path):
    sandbox = Sandbox(workspace=tmp_path)
    argv = sandbox.argv(["sh", "-c", "true"])

    assert "--unshare-net" in argv
    assert "--clearenv" in argv
    assert "--die-with-parent" in argv
    assert argv[-3:] == ["--", "sh", "-c"] or argv[-1] == "true"
    assert "/work" in argv


def test_sandbox_masks_secret_files(tmp_path):
    (tmp_path / ".env").write_text("HF_TOKEN=value\n", encoding="utf-8")
    sandbox = Sandbox(workspace=tmp_path)
    argv = sandbox.argv(["true"])

    index = argv.index("/dev/null")
    assert argv[index + 1] == "/work/.env"


def test_sandbox_env_has_no_inherited_variables():
    sandbox = Sandbox(workspace=Path("/tmp"))
    env = sandbox.env

    assert env["HOME"] == "/tmp"
    assert env["TMPDIR"] == "/tmp"
    assert "PATH" in env
    assert "EVO_PROVIDER_KEY" not in env


def test_sandbox_reports_a_missing_bwrap(monkeypatch):
    monkeypatch.setattr("evo_bench.sandbox.shutil.which", lambda _: None)
    with pytest.raises(SandboxUnavailable):
        Sandbox(workspace=Path("/tmp"))


def rows(pairs: list[tuple[str, float]], cost: float = 0.5) -> list[dict]:
    return [
        {"task_id": task_id, "score": score, "cost": cost} for task_id, score in pairs
    ]


def test_compare_counts_the_two_by_two():
    a = rows([("t1", 1.0), ("t2", 1.0), ("t3", 0.0), ("t4", 0.0)])
    b = rows([("t1", 1.0), ("t2", 0.0), ("t3", 1.0), ("t4", 0.0)])

    paired = compare(a, b)

    assert paired.both_pass == 1
    assert paired.both_fail == 1
    assert paired.a_only == 1
    assert paired.b_only == 1
    assert paired.tasks == 4
    assert paired.discordant == 2


def test_compare_reports_a_tie_as_noise():
    a = rows([("t1", 1.0), ("t2", 0.0)])
    b = rows([("t1", 0.0), ("t2", 1.0)])

    paired = compare(a, b)

    assert paired.p_value == pytest.approx(1.0)
    assert paired.verdict() == "inside noise"


def test_compare_reports_a_clear_win():
    a = rows([(f"t{i}", 0.0) for i in range(18)])
    b = rows([(f"t{i}", 1.0) for i in range(14)] + [(f"t{i}", 0.0) for i in range(14, 18)])

    paired = compare(a, b)

    assert paired.b_only == 14
    assert paired.p_value < 0.05
    assert paired.verdict() == "B better"


def test_compare_flags_unpaired_tasks():
    paired = compare(rows([("t1", 1.0), ("t2", 1.0)]), rows([("t1", 1.0)]))

    assert paired.tasks == 1
    assert paired.missing == ("t2",)


def test_compare_sums_cost_per_variant():
    paired = compare(rows([("t1", 1.0)], cost=1.5), rows([("t1", 1.0)], cost=2.5))
    assert paired.cost_a == pytest.approx(1.5)
    assert paired.cost_b == pytest.approx(2.5)


def test_report_mentions_the_verdict_and_the_interval():
    paired = compare(rows([("t1", 1.0)]), rows([("t1", 1.0)]))
    text = report(paired)

    assert "mcnemar p" in text
    assert "verdict" in text
    assert "95% CI" in text


def test_compare_aggregates_repeated_trials_as_pass_k():
    """A task only counts when every trial passed."""
    a = [
        {"task_id": "t1", "score": 1.0, "cost": 0.1},
        {"task_id": "t1", "score": 0.0, "cost": 0.1},
        {"task_id": "t2", "score": 1.0, "cost": 0.1},
        {"task_id": "t2", "score": 1.0, "cost": 0.1},
    ]
    b = [
        {"task_id": "t1", "score": 1.0, "cost": 0.1},
        {"task_id": "t1", "score": 1.0, "cost": 0.1},
        {"task_id": "t2", "score": 1.0, "cost": 0.1},
        {"task_id": "t2", "score": 1.0, "cost": 0.1},
    ]

    paired = compare(a, b)

    # t1 is unreliable in A, so A scores 0 on it under pass^2.
    assert paired.tasks == 2
    assert paired.a_only == 0
    assert paired.b_only == 1
    assert paired.cost_a == pytest.approx(0.4)


def test_trials_per_task_counts_per_variant_not_across_variants():
    rows = [
        {"task_id": "t1", "variant": "baseline", "score": 1.0},
        {"task_id": "t1", "variant": "strict", "score": 1.0},
        {"task_id": "t2", "variant": "baseline", "score": 1.0},
    ]
    # Two variants on one task is not two trials.
    assert trials_per_task(rows) == 1


def test_trials_per_task_reports_the_largest_count():
    rows = [
        {"task_id": "t1", "variant": "baseline", "score": 1.0},
        {"task_id": "t1", "variant": "baseline", "score": 1.0},
        {"task_id": "t2", "variant": "baseline", "score": 1.0},
    ]
    assert trials_per_task(rows) == 2
