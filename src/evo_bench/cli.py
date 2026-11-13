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
from evo_bench.cache import CachingProvider, ResponseCache
from evo_bench.compare import compare, report
from evo_bench.cycle import run_cycle, write_summary
from evo_bench.gate import Policy, evaluate, report as gate_report
from evo_bench.ledger import append, read as read_ledger
from evo_bench.mining import mine
from evo_bench.planning import report as plan_report, resolution, tasks_for
from evo_bench.pricing import (
    estimate as build_estimate,
    fetch_openrouter_prices,
    format_estimate,
    load_prices,
    observe_tokens,
    write_prices,
)
from evo_bench.providers import MissingCredentials, build as build_provider
from evo_bench.report import write_report
from evo_bench.runner import run_task, write_trace
from evo_bench.secrets import check as check_secrets
from evo_bench.tasks import Task, class_counts, load_tasks
from evo_bench.variants import Variant, load_variants

DEFAULT_TASKS = "benchmarks/tasks.jsonl"
EXAMPLE_TASKS = "benchmarks/tasks.example.jsonl"
DEFAULT_LEDGER = "runs/ledger.jsonl"
DEFAULT_VARIANTS = "benchmarks/variants"
DEFAULT_PRICES = "benchmarks/prices.toml"
DEFAULT_POLICY = Policy()


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


def _cache_or_none(cache: Path | None, trials: int) -> Path | None:
    """Trials and a response cache do not mix.

    Replaying a stored answer for every trial reports perfect reliability, which
    is the opposite of what a trial is for. When more than one trial is asked
    for, the cache is dropped and the caller is told why.
    """
    if cache is not None and trials > 1:
        print("note: --trials > 1 disables the response cache, replay would fake reliability")
        return None
    return cache


def _load(
    root: Path, corpus: Path | None = None, split: str | None = None
) -> list[Task]:
    """Load a corpus, optionally filtered to one split.

    Campaigns should tune on ``train`` and confirm on ``holdout``. Running every
    task every time spends a fifth of the budget re-measuring tasks that are
    supposed to be untouched.
    """
    path = corpus or _find_corpus(root)
    if path is None:
        raise SystemExit(f"no task corpus: add {DEFAULT_TASKS}")
    tasks = load_tasks(path if path.is_absolute() else root / path)
    if split and split != "all":
        selected = [task for task in tasks if task.split == split]
        if not selected:
            raise SystemExit(f"no tasks in split {split!r} in {path}")
        return selected
    return tasks


def _workdir() -> Path:
    base = Path(os.environ.get("EVO_TMP") or tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="evo-run-", dir=base))


