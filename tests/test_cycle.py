"""Tests for variants and for a full search cycle.

The cycle test uses a provider that changes its behaviour based on the system
prompt, which is exactly what a variant does. That makes the promotion path real
without spending a cent.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import pytest
from tau_agent.messages import AssistantMessage, TextContent, ToolCall
from tau_ai.events import AssistantDoneEvent

from evo_bench.cycle import run_cycle, summary
from evo_bench.gate import Policy
from evo_bench.tasks import Task, load_tasks
from evo_bench.variants import (
    DEFAULT_TOOLS,
    Variant,
    compose_system,
    load_variant,
    load_variants,
    select_tools,
)

ROOT = Path(__file__).resolve().parents[1]
TASKS = {task.id: task for task in load_tasks(ROOT / "benchmarks" / "tasks.jsonl")}


def workdir() -> Path:
    base = os.environ.get("EVO_TMP") or tempfile.gettempdir()
    return Path(tempfile.mkdtemp(prefix="evo-cycle-", dir=base))


def make_corpus(root: Path, count: int) -> list[Task]:
    """Build a tiny corpus where each task writes one number to a file."""
    tasks = []
    for index in range(count):
        fixture = root / f"fixture-{index}"
        (fixture / "tests").mkdir(parents=True)
        (fixture / "tests" / "test_answer.py").write_text(
            "from pathlib import Path\n\n\n"
            "def test_answer() -> None:\n"
            f"    assert Path('answer.txt').read_text().strip() == '{index}'\n",
            encoding="utf-8",
        )
        tasks.append(
            Task(
                id=f"t{index}",
                prompt=f"Write the number {index} into answer.txt.",
                acceptance="python -m pytest -q tests/test_answer.py",
                fixture=str(fixture),
            )
        )
    return tasks


class NumberWriterProvider:
    """Writes answer.txt from the prompt, but only for the marked variant."""

    def __init__(self, marker: str) -> None:
        self.marker = marker
        self.calls = 0

    def stream_response(self, *, model, system, messages, tools, signal=None, session_id=None):
        self.calls += 1
        ran_a_tool = any(
            getattr(message, "role", None) == "toolResult" for message in messages
        )
        prompt = ""
        for message in messages:
            if getattr(message, "role", None) == "user":
                prompt = message.content if isinstance(message.content, str) else prompt

        match = re.search(r"number (\d+)", prompt)
        if self.marker in system and not ran_a_tool and match:
            message = AssistantMessage(
                content=[
                    ToolCall(
                        id="call-1",
                        name="write",
                        arguments={"path": "answer.txt", "content": match.group(1)},
                    )
                ],
                stop_reason="toolUse",
            )
            stream = [AssistantDoneEvent(reason="toolUse", message=message)]
        else:
            message = AssistantMessage(content=[TextContent(text="done")], stop_reason="stop")
            stream = [AssistantDoneEvent(reason="stop", message=message)]

        async def iterator():
            for event in stream:
                yield event

        return iterator()


def test_load_variants_from_the_repository():
    variants = load_variants(ROOT / "benchmarks" / "variants")

    assert {"baseline", "strict", "smallest-diff", "no-bash"} <= set(variants)
    assert variants["strict"].max_turns is None
    assert "acceptance command" in variants["strict"].system_addendum
    assert variants["no-bash"].tools == ("read", "write", "edit")


def test_variant_without_files_is_a_copy_of_the_baseline(tmp_path):
    (tmp_path / "empty").mkdir()
    variant = load_variant(tmp_path / "empty")

    assert variant.name == "empty"
    assert variant.system_addendum == ""
    assert variant.tools == DEFAULT_TOOLS


def test_unknown_tool_is_rejected():
    with pytest.raises(ValueError, match="unknown tools"):
        Variant(name="bad", tools=("read", "telepathy"))


def test_empty_name_is_rejected():
    with pytest.raises(ValueError):
        Variant(name="  ")


def test_compose_system_appends_the_addendum():
    variant = Variant(name="v", system_addendum="Extra rule.")
    composed = compose_system("Base prompt.", variant)

    assert composed.startswith("Base prompt.")
    assert composed.rstrip().endswith("Extra rule.")


def test_compose_system_without_addendum_is_identity():
    assert compose_system("Base.", Variant(name="v")) == "Base."


def test_select_tools_filters_by_name():
    class Tool:
        def __init__(self, name: str) -> None:
            self.name = name

    tools = [Tool("read"), Tool("bash")]
    selected = select_tools(Variant(name="v", tools=("read",)), tools)

    assert [tool.name for tool in selected] == ["read"]


async def test_cycle_promotes_a_variant_that_changes_behaviour(tmp_path):
    tasks = make_corpus(tmp_path, 6)
    provider = NumberWriterProvider(marker="Before you stop")
    ledger = tmp_path / "cycle.jsonl"

    result = await run_cycle(
        tasks,
        baseline=Variant(name="baseline"),
        candidates=[
            Variant(name="strict", system_addendum="Before you stop, run the acceptance command.")
        ],
        provider=provider,
        model="fake",
        ledger=ledger,
        workdir_for=workdir,
        policy=Policy(min_tasks=6),
        base=tmp_path,
    )

    assert len(result.rows) == 12
    assert result.decisions["strict"].verdict == "promote"
    assert result.decisions["strict"].paired.b_only == 6
    assert ledger.exists()

    text = summary(result)
    assert "PROMOTE" in text
    assert "Promoted: strict" in text


async def test_cycle_reports_no_promotion_when_nothing_changes(tmp_path):
    tasks = make_corpus(tmp_path, 6)
    provider = NumberWriterProvider(marker="a marker that never appears")

    result = await run_cycle(
        tasks,
        baseline=Variant(name="baseline"),
        candidates=[Variant(name="strict", system_addendum="Nothing useful.")],
        provider=provider,
        model="fake",
        ledger=tmp_path / "cycle.jsonl",
        workdir_for=workdir,
        policy=Policy(min_tasks=6),
        base=tmp_path,
    )

    assert result.decisions["strict"].verdict == "inconclusive"
    assert "Nothing promoted" in summary(result)


async def test_cycle_stops_at_the_budget_cap(tmp_path):
    tasks = make_corpus(tmp_path, 2)
    provider = NumberWriterProvider(marker="x")

    result = await run_cycle(
        tasks,
        baseline=Variant(name="baseline"),
        candidates=[Variant(name="strict")],
        provider=provider,
        model="fake",
        ledger=tmp_path / "cycle.jsonl",
        workdir_for=workdir,
        policy=Policy(min_tasks=1),
        max_usd=0.0,
        base=tmp_path,
    )

    assert result.aborted
    assert result.rows == []
    assert "cap" in result.aborted_reason


async def test_concurrency_runs_every_job_and_keeps_every_row(tmp_path):
    tasks = make_corpus(tmp_path, 3)
    provider = NumberWriterProvider(marker="Before you stop")

    result = await run_cycle(
        tasks,
        baseline=Variant(name="baseline"),
        candidates=[Variant(name="strict", system_addendum="Before you stop, verify.")],
        provider=provider,
        model="fake",
        ledger=tmp_path / "cycle.jsonl",
        workdir_for=workdir,
        policy=Policy(min_tasks=3),
        base=tmp_path,
        concurrency=3,
    )

    assert len(result.rows) == 6
    assert len(list((tmp_path / "cycle.jsonl").read_text().splitlines())) == 6
    assert result.decisions["strict"].paired.b_only == 3
