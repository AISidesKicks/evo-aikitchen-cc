"""Command line entry point for the bench.

Only one subcommand exists so far: ``status``. It reports the corpus inventory,
the local paths and the Tau version, which is enough to tell whether the
workspace is ready for a run.
"""

from __future__ import annotations

import argparse
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from evo_bench import __version__
from evo_bench.tasks import class_counts, load_tasks

DEFAULT_TASKS = "benchmarks/tasks.jsonl"
EXAMPLE_TASKS = "benchmarks/tasks.example.jsonl"


def _tau_version() -> str:
    try:
        return version("tau-ai")
    except PackageNotFoundError:
        return "not installed"


def _find_corpus(root: Path) -> Path | None:
    for candidate in (root / DEFAULT_TASKS, root / EXAMPLE_TASKS):
        if candidate.exists():
            return candidate
    return None


def status(root: Path) -> int:
    print(f"evo_bench {__version__}")
    print(f"root      {root}")
    print(f"TMPDIR    {os.environ.get('TMPDIR', '-')}")
    print(f"EVO_TMP   {os.environ.get('EVO_TMP', '-')}")
    print(f"SCRATCH   {os.environ.get('SCRATCH', '-')}")
    print(f"tau-ai    {_tau_version()}")

    corpus = _find_corpus(root)
    if corpus is None:
        print("corpus    missing, add benchmarks/tasks.jsonl")
        return 1

    tasks = load_tasks(corpus)
    print(f"corpus    {corpus.relative_to(root)} ({len(tasks)} tasks)")
    for name, count in class_counts(tasks).items():
        print(f"  {name:<20} {count}")

    runs = root / "runs"
    print(f"runs      {runs} {'present' if runs.exists() else 'missing'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evo_bench", description=__doc__)
    parser.add_argument(
        "--root",
        default=Path(os.environ.get("PIXI_PROJECT_ROOT", Path.cwd())),
        type=Path,
        help="project root (default: PIXI_PROJECT_ROOT or the current directory)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="report the bench inventory and local paths")

    args = parser.parse_args(argv)
    if args.command == "status":
        return status(args.root)
    return 2
