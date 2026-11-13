"""Provider construction.

The bench never invents credentials. It reads them from the process environment,
which nothing in this repository writes to ``.env`` automatically: secrets are
loaded by the caller, so a run can be started with a key that never touches the
repository, the ledger or the sandbox.

Configuration, in order of precedence:

- the argument passed to :func:`build` or :func:`openai_compatible`
- ``EVO_PROVIDER`` for the preset name
- ``EVO_BASE_URL`` for the endpoint
- ``EVO_PROVIDER_KEY`` for the key
- ``EVO_MODEL`` for the model id, read by the CLI
"""

from __future__ import annotations

import os

from tau_agent.provider import ModelProvider
from tau_ai import FakeProvider, OpenAICompatibleConfig, OpenAICompatibleProvider

# Endpoints for providers that speak the OpenAI chat-completions protocol.
# Everything here can be overridden with EVO_BASE_URL, which is what to do when
# a provider moves or you run a gateway in front of one.
PRESETS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "huggingface": "https://router.huggingface.co/v1",
    "together": "https://api.together.xyz/v1",
    "groq": "https://api.groq.com/openai/v1",
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
}

# Presets that do not need an API key because they run on this machine.
KEYLESS = frozenset({"ollama", "lmstudio"})

DEFAULT_PROVIDER = "fake"


class MissingCredentials(RuntimeError):
    """Raised when a real provider is requested without a key."""


class UnknownProvider(ValueError):
    """Raised when the provider name is not a preset."""


def fake_provider(streams: list[list] | None = None) -> FakeProvider:
    """A deterministic provider for tests and dry runs."""
    return FakeProvider(streams or [])


def resolve_base_url(provider: str, base_url: str | None = None) -> str:
    """Return the endpoint for a provider, honouring an explicit override."""
    if base_url:
        return base_url
    from_env = os.environ.get("EVO_BASE_URL")
    if from_env:
        return from_env
    if provider in PRESETS:
        return PRESETS[provider]
    raise UnknownProvider(
        f"unknown provider {provider!r}. Use one of {', '.join(sorted(PRESETS))}, "
        "or set EVO_BASE_URL to any OpenAI-compatible endpoint."
    )


def _attribution_headers() -> dict[str, str]:
    """Optional app attribution, which OpenRouter and some gateways use."""
    headers: dict[str, str] = {}
    name = os.environ.get("EVO_APP_NAME")
    url = os.environ.get("EVO_APP_URL")
    if name:
        headers["X-Title"] = name
    if url:
        headers["HTTP-Referer"] = url
    return headers


def openai_compatible(
    *,
    provider: str = "openai",
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 120.0,
) -> ModelProvider:
    """Build an OpenAI-compatible provider from arguments or the environment."""
    endpoint = resolve_base_url(provider, base_url)
    key = api_key or os.environ.get("EVO_PROVIDER_KEY")
    if not key:
        if provider in KEYLESS:
            key = "not-needed"
        else:
            raise MissingCredentials(
                f"set EVO_PROVIDER_KEY for {provider}, or use --provider fake for a dry run"
            )
    config = OpenAICompatibleConfig(
        api_key=key,
        base_url=endpoint,
        headers=_attribution_headers() or None,
        timeout_seconds=timeout_seconds,
        provider_name=provider,
    )
    return OpenAICompatibleProvider(config)


def build(name: str | None = None) -> ModelProvider:
    """Build the provider named by the argument, or by ``EVO_PROVIDER``."""
    provider = (name or os.environ.get("EVO_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if provider in {"fake", "none", "dry-run"}:
        return fake_provider()
    return openai_compatible(provider=provider)


def model_id(default: str = "fake") -> str:
    """The model id from the environment, or a default."""
    return os.environ.get("EVO_MODEL") or default
