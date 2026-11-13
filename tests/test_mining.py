"""Tests for task mining.

These run against a throwaway git repository, so they test the recipe without
cloning anything: a commit that changes a test and the code it tests becomes one
task, with a gold patch that makes the flipping test pass.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from evo_bench.mining import (
    acceptance_command,
    build_fixture,
    candidates,
    gold_patch,
    mine,
    probe,
    source_root,
)

GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "PATH": "/usr/bin:/bin",
    "HOME": "/tmp",
}


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, env=GIT_ENV
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def make_repo(root: Path) -> Path:
    repo = root / "project"
    repo.mkdir()
    (repo / "src" / "calc").mkdir(parents=True)
    (repo / "tests").mkdir()

    (repo / "src" / "calc" / "__init__.py").write_text(
        "def divide(a, b):\n    return a / b\n", encoding="utf-8"
    )
    (repo / "tests" / "test_calc.py").write_text(
        "from calc import divide\n\n\ndef test_divide():\n    assert divide(6, 3) == 2\n",
        encoding="utf-8",
    )

    git(repo, "init")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial")

    # The task commit: a test that fails until the guard is added.
    (repo / "src" / "calc" / "__init__.py").write_text(
        "def divide(a, b):\n"
        "    if b == 0:\n"
        '        raise ValueError("division by zero")\n'
        "    return a / b\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_calc.py").write_text(
        "import pytest\n\nfrom calc import divide\n\n\n"
        "def test_divide():\n    assert divide(6, 3) == 2\n\n\n"
        "def test_divide_by_zero():\n"
        '    with pytest.raises(ValueError, match="division by zero"):\n'
        "        divide(1, 0)\n",
        encoding="utf-8",
    )
    git(repo, "commit", "-am", "guard against division by zero")
    return repo


def test_source_root_detects_a_src_layout(tmp_path):
    tree = tmp_path / "tree"
    (tree / "src").mkdir(parents=True)
    assert source_root(tree, tree) == tree / "src"


def test_source_root_falls_back_to_the_repository(tmp_path):
    tree = tmp_path / "tree"
    tree.mkdir()
    assert source_root(tree, tree) == tree


def test_candidates_finds_a_test_and_source_pair(tmp_path):
    repo = make_repo(tmp_path)
    found = candidates(repo, scan=10, limit=5)

    assert len(found) == 1
    assert found[0].subject == "guard against division by zero"
    assert "tests/test_calc.py" in found[0].test_files


def test_build_fixture_overlays_the_new_tests(tmp_path):
    repo = make_repo(tmp_path)
    candidate = candidates(repo, scan=10, limit=5)[0]
    fixture = tmp_path / "fixture"
    build_fixture(repo, candidate, fixture)

    tests = (fixture / "tests" / "test_calc.py").read_text(encoding="utf-8")
    source = (fixture / "src" / "calc" / "__init__.py").read_text(encoding="utf-8")

    assert "test_divide_by_zero" in tests
    assert "raise ValueError" not in source


def test_gold_patch_excludes_tests(tmp_path):
    repo = make_repo(tmp_path)
    candidate = candidates(repo, scan=10, limit=5)[0]
    patch = gold_patch(repo, candidate)

    assert "src/calc/__init__.py" in patch
    assert "tests/test_calc.py" not in patch


def test_probe_finds_the_flipping_test(tmp_path):
    repo = make_repo(tmp_path)
    candidate = candidates(repo, scan=10, limit=5)[0]
    work = tmp_path / "work"
    work.mkdir()

    flips, regressions = probe(repo, candidate, work)

    assert flips == ["tests/test_calc.py::test_divide_by_zero"]
    assert regressions == []


def test_acceptance_command_uses_relative_paths(tmp_path):
    fixture = tmp_path / "fixture"
    (fixture / "src").mkdir(parents=True)

    command = acceptance_command(fixture, ["tests/test_calc.py::test_divide_by_zero"])

    assert "PYTHONPATH=src" in command
    assert str(tmp_path) not in command
    assert "test_divide_by_zero" in command


def test_acceptance_command_quotes_awkward_node_ids(tmp_path):
    fixture = tmp_path / "fixture"
    fixture.mkdir()

    command = acceptance_command(fixture, ["tests/test_x.py::test_y[-'--units']"])

    assert "'\"'\"'" in command or "test_y" in command
    # The dangerous part is an unescaped apostrophe ending the quoted token.
    assert "[-'--units']'" not in command


def test_mine_writes_cards_and_a_gold_patch(tmp_path):
    repo = make_repo(tmp_path)
    mined = mine(
        repo,
        out=tmp_path / "mined",
        fixtures=tmp_path / "fixtures",
        limit=1,
        scan=10,
    )

    assert len(mined) == 1
    cards = (tmp_path / "mined" / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(cards) == 1
    assert (tmp_path / "mined" / "gold" / f"{mined[0].id}.patch").exists()


def test_mine_drops_a_commit_whose_gold_does_not_flip(tmp_path):
    repo = make_repo(tmp_path)
    # A commit that touches tests and source but changes no behaviour the tests
    # observe cannot produce a task.
    (repo / "src" / "calc" / "__init__.py").write_text(
        "# a comment only\n"
        "def divide(a, b):\n"
        "    if b == 0:\n"
        '        raise ValueError("division by zero")\n'
        "    return a / b\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_calc.py").write_text(
        "import pytest\n\nfrom calc import divide\n\n\n"
        "def test_divide():\n    assert divide(6, 3) == 2\n\n\n"
        "def test_divide_by_zero():\n"
        '    with pytest.raises(ValueError, match="division by zero"):\n'
        "        divide(1, 0)\n\n\n"
        "def test_unrelated():\n    assert True\n",
        encoding="utf-8",
    )
    git(repo, "commit", "-am", "comment only")

    mined = mine(
        repo,
        out=tmp_path / "mined",
        fixtures=tmp_path / "fixtures",
        limit=5,
        scan=10,
    )

    # The first commit still mines; the no-op commit is dropped.
    assert all("comment only" not in task.candidate.subject for task in mined)