def status(root: Path, corpus_path: Path | None = None) -> int:
    print(f"evo_bench {__version__}")
    print(f"root      {root}")
    print(f"TMPDIR    {os.environ.get('TMPDIR', '-')}")
    print(f"EVO_TMP   {os.environ.get('EVO_TMP', '-')}")
    print(f"SCRATCH   {os.environ.get('SCRATCH', '-')}")
    print(f"tau-ai    {_tau_version()}")
    print(f"provider  {os.environ.get('EVO_PROVIDER', 'fake')}")
    print(f"model     {os.environ.get('EVO_MODEL') or '-'}")

    corpus = corpus_path or _find_corpus(root)
    if corpus is None:
        print("corpus    missing, add benchmarks/tasks.jsonl")
        return 1
    if not corpus.is_absolute():
        corpus = root / corpus

    tasks = load_tasks(corpus)
    print(f"corpus    {corpus.relative_to(root)} ({len(tasks)} tasks)")
    for name, count in class_counts(tasks).items():
        print(f"  {name:<20} {count}")

    splits = {}
    for task in tasks:
        splits[task.split] = splits.get(task.split, 0) + 1
    print(f"splits    {', '.join(f'{name} {count}' for name, count in sorted(splits.items()))}")

    # The resolution rule belongs on the status line, not in a document nobody
    # opens before a campaign.
    item = resolution(len(tasks))
    paired = (
        f"{item.paired_effect:.0%}"
        if item.paired_achievable
        else "not achievable"
    )
    print(
        f"resolves  {item.independent_effect:.0%} independent, {paired} paired "
        f"at {item.rate:.0%}"
    )

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
    cache: Path | None = None,
    variant: Variant | None = None,
    max_usd: float | None = None,
    max_turns: int | None = None,
    trace_dir: Path | None = None,
    prices: Path | None = None,
    trials: int = 1,
) -> int:
    provider = build_provider(provider_name)
    cache = _cache_or_none(cache, trials)
    if cache is not None:
        provider = CachingProvider(provider, ResponseCache(cache))
    book = load_prices(prices) if prices is not None else None
    selected = tasks[:limit] if limit else tasks
    passed = 0
    spend = 0.0
    for task in selected:
        for trial in range(trials):
            if max_usd is not None and spend >= max_usd:
                print(f"stopped: spend {spend:.2f} reached the cap {max_usd:.2f}")
                break

            result = await run_task(
                task,
                mode="agent",
                provider=provider,
                model=model,
                workdir=_workdir(),
                base=root,
                timeout=timeout,
                variant=variant,
                variant_name=variant.name if variant else "baseline",
                max_turns=max_turns,
                prices=book,
                trial=trial,
            )
            if trace_dir is not None:
                write_trace(result, root / trace_dir)
            append(ledger, result.row)
            spend += float(result.row.get("cost") or 0.0)
            passed += int(result.passed)

            label = task.id if trials == 1 else f"{task.id} #{trial + 1}"
            print(
                f"{label:<30} {'pass' if result.passed else 'fail':<5} "
                f"turns={result.turns:<3} cost=${result.cost:.4f} {result.wall_clock:.1f}s"
            )
            if not result.passed:
                print(f"  {result.grade.output.strip()[-300:]}")

    runs = len(selected) * trials
    print(f"\n{passed}/{runs} runs passed, spend ${spend:.4f}, ledger {ledger}")
    return 0


def _compare(root: Path, first: Path, second: Path, labels: tuple[str, str]) -> int:
    paired = compare(list(read_ledger(root / first)), list(read_ledger(root / second)))
    print(report(paired, label_a=labels[0], label_b=labels[1]))
    return 0


def _gate(
    root: Path,
    baseline: Path,
    candidate: Path,
    *,
    policy: Policy,
    labels: tuple[str, str],
    use_holdout: bool,
) -> int:
    decision = evaluate(
        list(read_ledger(root / baseline)),
        list(read_ledger(root / candidate)),
        policy=policy,
        use_holdout=use_holdout,
    )
    print(gate_report(decision, label_a=labels[0], label_b=labels[1]))
    return 0 if decision.promoted else 1


def _prices(out: Path, *, refresh: bool, model: str | None) -> int:
    if not refresh:
        book = load_prices(out)
        if not book.prices:
            print(f"no price book at {out}; run with --refresh to fetch one")
            return 1
        print(f"{len(book.prices)} prices from {out} ({book.source or 'unknown'}, {book.read_on or 'undated'})")
        return 0

    book = fetch_openrouter_prices()
    if model:
        selected = book.prices.get(model)
        if selected is None:
            print(f"model {model!r} is not in the OpenRouter list")
            return 1
        book.prices = {model: selected}
    if not book.prices:
        print("the provider returned no prices")
        return 1
    path = write_prices(out, book)
    print(f"wrote {len(book.prices)} price(s) to {path} from {book.source} on {book.read_on}")
    return 0


