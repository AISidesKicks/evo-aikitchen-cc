"""Command line entry point for the bench.

Subcommands:

- ``status`` reports the corpus inventory, the local paths and the Tau version.
- ``control`` runs the gold and null controls over the corpus. Nothing else is
  worth measuring until both pass.
- ``run`` runs the agent over the corpus and appends rows to the ledger.
- ``compare`` runs a paired comparison between two ledger files.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from evo_bench import __version__
from evo_bench.compare import compare, report
from evo_bench.ledger import append, read as read_ledger
from evo_bench.providers import MissingCredentials, build as build_provider
from evo_bench.runner import run_task
from evo_bench.tasks import Task, class_counts, load_tasks

DEFAULT_TASKS = "benchmarks/tasks.jsonl"
EXAMPLE_TASKS = "benchmarks/tasks.example.jsonl"
DEFAULT_LEDGER = "runs/ledger.jsonl"


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


def _load(root: Path) -> list[Task]:
    corpus = _find_corpus(root)
    if corpus is None:
        raise SystemExit(f"no task corpus: add {DEFAULT_TASKS}")
    return load_tasks(corpus)


def _workdir() -> Path:
    base = Path(os.environ.get("EVO_TMP") or tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="evo-run-", dir=base))


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


async def _controls(root: Path, tasks: list[Task], timeout: float) -> int:
    """Gold must pass and null must fail, for every task."""
    failures = 0
    print(f"{'task':<26} {'gold':<6} {'null':<6}")
    for task in tasks:
        gold = await run_task(
            task, mode="gold", workdir=_workdir(), base=root, timeout=timeout
        )
        null = await run_task(
            task, mode="null", workdir=_workdir(), base=root, timeout=timeout
        )
        gold_ok = gold.passed
        null_ok = not null.passed
        if not (gold_ok and null_ok):
            failures += 1
        print(
            f"{task.id:<26} {'pass' if gold_ok else 'FAIL':<6} "
            f"{'pass' if null_ok else 'FAIL':<6}"
        )
        if not gold_ok:
            print(f"  gold exit {gold.grade.exit_code}: {gold.grade.output.strip()[:400]}")
        if null.passed:
            print("  null run passed, so the task already holds")
    print()
    if failures:
        print(f"{failures} task(s) failed their controls. Fix the tasks before measuring.")
        return 1
    print(f"all {len(tasks)} tasks pass their controls")
    return 0


async def _run(
    root: Path,
    tasks: list[Task],
    *,
    provider_name: str,
    model: str,
    ledger: Path,
    timeout: float,
    limit: int | None,
) -> int:
    provider = build_provider(provider_name)
    selected = tasks[:limit] if limit else tasks
    passed = 0
    for task in selected:
        result = await run_task(
            task,
            mode="agent",
            provider=provider,
            model=model,
            workdir=_workdir(),
            base=root,
            timeout=timeout,
        )
        append(ledger, result.row)
        passed += int(result.passed)
        print(
            f"{task.id:<26} {'pass' if result.passed else 'fail':<5} "
            f"turns={result.turns:<3} cost=${result.cost:.4f} {result.wall_clock:.1f}s"
        )
        if not result.passed:
            print(f"  {result.grade.output.strip()[-300:]}")
    print(f"\n{passed}/{len(selected)} passed, ledger {ledger}")
    return 0


def _compare(root: Path, first: Path, second: Path, labels: tuple[str, str]) -> int:
    paired = compare(list(read_ledger(root / first)), list(read_ledger(root / second)))
    print(report(paired, label_a=labels[0], label_b=labels[1]))
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

    control = sub.add_parser("control", help="run the gold and null controls")
    control.add_argument("--timeout", type=float, default=120.0)

    run = sub.add_parser("run", help="run the agent over the corpus")
    run.add_argument("--provider", default="fake", help="fake or openai-compatible")
    run.add_argument("--model", default=os.environ.get("EVO_MODEL", "fake"))
    run.add_argument("--ledger", type=Path, default=Path(DEFAULT_LEDGER))
    run.add_argument("--timeout", type=float, default=300.0)
    run.add_argument("--limit", type=int, default=None)

    compare_cmd = sub.add_parser("compare", help="paired comparison of two ledgers")
    compare_cmd.add_argument("first", type=Path)
    compare_cmd.add_argument("second", type=Path)
    compare_cmd.add_argument("--labels", default="A,B")

    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.command == "status":
        return status(root)
    if args.command == "control":
        return asyncio.run(_controls(root, _load(root), args.timeout))
    if args.command == "run":
        try:
            return asyncio.run(
                _run(
                    root,
                    _load(root),
                    provider_name=args.provider,
                    model=args.model,
                    ledger=args.ledger,
                    timeout=args.timeout,
                    limit=args.limit,
                )
            )
        except MissingCredentials as error:
            print(f"error: {error}")
            return 2
    if args.command == "compare":
        labels = tuple(part.strip() for part in args.labels.split(",", 1))
        return _compare(root, args.first, args.second, (labels[0], labels[-1]))
    return 2
