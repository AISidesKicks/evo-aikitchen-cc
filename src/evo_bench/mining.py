"""Task mining: turn a repository's history into bench tasks.

A task is a commit where the tests changed and the source changed. The fixture is
the tree at the parent commit with the *new tests* overlaid, so the tests fail
before the change and pass after it. The gold solution is the source half of the
commit.

Three details decide whether the result is usable:

1. **The workspace must shadow installed packages.** ``PYTHONPATH`` points at the
   repository's source root, otherwise ``import click`` resolves to site-packages
   and the agent's edit has no effect. This was the first bug this miner had.
2. **Only flipping tests are graded.** Repositories have pre-existing failures in
   any given environment, so the acceptance command names the node ids that went
   from fail to pass, not whole files.
3. **A task is only kept when the gold passes and the null fails** under the real
   sandbox. Everything else is a task that would grade noise.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

TEST_FILE = re.compile(r"(^|/)test_[^/]*\.py$|(^|/)[^/]*_test\.py$")

# Files pytest treats as its own configuration at the root of a project.
PYTEST_CONFIG = ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini")

NEUTRAL_INI = ".bench/pytest.ini"
NEUTRAL_INI_TEXT = "[pytest]\n"

# Paths that never belong in a gold patch: the tests are the task, docs are not
# the behaviour, and generated files are not reproducible.
GOLD_EXCLUDES = ("tests", "docs", "*.md", "*.rst", "*.txt")


class MiningError(RuntimeError):
    """Raised when the repository cannot be mined at all."""


@dataclass(slots=True)
class Candidate:
    """A commit that might become a task."""

    commit: str
    subject: str
    source_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        words = re.sub(r"[^a-z0-9]+", "-", self.subject.lower()).strip("-")
        return f"{self.commit}-{words[:40].strip('-')}"


@dataclass(slots=True)
class Mined:
    """A validated task."""

    candidate: Candidate
    fixture: Path
    gold: Path
    acceptance: str
    flips: list[str]
    split: str = "train"

    @property
    def id(self) -> str:
        return self.candidate.slug


def _git(repo: Path, *args: str, binary: bool = False):
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True)
    if result.returncode != 0:
        raise MiningError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout if binary else result.stdout.decode("utf-8", errors="replace")


def _changed(repo: Path, commit: str, *paths: str) -> list[str]:
    out = _git(repo, "diff", "--name-only", f"{commit}^", commit, "--", *paths)
    return [line for line in out.splitlines() if line]


def source_root(repo: Path, tree: Path) -> Path | None:
    """Find the import root: ``src`` for a src layout, otherwise the repo root."""
    if (tree / "src").is_dir():
        return tree / "src"
    return tree


def candidates(repo: str | Path, *, scan: int = 400, limit: int = 20) -> list[Candidate]:
    """Scan recent commits for test-and-source pairs."""
    base = Path(repo).resolve()
    if not (base / ".git").exists():
        raise MiningError(f"not a git repository: {base}")

    found: list[Candidate] = []
    for commit in _git(base, "log", "--no-merges", "--format=%h", f"-{scan}").split():
        try:
            source_files = _changed(base, commit, ".")
        except MiningError:
            # A root commit has no parent, so it cannot become a task.
            continue
        tests = [path for path in source_files if TEST_FILE.search(path)]
        code = [
            path
            for path in source_files
            if not path.startswith("tests/")
            and not TEST_FILE.search(path)
            and not path.endswith((".md", ".rst", ".txt"))
        ]
        if not tests or not code:
            continue
        subject = _git(base, "log", "-1", "--format=%s", commit).strip()
        found.append(
            Candidate(commit=commit, subject=subject, source_files=code, test_files=sorted(tests))
        )
        if len(found) >= limit:
            break
    return found


def build_fixture(repo: Path, candidate: Candidate, destination: Path) -> None:
    """Materialise the parent tree, then overlay the tests from the commit."""
    destination = destination.resolve()
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    archive = _git(repo, "archive", f"{candidate.commit}^", binary=True)
    subprocess.run(["tar", "-x", "-C", str(destination)], input=archive, check=True)

    for name in _changed(repo, candidate.commit, "tests"):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_git(repo, "show", f"{candidate.commit}:{name}", binary=True))

    # A fixture with no pytest config of its own would inherit the config of
    # whatever directory it happens to live under, including this repository's
    # pytest.ini. Pin a neutral one so the run depends on the repository being
    # mined and nothing else.
    if not any((destination / name).exists() for name in PYTEST_CONFIG):
        neutral = destination / NEUTRAL_INI
        neutral.parent.mkdir(parents=True, exist_ok=True)
        neutral.write_text(NEUTRAL_INI_TEXT, encoding="utf-8")


def gold_patch(repo: Path, candidate: Candidate) -> str:
    """The source half of the commit, as a patch."""
    args = ["diff", f"{candidate.commit}^", candidate.commit, "--", "."]
    args += [f":(exclude){pattern}" for pattern in GOLD_EXCLUDES]
    return _git(repo, *args)


def _env(fixture: Path) -> dict[str, str]:
    root = source_root(fixture, fixture)
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(fixture.parent),
        "PYTHONPATH": str(root) if root else str(fixture),
        # Third-party pytest plugins from our own environment must not leak into
        # the target repository's suite.
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }


def _node_id(case, fixture: Path, files: list[str]) -> str:
    """Rebuild the pytest node id from a JUnit testcase.

    JUnit reports a dotted classname (``tests.test_mod.TestClass``) and no file
    path. pytest wants a path (``tests/test_mod.py::TestClass::name``). The module
    boundary is found by looking for the longest dotted prefix that names a real
    file, which also handles packages.

    Getting this wrong produces an acceptance command that runs nothing and exits
    4, which looks exactly like a failed task. It cost two mining runs to notice.
    """
    name = case.get("name") or ""
    classname = case.get("classname") or ""
    parts = [part for part in classname.split(".") if part]

    if not parts:
        # A test directory without ``__init__.py`` can report an empty
        # classname. Fall back to the file that defines the function.
        function = name.split("[")[0]
        pattern = re.compile(rf"def {re.escape(function)}\s*\(")
        for relative in files:
            path = fixture / relative
            if path.is_file() and pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                return f"{relative}::{name}"
        return name

    for size in range(len(parts), 0, -1):
        relative = "/".join(parts[:size]) + ".py"
        if (fixture / relative).exists():
            return "::".join([relative, *parts[size:], name])

    # A test directory without an ``__init__.py`` is not a package, so JUnit
    # reports ``test_mod`` with no directory. Find the file by name instead.
    for size in range(len(parts), 0, -1):
        matches = sorted(
            (path for path in fixture.rglob(parts[size - 1] + ".py")),
            key=lambda path: len(path.parts),
        )
        if matches:
            relative = matches[0].relative_to(fixture).as_posix()
            return "::".join([relative, *parts[size:], name])
    return f"{classname}::{name}"


def _outcomes(xml: Path, fixture: Path, files: list[str]) -> dict[str, str]:
    if not xml.exists():
        return {}
    result: dict[str, str] = {}
    for case in ET.parse(xml).getroot().iter("testcase"):
        failed = case.find("failure") is not None or case.find("error") is not None
        result[_node_id(case, fixture, files)] = "fail" if failed else "pass"
    return result


def _config_args(fixture: Path) -> list[str]:
    neutral = fixture / NEUTRAL_INI
    return ["-c", str(neutral.relative_to(fixture))] if neutral.exists() else []


def _run_tests(fixture: Path, files: list[str], xml: Path) -> dict[str, str]:
    """Run test modules and return per-node outcomes."""
    xml.unlink(missing_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *_config_args(fixture),
            "--junit-xml",
            str(xml),
            *files,
        ],
        cwd=fixture,
        env=_env(fixture),
        capture_output=True,
        text=True,
    )
    return _outcomes(xml, fixture, files)


def acceptance_command(fixture: Path, node_ids: list[str]) -> str:
    """The command the grader runs: only the tests that must flip.

    Paths are relative to the workspace, because the grader runs inside the
    sandbox where the workspace is mounted at ``/work``. An absolute host path
    would quietly resolve to nothing and the tests would import site-packages.
    """
    root = source_root(fixture, fixture)
    if root is not None:
        relative = "." if root == fixture else str(root.relative_to(fixture))
        prefix = f"PYTHONPATH={relative} "
    else:
        prefix = ""
    # Node ids can contain quotes, brackets and spaces: pytest parametrisation
    # ids are arbitrary strings. shlex.quote is the only safe way to join them.
    quoted = " ".join(shlex.quote(node) for node in node_ids)
    config = f"-c {NEUTRAL_INI} " if (fixture / NEUTRAL_INI).exists() else ""
    return (
        f"PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 {prefix}python -m pytest -q {config}{quoted}"
    )


def probe(repo: Path, candidate: Candidate, work: Path) -> tuple[list[str], list[str]]:
    """Return the flipping tests and any regressions for one candidate."""
    fixture = work / "fixture"
    build_fixture(repo, candidate, fixture)

    test_files = [path for path in candidate.test_files if TEST_FILE.search(path)]
    if not test_files:
        return [], []

    before = _run_tests(fixture, test_files, work / "before.xml")
    patch = gold_patch(repo, candidate)
    if not patch.strip():
        return [], []
    patch_path = work / "gold.patch"
    patch_path.write_text(patch, encoding="utf-8")
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(fixture.parent)
    applied = subprocess.run(
        ["git", "apply", str(patch_path)],
        cwd=fixture,
        capture_output=True,
        text=True,
        env=env,
    )
    if applied.returncode != 0:
        return [], []

    after = _run_tests(fixture, test_files, work / "after.xml")

    flips = [node for node, state in before.items() if state == "fail" and after.get(node) == "pass"]
    regressions = [
        node for node, state in before.items() if state == "pass" and after.get(node) == "fail"
    ]
    return sorted(flips), sorted(regressions)


def prompt_for(candidate: Candidate) -> str:
    return (
        f"{candidate.subject}.\n\n"
        "The test suite describes the intended behaviour and it currently fails. "
        "Make the tests pass without modifying them. Run the acceptance command to "
        "check your work."
    )


def mine(
    repo: str | Path,
    *,
    out: str | Path,
    fixtures: str | Path,
    limit: int = 20,
    scan: int = 400,
    holdout_every: int = 5,
    work: str | Path | None = None,
) -> list[Mined]:
    """Scan, validate and materialise tasks. Returns the ones that worked."""
    base = Path(repo).resolve()
    out_dir = Path(out).resolve()
    fixture_root = Path(fixtures).resolve()
    scratch = Path(work).resolve() if work else fixture_root / ".work"
    out_dir.mkdir(parents=True, exist_ok=True)
    fixture_root.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)

    # Cards are written as they are mined, not at the end. A long mining run
    # that is interrupted should cost the interrupted task, not the whole corpus.
    cards_path = out_dir / "tasks.jsonl"
    cards_path.parent.mkdir(parents=True, exist_ok=True)
    cards_path.write_text("", encoding="utf-8")

    mined: list[Mined] = []
    for candidate in candidates(base, scan=scan, limit=limit * 3):
        if len(mined) >= limit:
            break
        flips, regressions = probe(base, candidate, scratch)
        if not flips or regressions:
            continue

        target = fixture_root / candidate.slug
        build_fixture(base, candidate, target)
        patch_path = out_dir / "gold" / f"{candidate.slug}.patch"
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        patch_path.write_text(gold_patch(base, candidate), encoding="utf-8")

        split = "holdout" if holdout_every and len(mined) % holdout_every == holdout_every - 1 else "train"
        mined.append(
            Mined(
                candidate=candidate,
                fixture=target,
                gold=patch_path,
                acceptance=acceptance_command(target, flips),
                flips=flips,
                split=split,
            )
        )
        with cards_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_card(mined[-1], Path.cwd())) + "\n")
        print(f"  mined {candidate.commit} flips={len(flips):<3} {candidate.subject[:50]}")
    shutil.rmtree(scratch, ignore_errors=True)
    return mined


def _relative(path: Path, base: Path) -> str:
    """Store paths relative to the mined repository when possible.

    Absolute host paths in a task card make the corpus unusable on another
    machine, and the fixture directory is regenerable anyway.
    """
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return str(path)


def _card(task: Mined, base: Path) -> dict:
    """One task card, with paths relative to the bench repository."""
    return {
        "id": task.id,
        "prompt": prompt_for(task.candidate),
        "acceptance": task.acceptance,
        "class": "bugfix",
        "source": "commit",
        "fixture": _relative(task.fixture, base),
        "gold": _relative(task.gold, base),
        "repo": task.candidate.commit,
        "difficulty": "medium",
        "contamination": "public",
        "split": task.split,
        "partial": "A change that fixes some of the listed tests",
        "notes": f"{len(task.flips)} flipping tests from {task.candidate.subject}",
    }


def _relative(path: Path, base: Path) -> str:
    """Store paths relative to the mined repository when possible.

    Absolute host paths in a task card make the corpus unusable on another
    machine, and the fixture directory is regenerable anyway.
    """
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return str(path)


def _card(task: Mined, base: Path) -> dict:
    """One task card, with paths relative to the bench repository."""
    return {
                "id": task.id,
                "prompt": prompt_for(task.candidate),
                "acceptance": task.acceptance,
                "class": "bugfix",
                "source": "commit",
                "fixture": _relative(task.fixture, base),
                "gold": _relative(task.gold, base),
                "repo": task.candidate.commit,
                "difficulty": "medium",
                "contamination": "public",
                "split": task.split,
                "partial": "A change that fixes some of the listed tests",
        "notes": f"{len(task.flips)} flipping tests from {task.candidate.subject}",
    }
