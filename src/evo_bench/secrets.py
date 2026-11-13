"""Secret hygiene checks.

The rule is simple: a value from a secret-named key in ``.env`` must never appear
in a tracked file or in git history. This module implements that check so it can
run before a commit, rather than being discovered after a push.

Values are never printed. Only counts and file names are reported, because a
checker that echoes the secret is a leak with extra steps.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Keys whose values are secrets. Anything else in .env is configuration and is
# allowed to appear in documentation.
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|PASSWD)", re.IGNORECASE)

# Shorter values produce false positives against ordinary words.
MIN_LENGTH = 8

# Files that are allowed to contain a secret shape, because they are the
# template and the scanner itself.
IGNORED_PATHS = frozenset({".env.example"})


@dataclass(slots=True)
class Report:
    """The outcome of a scan."""

    secrets: int = 0
    tracked_hits: dict[str, list[str]] = field(default_factory=dict)
    history_hits: dict[str, int] = field(default_factory=dict)

    @property
    def clean(self) -> bool:
        return not self.tracked_hits and not self.history_hits


def load_env(path: str | Path = ".env") -> dict[str, str]:
    """Parse a .env file without executing it."""
    target = Path(path)
    values: dict[str, str] = {}
    if not target.is_file():
        return values
    for line in target.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        name, _, value = text.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[name.strip()] = value
    return values


def secret_values(env: dict[str, str]) -> dict[str, str]:
    """Return the entries whose key name looks like a secret."""
    return {
        name: value
        for name, value in env.items()
        if SECRET_NAME.search(name) and len(value) >= MIN_LENGTH
    }


def tracked_files(root: str | Path = ".") -> list[str]:
    """Tracked paths, relative to the repository root."""
    result = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
    )
    return [line for line in result.stdout.splitlines() if line]


def scan_tracked(
    secrets: dict[str, str], root: str | Path = ".", files: list[str] | None = None
) -> dict[str, list[str]]:
    """Map each file that contains a secret to the names of the keys it leaks."""
    base = Path(root)
    hits: dict[str, list[str]] = {}
    for name in files if files is not None else tracked_files(root):
        if name in IGNORED_PATHS:
            continue
        path = base / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        found = [key for key, value in secrets.items() if value in text]
        if found:
            hits[name] = found
    return hits


def scan_history(
    secrets: dict[str, str], root: str | Path = ".", max_commits: int = 500
) -> dict[str, int]:
    """Count commits whose patch contains a secret, without printing the value."""
    if not secrets:
        return {}
    result = subprocess.run(
        ["git", "log", "-p", "--all", f"--max-count={max_commits}"],
        cwd=root,
        capture_output=True,
        text=True,
        errors="ignore",
    )
    counts = dict.fromkeys(secrets, 0)
    for line in result.stdout.splitlines():
        for key, value in secrets.items():
            if value in line:
                counts[key] += 1
    return {key: count for key, count in counts.items() if count}


def check(root: str | Path = ".", env_path: str | Path | None = None) -> Report:
    """Run both scans and return a report."""
    base = Path(root)
    env = load_env(env_path or (base / ".env"))
    secrets = secret_values(env)
    return Report(
        secrets=len(secrets),
        tracked_hits=scan_tracked(secrets, base),
        history_hits=scan_history(secrets, base),
    )
