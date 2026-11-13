"""Tests for the runner, the controls and the sandboxed tool layer.

The agent path is exercised with Tau's ``FakeProvider``, so the whole loop runs
for free: a scripted tool call writes the fix, then a scripted final message ends
the run. No credentials and no network are involved.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from tau_agent.messages import AssistantMessage, TextContent, ToolCall
from tau_ai import FakeProvider
from tau_ai.events import AssistantDoneEvent

from evo_bench.runner import run_task
from evo_bench.tasks import load_tasks
from evo_bench.tools import workspace_tools

ROOT = Path(__file__).resolve().parents[1]
TASKS = {task.id: task for task in load_tasks(ROOT / "benchmarks" / "tasks.jsonl")}


def workdir() -> Path:
    base = os.environ.get("EVO_TMP") or tempfile.gettempdir()
    return Path(tempfile.mkdtemp(prefix="evo-test-", dir=base))


def tool_call_stream(name: str, arguments: dict) -> list:
    message = AssistantMessage(
        content=[ToolCall(id="call-1", name=name, arguments=arguments)],
        stop_reason="toolUse",
    )
    return [AssistantDoneEvent(reason="toolUse", message=message)]


def text_stream(text: str) -> list:
    message = AssistantMessage(content=[TextContent(text=text)], stop_reason="stop")
    return [AssistantDoneEvent(reason="stop", message=message)]


def fixed_core() -> str:
    return (
        '"""Small arithmetic helpers used by the report module."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def add(a: float, b: float) -> float:\n    return a + b\n\n\n"
        "def subtract(a: float, b: float) -> float:\n    return a - b\n\n\n"
        "def multiply(a: float, b: float) -> float:\n    return a * b\n\n\n"
        "def divide(a: float, b: float) -> float:\n"
        '    if b == 0:\n        raise ValueError("division by zero")\n'
        "    return a / b\n\n\n"
        "def mean(values: list[float]) -> float:\n"
        "    return sum(values) / len(values)\n\n\n"
        "def sum_scores(scores: list[float | None]) -> float:\n"
        "    return sum(scores)\n"
    )


async def test_gold_control_passes():
    task = TASKS["calc-divide-zero"]
    result = await run_task(task, mode="gold", workdir=workdir(), base=ROOT)
    assert result.passed
    assert "calc/core.py" in result.changed


async def test_null_control_fails():
    task = TASKS["calc-divide-zero"]
    result = await run_task(task, mode="null", workdir=workdir(), base=ROOT)
    assert not result.passed
    assert result.grade.exit_code != 0
    assert result.changed == []


async def test_agent_run_with_a_scripted_provider():
    task = TASKS["calc-divide-zero"]
    provider = FakeProvider(
        [
            tool_call_stream("write", {"path": "calc/core.py", "content": fixed_core()}),
            text_stream("Fixed the divide guard."),
        ]
    )

    result = await run_task(
        task,
        mode="agent",
        provider=provider,
        model="fake",
        workdir=workdir(),
        base=ROOT,
    )

    assert result.passed, result.grade.output
    assert result.turns >= 1
    assert result.tool_calls == 1
    assert "calc/core.py" in result.changed
    assert result.row["score"] == 1.0
    assert result.row["task_id"] == "calc-divide-zero"
    assert result.row["harness"] == "tau"


async def test_agent_run_without_a_fix_fails():
    task = TASKS["calc-divide-zero"]
    provider = FakeProvider([text_stream("Looks fine to me.")])

    result = await run_task(
        task, mode="agent", provider=provider, model="fake", workdir=workdir(), base=ROOT
    )

    assert not result.passed
    assert result.tool_calls == 0


def test_read_tool_refuses_to_escape_the_workspace(tmp_path):
    tools = {tool.name: tool for tool in workspace_tools(tmp_path)}
    read = tools["read"]
    assert read.prepare_arguments is not None

    with pytest.raises(ValueError, match="escapes the workspace"):
        read.prepare_arguments({"path": "../../etc/passwd"})


def test_write_tool_accepts_an_inner_path(tmp_path):
    tools = {tool.name: tool for tool in workspace_tools(tmp_path)}
    write = tools["write"]
    assert write.prepare_arguments is not None

    prepared = write.prepare_arguments({"path": "calc/core.py", "content": "x"})
    assert prepared["path"] == str((tmp_path / "calc" / "core.py").resolve())


async def test_bash_tool_has_no_network(tmp_path):
    tools = {tool.name: tool for tool in workspace_tools(tmp_path)}
    bash = tools["bash"]

    result = await bash.execute(
        "call-1",
        {"command": "curl -s -m 2 https://pypi.org >/dev/null && echo open || echo closed"},
    )

    assert "closed" in result.text


async def test_bash_tool_cannot_write_outside_the_workspace(tmp_path):
    tools = {tool.name: tool for tool in workspace_tools(tmp_path)}
    bash = tools["bash"]

    result = await bash.execute("call-1", {"command": "touch /work/../escaped.txt"})

    assert result.details["exit_code"] != 0 or not (tmp_path.parent / "escaped.txt").exists()


async def test_a_run_that_hits_the_turn_cap_is_flagged():
    """Truncation must be visible, not silently scored as a plain failure."""
    task = TASKS["calc-divide-zero"]

    class LoopProvider:
        def stream_response(self, *, model, system, messages, tools, signal=None, session_id=None):
            message = AssistantMessage(
                content=[ToolCall(id="c", name="bash", arguments={"command": "true"})],
                stop_reason="toolUse",
            )
            stream = [AssistantDoneEvent(reason="toolUse", message=message)]

            async def iterator():
                for event in stream:
                    yield event

            return iterator()

    result = await run_task(
        task,
        mode="agent",
        provider=LoopProvider(),
        model="fake",
        workdir=workdir(),
        base=ROOT,
        max_turns=3,
    )

    assert result.row["exit_reason"] == "max_turns"
    assert result.turns >= 3


async def test_a_run_that_hits_the_deadline_is_flagged():
    """A wall-clock deadline must stop a run whose turns each look cheap."""
    task = TASKS["calc-divide-zero"]

    class SlowLoopProvider:
        def stream_response(self, *, model, system, messages, tools, signal=None, session_id=None):
            message = AssistantMessage(
                content=[ToolCall(id="c", name="bash", arguments={"command": "sleep 0.2"})],
                stop_reason="toolUse",
            )
            stream = [AssistantDoneEvent(reason="toolUse", message=message)]

            async def iterator():
                for event in stream:
                    yield event

            return iterator()

    result = await run_task(
        task,
        mode="agent",
        provider=SlowLoopProvider(),
        model="fake",
        workdir=workdir(),
        base=ROOT,
        max_turns=50,
        deadline=0.5,
    )

    assert result.row["exit_reason"] == "deadline"
    assert result.wall_clock < 30