def _estimate(
    root: Path,
    *,
    tasks: list[Task],
    candidates: int,
    trials: int,
    model: str,
    prices: Path,
    ledger: Path | None,
) -> int:
    """Estimate a campaign's cost before any money is spent."""
    book = load_prices(root / prices)
    runs = len(tasks) * (candidates + 1) * trials

    rows = []
    if ledger is not None and (root / ledger).exists():
        rows = list(read_ledger(root / ledger))

    # Infer the model rather than demanding an environment variable: a ledger
    # already says which model it ran, and a single-entry price book is
    # unambiguous.
    if not model or model == "unknown":
        if rows:
            model = str(rows[-1].get("model") or "")
        elif len(book.prices) == 1:
            model = next(iter(book.prices))
    if not model:
        print("no model given and none inferable: pass --model")
        return 2

    observed = observe_tokens(rows, model) if rows else None

    if observed is None:
        tokens_in, tokens_out, source = 15_000, 3_000, "assumed"
    else:
        tokens_in, tokens_out = observed
        source = f"observed in {ledger}"

    item = build_estimate(
        book, model, runs=runs, tokens_in=tokens_in, tokens_out=tokens_out, source=source
    )
    print(f"tasks        {len(tasks)} ({candidates + 1} variants x {trials} trials)")
    print(format_estimate(item))
    return 0


def _secrets(root: Path) -> int:
    report = check_secrets(root)
    if report.secrets == 0:
        print("no secret-named values in .env, nothing to check")
        return 0
    print(f"checked {report.secrets} secret value(s) from .env")
    if report.tracked_hits:
        for name, keys in sorted(report.tracked_hits.items()):
            print(f"  LEAK {name}: contains {', '.join(keys)}")
    if report.history_hits:
        for key, count in sorted(report.history_hits.items()):
            print(f"  HISTORY {key}: appears in {count} commit line(s)")
    if report.clean:
        print("clean: no secret value appears in a tracked file or in history")
        return 0
    print("rotate the key, then remove the value from the file and from history")
    return 1


def _report(
    root: Path, ledger: Path, out: Path, *, title: str, baseline: str | None
) -> int:
    rows = list(read_ledger(root / ledger))
    if not rows:
        print(f"no rows in {ledger}")
        return 1
    path = write_report(
        root / out, rows, title=title, baseline=baseline, source=str(ledger)
    )
    print(f"report {path} ({len(rows)} runs)")
    return 0


