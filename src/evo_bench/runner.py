"""Running one task, in one of three modes.

- ``gold`` applies the reference patch and grades it. This is the control that
  proves the task and its acceptance check agree.
- ``null`` changes nothing and grades. This is the control that proves the task
  does not already pass.
- ``agent`` lets the model work, then grades.

All three produce the same ledger row, so a control run and a real run are
directly comparable.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from tau_agent.events import MessageEndEvent, ToolExecutionStartEvent, TurnEndEvent
from tau_agent.harness import AgentHarness, AgentHarnessConfig
from tau_agent.provider import ModelProvider

from evo_bench.grader import Grade, grade
from evo_bench.ledger import make_row
from evo_bench.pricing import PriceBook
from evo_bench.tasks import Task
from evo_bench.tools import workspace_tools
from evo_bench.variants import Variant, compose_system, select_tools
from evo_bench.workspace import Workspace, apply_gold, changed_files, prepare

SYSTEM_PROMPT = """You are working in a small repository at /work.

Make the requested change and verify it with the acceptance command. You have no
network access. Edit the files directly, run the tests, and stop when the
acceptance command passes.

Rules:
- Do not modify the tests.
- Do not add dependencies.
- Keep the change as small as the task allows.
"""


@dataclass(frozen=True, slots=True)
class RunResult:
    """Everything one run produced, including its ledger row."""

    task_id: str
    mode: str
    grade: Grade
    cost: float
    turns: int
    tool_calls: int
    wall_clock: float
    changed: list[str] = field(default_factory=list)
    row: dict = field(default_factory=dict)
    run_id: str = ""
    trace: list[dict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.grade.passed


def write_trace(result: RunResult, directory: str | Path) -> Path:
    """Write the run's messages as JSONL, one message per line.

    A failed run without a trace is a story you cannot check. The ledger says
    what the score was; the trace says what the model actually did.
    """
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{result.run_id or result.task_id}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for message in result.trace:
            handle.write(json.dumps(message, sort_keys=True) + "\n")
    return path


async def run_task(
    task: Task,
    *,
    fixture: str | Path | None = None,
    mode: str = "agent",
    provider: ModelProvider | None = None,
    model: str = "fake",
    harness: str = "tau",
    harness_version: str = "0.4.11",
    workdir: str | Path,
    timeout: float = 300.0,
    max_turns: int | None = None,
    base: str | Path | None = None,
    variant: Variant | None = None,
    variant_name: str = "baseline",
    prices: PriceBook | None = None,
    trial: int = 0,
) -> RunResult:
    """Run one task and grade it."""
    if mode not in {"agent", "gold", "null"}:
        raise ValueError(f"unknown mode: {mode}")
    if mode == "agent" and provider is None:
        raise ValueError("agent mode needs a provider")

    root = Path(base).resolve() if base is not None else Path.cwd().resolve()

    def resolve(value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else root / path

    source = fixture or task.fixture
    if source is None:
        raise ValueError(f"task {task.id} has no fixture")

    workspace: Workspace = prepare(resolve(source), workdir)
    started = time.monotonic()

    cost = 0.0
    turns = 0
    tool_calls = 0
    tokens_in = 0
    tokens_out = 0
    cache_read = 0
    cache_write = 0
    trace: list[dict] = []

    if mode == "gold":
        if not task.gold:
            raise ValueError(f"task {task.id} has no gold patch")
        apply_gold(workspace, resolve(task.gold))
    elif mode == "agent":
        assert provider is not None
        system = compose_system(SYSTEM_PROMPT, variant) if variant else SYSTEM_PROMPT
        tools = workspace_tools(workspace.root)
        if variant is not None:
            tools = select_tools(variant, tools)
        config = AgentHarnessConfig(
            provider=provider,
            model=variant.model if variant and variant.model else model,
            system=system,
            tools=tools,
            max_turns=(variant.max_turns if variant and variant.max_turns else None)
            or max_turns
            or task.budget_turns,
        )
        agent = AgentHarness(config)
        async for event in agent.prompt(task.prompt):
            if isinstance(event, TurnEndEvent):
                turns += 1
            elif isinstance(event, ToolExecutionStartEvent):
                tool_calls += 1
            elif isinstance(event, MessageEndEvent):
                usage = getattr(event.message, "usage", None)
                if usage is not None:
                    cost += float(getattr(usage.cost, "total", 0.0) or 0.0)
                    tokens_in += int(getattr(usage, "input", 0) or 0)
                    tokens_out += int(getattr(usage, "output", 0) or 0)
                    cache_read += int(getattr(usage, "cache_read", 0) or 0)
                    cache_write += int(getattr(usage, "cache_write", 0) or 0)
                trace.append(event.message.model_dump(mode="json"))

    result = await grade(workspace, task.acceptance, timeout=timeout)
    elapsed = time.monotonic() - started

    if prices is not None:
        priced = prices.cost(
            variant.model if variant and variant.model else model,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            cache_read=cache_read,
            cache_write=cache_write,
        )
        if priced is not None:
            cost = priced

    run_id = f"{task.id}-{uuid.uuid4().hex[:8]}"

    row = make_row(
        run_id=run_id,
        date=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        task_id=task.id,
        task_class=task.task_class,
        split=task.split,
        variant=variant_name,
        trial=trial,
        harness=harness,
        harness_version=harness_version,
        model=model,
        provider=type(provider).__name__ if provider is not None else mode,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cache_read=cache_read,
        cache_write=cache_write,
        cost=round(cost, 6),
        wall_clock=round(elapsed, 3),
        turns=turns,
        tool_calls=tool_calls,
        exit_reason="graded",
        score=result.score,
        grader_version="acceptance-v1",
    )

    return RunResult(
        task_id=task.id,
        mode=mode,
        grade=result,
        cost=cost,
        turns=turns,
        tool_calls=tool_calls,
        wall_clock=elapsed,
        changed=changed_files(workspace),
        row=row,
        run_id=run_id,
        trace=trace,
    )
