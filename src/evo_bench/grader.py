"""Grading: run the acceptance check inside the sandbox.

A task passes when its acceptance command exits zero. That is deliberately
narrow. Partial credit, regression guards and trajectory checks are separate
concerns and belong in the task card, not in the grader.

The grader runs in the sandbox for the same reason the agent's tools do: an
acceptance check is arbitrary code from a task card, and a task card is data.
"""

from __future__ import annotations

from dataclasses import dataclass

from evo_bench.sandbox import Sandbox
from evo_bench.workspace import Workspace


@dataclass(frozen=True, slots=True)
class Grade:
    """The outcome of one acceptance check."""

    score: float
    exit_code: int
    output: str

    @property
    def passed(self) -> bool:
        return self.score >= 1.0


async def grade(
    workspace: Workspace,
    acceptance: str,
    *,
    timeout: float = 300.0,
) -> Grade:
    """Run the acceptance command in the workspace and score it 0 or 1."""
    sandbox = Sandbox(workspace=workspace.root)
    code, output = await sandbox.run(["sh", "-c", acceptance], timeout=timeout)
    return Grade(score=1.0 if code == 0 else 0.0, exit_code=code, output=output)
