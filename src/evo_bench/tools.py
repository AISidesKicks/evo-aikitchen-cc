"""Tools the agent gets, all of them bounded by the workspace.

Two rules hold here, and they are the reason this module exists instead of a
straight call to ``tau_coding.create_coding_tools``:

1. **Path containment.** ``read``, ``write`` and ``edit`` refuse any path that
   resolves outside the workspace, so an agent cannot read ``~/.ssh`` or write
   to the host even if a prompt injection asks it to.
2. **Shell isolation.** ``bash`` runs inside bubblewrap with no network, no
   inherited environment and no home directory.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Mapping

from tau_agent.messages import TextContent
from tau_agent.tools import AgentTool, AgentToolResult
from tau_coding.tools import create_edit_tool, create_read_tool, create_write_tool

from evo_bench.sandbox import Sandbox

MAX_OUTPUT_CHARS = 20_000


def _contain(root: Path, value: str) -> str:
    """Resolve a path and reject anything outside the workspace root."""
    candidate = Path(value)
    resolved = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"path escapes the workspace: {value}")
    return str(resolved)


def _guard(root: Path):
    """Return a ``prepare_arguments`` hook that enforces containment."""

    def prepare(arguments: object) -> Mapping[str, Any]:
        if not isinstance(arguments, Mapping):
            raise ValueError("tool arguments must be an object")
        path = arguments.get("path")
        if not isinstance(path, str):
            return arguments
        return {**arguments, "path": _contain(root, path)}

    return prepare


def _bash_tool(root: Path) -> AgentTool:
    sandbox = Sandbox(workspace=root)

    async def execute(
        tool_call_id: str,
        arguments: Mapping[str, Any],
        signal: object = None,
        on_update: object = None,
    ) -> AgentToolResult:
        del tool_call_id, on_update
        command = arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string")
        if signal is not None and getattr(signal, "is_cancelled", lambda: False)():
            raise ValueError("command cancelled")

        timeout = arguments.get("timeout")
        timeout_value = float(timeout) if isinstance(timeout, (int, float)) else 120.0
        code, output = await sandbox.run(["sh", "-c", command], timeout=timeout_value)

        if len(output) > MAX_OUTPUT_CHARS:
            output = "...output truncated...\n" + output[-MAX_OUTPUT_CHARS:]
        if code != 0:
            output = f"{output}\n\nCommand exited with code {code}".strip()

        return AgentToolResult(
            content=[TextContent(text=output or "(no output)")],
            details={"command": command, "exit_code": code},
        )

    return AgentTool(
        name="bash",
        label="bash",
        description=(
            "Execute a shell command in the workspace. Output is truncated to the last "
            f"{MAX_OUTPUT_CHARS} characters. The command runs without network access."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "timeout": {"type": "number", "description": "Timeout in seconds"},
            },
            "required": ["command"],
        },
        execute_fn=execute,
        prompt_snippet="Run shell commands in the workspace",
        prompt_guidelines=("There is no network access. Run the acceptance check to verify work.",),
    )


def workspace_tools(workspace: Path) -> list[AgentTool]:
    """Return read, write, edit and bash, all confined to the workspace."""
    root = Path(workspace).resolve()
    tools = [
        create_read_tool(cwd=root),
        create_write_tool(cwd=root),
        create_edit_tool(cwd=root),
    ]
    guarded = []
    for tool in tools:
        guarded.append(
            AgentTool(
                name=tool.name,
                label=tool.label,
                description=tool.description,
                parameters=tool.parameters,
                execute_fn=tool.execute_fn,
                prompt_snippet=tool.prompt_snippet,
                prompt_guidelines=tool.prompt_guidelines,
                prepare_arguments=_guard(root),
                execution_mode=tool.execution_mode,
            )
        )
    return [*guarded, _bash_tool(root)]


async def run_acceptance(root: Path, command: str, timeout: float = 300.0) -> tuple[int, str]:
    """Run a command in the sandbox, used by tests and ad hoc checks."""
    sandbox = Sandbox(workspace=root)
    return await sandbox.run(["sh", "-c", command], timeout=timeout)


__all__ = ["MAX_OUTPUT_CHARS", "run_acceptance", "workspace_tools"]
