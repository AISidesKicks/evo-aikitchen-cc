"""Workspace preparation and patch application.

Every run gets a throwaway copy of the task's fixture. The copy is what the
agent edits and what the grader scores, so a run can never damage the source
tree and two runs can never see each other's changes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".git")


@dataclass(frozen=True, slots=True)
class Workspace:
    """A prepared copy of a fixture, ready to be edited."""

    root: Path
    fixture: Path

    def path(self, relative: str = "") -> Path:
        return self.root / relative if relative else self.root


def prepare(fixture: str | Path, destination: str | Path) -> Workspace:
    """Copy a fixture into a fresh workspace directory."""
    source = Path(fixture).resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"no fixture at {source}")

    target = Path(destination).resolve()
    if target.exists():
        if any(target.iterdir()):
            raise FileExistsError(f"workspace is not empty: {target}")
    else:
        target.mkdir(parents=True)

    shutil.copytree(source, target, ignore=IGNORED, dirs_exist_ok=True)
    return Workspace(root=target, fixture=source)


def apply_patch(workspace: Workspace, patch: str | Path) -> None:
    """Apply a unified diff to the workspace with ``git apply``.

    ``git apply`` is used rather than ``patch`` because it is strict about
    context and fails loudly instead of applying a fuzzy hunk in the wrong
    place, which is what a gold control needs.
    """
    patch_path = Path(patch).resolve()
    if not patch_path.is_file():
        raise FileNotFoundError(f"no patch at {patch_path}")

    # A workspace inside another repository would make git discover that outer
    # repository and resolve patch paths against the wrong root. Ceiling the
    # search at the workspace parent keeps ``git apply`` local.
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(workspace.root.parent)

    result = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(patch_path)],
        cwd=workspace.root,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git apply failed: {result.stderr.strip()}")


def apply_gold(workspace: Workspace, gold: str | Path) -> None:
    """Apply a reference solution.

    A directory is copied over the workspace file by file, which is the easy way
    to author a gold control. A ``.patch`` file is applied with ``git apply``,
    which is the honest way to store one once tasks come from real commits.
    """
    source = Path(gold).resolve()
    if source.is_dir():
        for path in sorted(source.rglob("*")):
            if path.is_file():
                target = workspace.root / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
        return
    if source.is_file():
        apply_patch(workspace, source)
        return
    raise FileNotFoundError(f"no gold solution at {source}")


def changed_files(workspace: Workspace) -> list[str]:
    """Return the files that differ from the fixture, sorted."""
    fixture = workspace.fixture
    changed: list[str] = []
    for path in sorted(workspace.root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(workspace.root)
        if any(part in {"__pycache__", ".pytest_cache"} for part in relative.parts):
            continue
        original = fixture / relative
        if not original.is_file() or original.read_bytes() != path.read_bytes():
            changed.append(str(relative))
    return changed
