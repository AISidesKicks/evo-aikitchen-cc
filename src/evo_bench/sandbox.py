"""Bubblewrap sandbox for tool execution.

The agent loop runs on the host, because it needs network access to the model
provider. Only tool execution is sandboxed. That split is deliberate and it is
the same one Pi documents: keep the agent on the host, route the tools into an
isolated environment.

Inside the sandbox a tool can see:

- the runtime directories it needs to start, read-only
- the locked pixi environment, read-only, so the same interpreter and packages
  are used as on the host
- the workspace, read-write, because the agent has to edit files
- an empty throwaway ``/tmp`` as ``HOME``

It cannot see ``$HOME``, the network, or any inherited environment variable.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Files that are masked even inside the workspace, because a repository is
# mounted read-only and a secret file in it would otherwise be readable.
MASKED_NAMES = (".env", ".env.local", ".env.production", ".netrc", ".pypirc")

RUNTIME_PATHS = ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc/alternatives", "/etc")


class SandboxUnavailable(RuntimeError):
    """Raised when bubblewrap is not installed or cannot create a namespace."""


@dataclass(frozen=True, slots=True)
class Sandbox:
    """A prepared sandbox around one workspace directory."""

    workspace: Path
    python_prefix: Path = field(default_factory=lambda: Path(sys.prefix))
    masked_names: tuple[str, ...] = MASKED_NAMES
    extra_env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if shutil.which("bwrap") is None:
            raise SandboxUnavailable("bwrap is not installed")

    @property
    def env(self) -> dict[str, str]:
        """The complete environment visible inside the sandbox."""
        env = {
            "PATH": f"{self.python_prefix / 'bin'}:/usr/local/bin:/usr/bin:/bin",
            "HOME": "/tmp",
            "TMPDIR": "/tmp",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "LANG": "C.UTF-8",
        }
        env.update(self.extra_env)
        return env

    def argv(self, command: list[str]) -> list[str]:
        """Build the bubblewrap command line for one command."""
        workspace = self.workspace.resolve()
        args = ["bwrap"]

        for path in RUNTIME_PATHS:
            if Path(path).exists():
                args += ["--ro-bind", path, path]

        # The interpreter and its packages, at the same absolute path so the
        # environment's own sys.path entries stay valid.
        prefix = self.python_prefix.resolve()
        args += ["--ro-bind", str(prefix), str(prefix)]

        args += ["--ro-bind", str(workspace), "/work"]

        for name in self.masked_names:
            if (workspace / name).exists():
                args += ["--ro-bind", "/dev/null", f"/work/{name}"]

        args += [
            "--tmpfs",
            "/tmp",
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            "--tmpfs",
            "/run",
            "--unshare-net",
            "--unshare-pid",
            "--unshare-uts",
            "--unshare-ipc",
            "--die-with-parent",
            "--chdir",
            "/work",
            "--clearenv",
        ]

        for name, value in self.env.items():
            args += ["--setenv", name, value]

        return args + ["--", *command]

    async def run(
        self,
        command: list[str],
        *,
        timeout: float | None = 120.0,
        max_output_bytes: int = 20_000,
    ) -> tuple[int, str]:
        """Run a command inside the sandbox and return exit code and output."""
        process = await asyncio.create_subprocess_exec(
            *self.argv(command),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
            code = process.returncode or 0
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return 124, f"Command timed out after {timeout:g} seconds"

        text = stdout.decode("utf-8", errors="replace")
        if len(text) > max_output_bytes:
            text = text[-max_output_bytes:]
            text = "...output truncated...\n" + text
        return code, text
