"""Tests for provider selection.

Nothing here talks to a network. The point is that the wrong environment either
produces the right client or fails loudly, and that a missing key is an error
rather than a request with an empty Authorization header.
"""

from __future__ import annotations

import pytest
from tau_ai import FakeProvider, OpenAICompatibleProvider

from evo_bench.providers import (
    KEYLESS,
    PRESETS,
    MissingCredentials,
    UnknownProvider,
    _attribution_headers,
    build,
    model_id,
    openai_compatible,
    resolve_base_url,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("EVO_PROVIDER", "EVO_BASE_URL", "EVO_PROVIDER_KEY", "EVO_MODEL", "EVO_APP_NAME", "EVO_APP_URL"):
        monkeypatch.delenv(name, raising=False)


def test_fake_provider_needs_nothing():
    assert isinstance(build("fake"), FakeProvider)


def test_default_provider_is_fake():
    assert isinstance(build(), FakeProvider)


def test_env_selects_the_provider(monkeypatch):
    monkeypatch.setenv("EVO_PROVIDER", "openrouter")
    monkeypatch.setenv("EVO_PROVIDER_KEY", "sk-or-test")

    provider = build()

    assert isinstance(provider, OpenAICompatibleProvider)


def test_openrouter_preset_endpoint():
    assert resolve_base_url("openrouter") == "https://openrouter.ai/api/v1"


def test_explicit_base_url_wins(monkeypatch):
    monkeypatch.setenv("EVO_BASE_URL", "http://gateway.internal/v1")
    assert resolve_base_url("openrouter") == "http://gateway.internal/v1"
    assert resolve_base_url("openrouter", "http://explicit/v1") == "http://explicit/v1"


def test_missing_key_is_an_error():
    with pytest.raises(MissingCredentials, match="EVO_PROVIDER_KEY"):
        openai_compatible(provider="openrouter")


def test_local_presets_need_no_key():
    for name in sorted(KEYLESS):
        provider = openai_compatible(provider=name)
        assert isinstance(provider, OpenAICompatibleProvider)


def test_unknown_provider_lists_the_presets():
    with pytest.raises(UnknownProvider, match="openrouter"):
        resolve_base_url("telepathy")


def test_attribution_headers_are_optional(monkeypatch):
    assert _attribution_headers() == {}

    monkeypatch.setenv("EVO_APP_NAME", "evo-bench")
    monkeypatch.setenv("EVO_APP_URL", "https://evo.aikitchen.cc")
    headers = _attribution_headers()

    assert headers["X-Title"] == "evo-bench"
    assert headers["HTTP-Referer"] == "https://evo.aikitchen.cc"


def test_model_id_reads_the_environment(monkeypatch):
    assert model_id() == "fake"
    monkeypatch.setenv("EVO_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    assert model_id() == "deepseek/deepseek-v4.1-flash-1017"


def test_every_preset_is_an_https_or_local_endpoint():
    for name, url in PRESETS.items():
        assert url.startswith(("https://", "http://localhost")), name
