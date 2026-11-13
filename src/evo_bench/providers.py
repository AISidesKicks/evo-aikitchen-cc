"""Provider construction.

The bench never invents credentials. It reads them from the process environment,
which the pixi activation does not populate from ``.env`` on purpose: secrets are
loaded by the caller, so a run can be started with a key that never touches the
repository or the sandbox.
"""

from __future__ import annotations

import os

from tau_agent.provider import ModelProvider
from tau_ai import FakeProvider, OpenAICompatibleConfig, OpenAICompatibleProvider

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class MissingCredentials(RuntimeError):
    """Raised when a real provider is requested without a key."""


def fake_provider(streams: list[list] | None = None) -> FakeProvider:
    """A deterministic provider for tests and dry runs."""
    return FakeProvider(streams or [])


def openai_compatible(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 120.0,
) -> ModelProvider:
    """Build an OpenAI-compatible provider from arguments or the environment."""
    key = api_key or os.environ.get("EVO_PROVIDER_KEY")
    if not key:
        raise MissingCredentials(
            "set EVO_PROVIDER_KEY in the environment, or use --provider fake for a dry run"
        )
    config = OpenAICompatibleConfig(
        api_key=key,
        base_url=base_url or os.environ.get("EVO_BASE_URL") or DEFAULT_BASE_URL,
        timeout_seconds=timeout_seconds,
    )
    return OpenAICompatibleProvider(config)


def build(name: str) -> ModelProvider:
    """Build a provider by name."""
    if name == "fake":
        return fake_provider()
    if name in {"openai", "openai-compatible"}:
        return openai_compatible()
    raise ValueError(f"unknown provider: {name}")
