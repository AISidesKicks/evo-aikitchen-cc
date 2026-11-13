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
from evo_bench.tasks import Task
from evo_bench.tools import workspace_tools
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

    @property
    def passed(self) -> bool:
        return self.grade.passed


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

    if mode == "gold":
        if not task.gold:
            raise ValueError(f"task {task.id} has no gold patch")
        apply_gold(workspace, resolve(task.gold))
    elif mode == "agent":
        assert provider is not None
        config = AgentHarnessConfig(
            provider=provider,
            model=model,
            system=SYSTEM_PROMPT,
            tools=workspace_tools(workspace.root),
            max_turns=max_turns or task.budget_turns,
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

    result = await grade(workspace, task.acceptance, timeout=timeout)
    elapsed = time.monotonic() - started

    row = make_row(
        run_id=f"{task.id}-{uuid.uuid4().hex[:8]}",
        date=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        task_id=task.id,
        task_class=task.task_class,
        split=task.split,
        harness=harness,
        harness_version=harness_version,
        model=model,
        provider=type(provider).__name__ if provider is not None else mode,
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
    )
