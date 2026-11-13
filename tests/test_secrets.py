"""Tests for the secret scanner.

The scanner's whole value is that it reports without echoing. These tests use
fake values, and check that configuration values (a model id, a provider name)
are not mistaken for secrets.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from evo_bench.secrets import (
    check,
    load_env,
    scan_history,
    scan_tracked,
    secret_values,
    tracked_files,
)

FAKE_KEY = "sk-or-v1-0000000000000000"


def write_env(path: Path) -> Path:
    path.write_text(
        "# a comment\n"
        "HF_TOKEN=hf_0000000000000000\n"
        'EVO_PROVIDER_KEY="' + FAKE_KEY + '"\n'
        "EVO_PROVIDER=openrouter\n"
        "EVO_MODEL=deepseek/deepseek-v4.1-flash-1017\n"
        "EMPTY=\n",
        encoding="utf-8",
    )
    return path


def git(repo: Path, *args: str) -> None:
    env = {
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "PATH": "/usr/bin:/bin",
    }
    subprocess.run(["git", *args], cwd=repo, check=True, env=env, capture_output=True)


def test_load_env_parses_and_strips_quotes(tmp_path):
    env = load_env(write_env(tmp_path / ".env"))

    assert env["EVO_PROVIDER_KEY"] == FAKE_KEY
    assert env["EVO_PROVIDER"] == "openrouter"
    assert "# a comment" not in env
    assert env["EMPTY"] == ""


def test_secret_values_filter_by_name(tmp_path):
    env = load_env(write_env(tmp_path / ".env"))
    secrets = secret_values(env)

    assert set(secrets) == {"HF_TOKEN", "EVO_PROVIDER_KEY"}
    # A model id is configuration, not a secret.
    assert "EVO_MODEL" not in secrets
    assert "EVO_PROVIDER" not in secrets


def test_short_values_are_ignored():
    assert secret_values({"EVO_PROVIDER_KEY": "short"}) == {}


def test_scan_tracked_finds_a_leak_and_names_the_key(tmp_path):
    (tmp_path / "notes.md").write_text(f"my key is {FAKE_KEY}\n", encoding="utf-8")
    (tmp_path / "clean.md").write_text("nothing here\n", encoding="utf-8")

    hits = scan_tracked(
        {"EVO_PROVIDER_KEY": FAKE_KEY}, tmp_path, files=["notes.md", "clean.md"]
    )

    assert hits == {"notes.md": ["EVO_PROVIDER_KEY"]}


def test_env_example_is_allowed(tmp_path):
    (tmp_path / ".env.example").write_text(f"EVO_PROVIDER_KEY={FAKE_KEY}\n", encoding="utf-8")

    hits = scan_tracked({"EVO_PROVIDER_KEY": FAKE_KEY}, tmp_path, files=[".env.example"])

    assert hits == {}


def test_scan_history_finds_a_committed_leak(tmp_path):
    git(tmp_path, "init")
    (tmp_path / "secret.txt").write_text(f"{FAKE_KEY}\n", encoding="utf-8")
    git(tmp_path, "add", "secret.txt")
    git(tmp_path, "commit", "-m", "oops")

    counts = scan_history({"EVO_PROVIDER_KEY": FAKE_KEY}, tmp_path)

    assert counts["EVO_PROVIDER_KEY"] >= 1


def test_scan_history_is_empty_without_secrets(tmp_path):
    git(tmp_path, "init")
    assert scan_history({}, tmp_path) == {}


def test_tracked_files_lists_the_index(tmp_path):
    git(tmp_path, "init")
    (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
    git(tmp_path, "add", "a.txt")

    assert tracked_files(tmp_path) == ["a.txt"]


def test_check_reports_clean_for_a_repo_without_the_value(tmp_path):
    git(tmp_path, "init")
    (tmp_path / ".env").write_text(f"EVO_PROVIDER_KEY={FAKE_KEY}\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    git(tmp_path, "add", "app.py")
    git(tmp_path, "commit", "-m", "initial")

    report = check(tmp_path)

    assert report.secrets == 1
    assert report.clean


def test_check_reports_a_leak(tmp_path):
    git(tmp_path, "init")
    (tmp_path / ".env").write_text(f"EVO_PROVIDER_KEY={FAKE_KEY}\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(f"KEY = '{FAKE_KEY}'\n", encoding="utf-8")
    git(tmp_path, "add", "app.py")

    report = check(tmp_path)

    assert not report.clean
    assert "app.py" in report.tracked_hits