async def _cycle(
    root: Path,
    tasks: list[Task],
    *,
    variants_dir: Path,
    baseline_name: str,
    candidate_names: list[str],
    provider_name: str,
    model: str,
    ledger: Path,
    summary_path: Path,
    policy: Policy,
    max_usd: float | None,
    timeout: float,
    cache: Path | None,
    max_turns: int | None = None,
    trace_dir: Path | None = None,
    prices: Path | None = None,
    trials: int = 1,
    limit: int | None = None,
) -> int:
    variants = load_variants(root / variants_dir)
    if baseline_name not in variants:
        raise SystemExit(
            f"no baseline variant {baseline_name!r} in {variants_dir} "
            f"(found: {', '.join(sorted(variants)) or 'none'})"
        )
    missing = [name for name in candidate_names if name not in variants]
    if missing:
        raise SystemExit(f"unknown candidates: {', '.join(missing)}")

    provider = build_provider(provider_name)
    cache = _cache_or_none(cache, trials)
    if cache is not None:
        provider = CachingProvider(provider, ResponseCache(cache))
    book = load_prices(prices) if prices is not None else None

    result = await run_cycle(
        tasks[:limit] if limit else tasks,
        baseline=variants[baseline_name],
        candidates=[variants[name] for name in candidate_names],
        provider=provider,
        model=model,
        ledger=root / ledger,
        workdir_for=_workdir,
        policy=policy,
        max_usd=max_usd,
        timeout=timeout,
        base=root,
        max_turns=max_turns,
        trace_dir=trace_dir,
        prices=book,
        trials=trials,
    )

    path = write_summary(result, root / summary_path, baseline=baseline_name)
    print(f"cycle {result.cycle_id}: {len(result.rows)} runs, spend ${result.spend:.4f}")
    if result.aborted:
        print(f"aborted: {result.aborted_reason}")
    for name, decision in result.decisions.items():
        print(f"  {name:<20} {decision.verdict}")
    print(f"summary {path}")
    return 0 if any(d.promoted for d in result.decisions.values()) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evo_bench", description=__doc__)
    parser.add_argument(
        "--root",
        default=Path(os.environ.get("PIXI_PROJECT_ROOT", Path.cwd())),
        type=Path,
        help="project root (default: PIXI_PROJECT_ROOT or the current directory)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    status_cmd = sub.add_parser("status", help="report the bench inventory and local paths")
    status_cmd.add_argument("--tasks", type=Path, default=None, help="corpus file to use")

    control = sub.add_parser("control", help="run the gold and null controls")
    control.add_argument("--timeout", type=float, default=120.0)
    control.add_argument("--tasks", type=Path, default=None, help="corpus file to use")
    control.add_argument("--split", default=None, choices=["train", "holdout", "all"])

    run = sub.add_parser("run", help="run the agent over the corpus")
    run.add_argument(
        "--provider",
        default=os.environ.get("EVO_PROVIDER", "fake"),
        help="fake, openai, openrouter, huggingface, ollama, or any OpenAI-compatible preset",
    )
    run.add_argument("--model", default=os.environ.get("EVO_MODEL", "fake"))
    run.add_argument("--ledger", type=Path, default=Path(DEFAULT_LEDGER))
    run.add_argument("--timeout", type=float, default=300.0)
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--tasks", type=Path, default=None, help="corpus file to use")
    run.add_argument(
        "--split", default=None, choices=["train", "holdout", "all"], help="filter by split"
    )
    run.add_argument("--trials", type=int, default=1, help="repeated runs per task")
    run.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="response cache file, so a campaign can be replayed without paying twice",
    )
    run.add_argument("--variant", default=None, help="variant name from benchmarks/variants")
    run.add_argument("--max-turns", type=int, default=None, help="override the task turn budget")
    run.add_argument(
        "--trace-dir",
        type=Path,
        default=None,
        help="write one JSONL transcript per run to this directory",
    )
    run.add_argument(
        "--prices",
        type=Path,
        default=Path(DEFAULT_PRICES) if Path(DEFAULT_PRICES).exists() else None,
        help="price book used to turn tokens into a cost",
    )
    run.add_argument("--max-usd", type=float, default=None, help="stop before exceeding this spend")

    compare_cmd = sub.add_parser("compare", help="paired comparison of two ledgers")
    compare_cmd.add_argument("first", type=Path)
    compare_cmd.add_argument("second", type=Path)
    compare_cmd.add_argument("--labels", default="A,B")

    gate_cmd = sub.add_parser("gate", help="apply the promotion policy to two ledgers")
    gate_cmd.add_argument("baseline", type=Path)
    gate_cmd.add_argument("candidate", type=Path)
    gate_cmd.add_argument("--labels", default="baseline,candidate")
    gate_cmd.add_argument("--alpha", type=float, default=DEFAULT_POLICY.alpha)
    gate_cmd.add_argument("--min-tasks", type=int, default=DEFAULT_POLICY.min_tasks)
    gate_cmd.add_argument("--min-effect", type=float, default=DEFAULT_POLICY.min_effect)
    gate_cmd.add_argument(
        "--max-cost-increase", type=float, default=DEFAULT_POLICY.max_cost_increase
    )
    gate_cmd.add_argument(
        "--no-holdout", action="store_true", help="ignore the holdout split"
    )

    cycle_cmd = sub.add_parser("cycle", help="run a baseline and candidates, then gate each")
    cycle_cmd.add_argument("--variants-dir", type=Path, default=Path(DEFAULT_VARIANTS))
    cycle_cmd.add_argument("--baseline", default="baseline")
    cycle_cmd.add_argument("--candidates", required=True, help="comma separated variant names")
    cycle_cmd.add_argument("--provider", default=os.environ.get("EVO_PROVIDER", "fake"))
    cycle_cmd.add_argument("--model", default=os.environ.get("EVO_MODEL", "fake"))
    cycle_cmd.add_argument("--ledger", type=Path, default=Path("runs/cycle.jsonl"))
    cycle_cmd.add_argument("--summary", type=Path, default=Path("runs/cycle-summary.md"))
    cycle_cmd.add_argument("--max-usd", type=float, default=None)
    cycle_cmd.add_argument("--timeout", type=float, default=300.0)
    cycle_cmd.add_argument("--cache", type=Path, default=None)
    cycle_cmd.add_argument("--tasks", type=Path, default=None, help="corpus file to use")
    cycle_cmd.add_argument(
        "--split", default=None, choices=["train", "holdout", "all"], help="filter by split"
    )
    cycle_cmd.add_argument("--limit", type=int, default=None, help="use only the first N tasks")
    cycle_cmd.add_argument("--max-turns", type=int, default=None)
    cycle_cmd.add_argument("--trials", type=int, default=1)
    cycle_cmd.add_argument("--trace-dir", type=Path, default=None)
    cycle_cmd.add_argument(
        "--prices",
        type=Path,
        default=Path(DEFAULT_PRICES) if Path(DEFAULT_PRICES).exists() else None,
    )
    cycle_cmd.add_argument("--alpha", type=float, default=DEFAULT_POLICY.alpha)
    cycle_cmd.add_argument("--min-tasks", type=int, default=DEFAULT_POLICY.min_tasks)
    cycle_cmd.add_argument("--min-effect", type=float, default=DEFAULT_POLICY.min_effect)
    cycle_cmd.add_argument(
        "--max-cost-increase", type=float, default=DEFAULT_POLICY.max_cost_increase
    )

    report_cmd = sub.add_parser("report", help="write a self-contained HTML report")
    report_cmd.add_argument("--ledger", type=Path, default=Path(DEFAULT_LEDGER))
    report_cmd.add_argument("--out", type=Path, default=Path("runs/report.html"))
    report_cmd.add_argument("--title", default="EVO bench report")
    report_cmd.add_argument("--baseline", default="baseline")

    sub.add_parser("secrets", help="check that .env secrets are not in tracked files or history")

    plan_cmd = sub.add_parser("plan", help="what this corpus can resolve")
    plan_cmd.add_argument("--tasks", type=Path, default=None, help="count tasks from this corpus")
    plan_cmd.add_argument("--n", type=int, default=None, help="task count to use instead")
    plan_cmd.add_argument("--rate", type=float, default=0.8)
    plan_cmd.add_argument("--discordant", type=float, default=0.1)
    plan_cmd.add_argument("--effect", type=float, default=None, help="also size the corpus")

    estimate_cmd = sub.add_parser("estimate", help="cost a campaign before running it")
    estimate_cmd.add_argument("--tasks", type=Path, default=None)
    estimate_cmd.add_argument("--split", default=None, choices=["train", "holdout", "all"])
    estimate_cmd.add_argument("--candidates", type=int, default=1)
    estimate_cmd.add_argument("--trials", type=int, default=1)
    estimate_cmd.add_argument("--model", default=os.environ.get("EVO_MODEL", ""))
    estimate_cmd.add_argument("--prices", type=Path, default=Path(DEFAULT_PRICES))
    estimate_cmd.add_argument("--ledger", type=Path, default=None)

    mine_cmd = sub.add_parser("mine", help="turn a repository's history into bench tasks")
    mine_cmd.add_argument("--repo", type=Path, required=True)
    mine_cmd.add_argument("--out", type=Path, default=Path("benchmarks/mined"))
    mine_cmd.add_argument("--fixtures", type=Path, default=Path("scratch/mined"))
    mine_cmd.add_argument("--limit", type=int, default=20)
    mine_cmd.add_argument("--scan", type=int, default=400)
    mine_cmd.add_argument("--holdout-every", type=int, default=5)

    prices_cmd = sub.add_parser("prices", help="read or refresh the model price book")
    prices_cmd.add_argument("--out", type=Path, default=Path(DEFAULT_PRICES))
    prices_cmd.add_argument("--refresh", action="store_true", help="fetch from OpenRouter")
    prices_cmd.add_argument("--model", default=os.environ.get("EVO_MODEL"))

    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.command == "status":
        return status(root, args.tasks)
    if args.command == "control":
        return asyncio.run(
            _controls(root, _load(root, args.tasks, args.split), args.timeout)
        )
    if args.command == "run":
        try:
            variant = None
            if args.variant:
                variant = load_variants(root / DEFAULT_VARIANTS).get(args.variant)
                if variant is None:
                    print(f"error: no variant {args.variant!r} in {DEFAULT_VARIANTS}")
                    return 2
            return asyncio.run(
                _run(
                    root,
                    _load(root, args.tasks, args.split),
                    provider_name=args.provider,
                    model=args.model,
                    ledger=args.ledger,
                    timeout=args.timeout,
                    limit=args.limit,
                    cache=args.cache,
                    variant=variant,
                    max_usd=args.max_usd,
                    max_turns=args.max_turns,
                    trace_dir=args.trace_dir,
                    prices=args.prices,
                    trials=args.trials,
                )
            )
        except MissingCredentials as error:
            print(f"error: {error}")
            return 2
    if args.command == "compare":
        labels = tuple(part.strip() for part in args.labels.split(",", 1))
        return _compare(root, args.first, args.second, (labels[0], labels[-1]))
    if args.command == "report":
        return _report(
            root,
            args.ledger,
            args.out,
            title=args.title,
            baseline=args.baseline or None,
        )
    if args.command == "secrets":
        return _secrets(root)
    if args.command == "prices":
        return _prices(root / args.out, refresh=args.refresh, model=args.model)
    if args.command == "plan":
        count = args.n
        if count is None:
            tasks = _load(root, args.tasks)
            count = len(tasks)
        result = resolution(count, rate=args.rate, discordant=args.discordant)
        print(plan_report(result))
        if args.effect is not None:
            needed = tasks_for(args.effect, rate=args.rate, discordant=args.discordant)
            print()
            print(f"to resolve {args.effect:.0%}: {needed['independent']} tasks independent, "
                  f"{needed['paired']} paired")
        return 0
    if args.command == "estimate":
        return _estimate(
            root,
            tasks=_load(root, args.tasks, args.split),
            candidates=args.candidates,
            trials=args.trials,
            model=args.model or "unknown",
            prices=args.prices,
            ledger=args.ledger,
        )
    if args.command == "mine":
        mined = mine(
            args.repo,
            out=args.out,
            fixtures=args.fixtures,
            limit=args.limit,
            scan=args.scan,
            holdout_every=args.holdout_every,
        )
        print(f"\n{len(mined)} task(s) written to {args.out / 'tasks.jsonl'}")
        return 0 if mined else 1
    if args.command == "gate":
        labels = tuple(part.strip() for part in args.labels.split(",", 1))
        policy = Policy(
            alpha=args.alpha,
            min_tasks=args.min_tasks,
            min_effect=args.min_effect,
            max_cost_increase=args.max_cost_increase,
        )
        return _gate(
            root,
            args.baseline,
            args.candidate,
            policy=policy,
            labels=(labels[0], labels[-1]),
            use_holdout=not args.no_holdout,
        )
    if args.command == "cycle":
        policy = Policy(
            alpha=args.alpha,
            min_tasks=args.min_tasks,
            min_effect=args.min_effect,
            max_cost_increase=args.max_cost_increase,
        )
        names = [name.strip() for name in args.candidates.split(",") if name.strip()]
        try:
            return asyncio.run(
                _cycle(
                    root,
                    _load(root, args.tasks, args.split),
                    variants_dir=args.variants_dir,
                    baseline_name=args.baseline,
                    candidate_names=names,
                    provider_name=args.provider,
                    model=args.model,
                    ledger=args.ledger,
                    summary_path=args.summary,
                    policy=policy,
                    max_usd=args.max_usd,
                    timeout=args.timeout,
                    cache=args.cache,
                    max_turns=args.max_turns,
                    trace_dir=(root / args.trace_dir) if args.trace_dir else None,
                    prices=args.prices,
                    trials=args.trials,
                    limit=args.limit,
                )
            )
        except MissingCredentials as error:
            print(f"error: {error}")
            return 2
    return 2
