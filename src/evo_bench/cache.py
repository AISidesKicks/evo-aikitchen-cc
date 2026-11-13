"""A response cache, so a campaign can be replayed without paying twice.

This is the piece that is harder than it looks. The cache key has to cover
everything that can change the model's answer: the model, the system prompt, the
full message list and the tool definitions. Miss one of those and the replay
silently diverges from the run it claims to reproduce.

Only the final assistant message is stored. Replaying it as a start event plus a
done event is enough for the loop, because the loop treats the finalised message
as authoritative and the streaming events as rendering detail.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from tau_agent.messages import AgentMessage, AssistantMessage
from tau_agent.provider import CancellationToken, ModelProvider
from tau_agent.provider_events import (
    AssistantDoneEvent,
    AssistantMessageEvent,
    AssistantStartEvent,
)
from tau_agent.tools import AgentTool


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True, mode="json")
    if isinstance(value, dict):
        return {key: _dump(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_dump(item) for item in value]
    return value


def cache_key(
    *,
    model: str,
    system: str,
    messages: list[AgentMessage],
    tools: list[AgentTool],
) -> str:
    """Hash every input that can change the model's answer."""
    payload = {
        "model": model,
        "system": system,
        "messages": [_dump(message) for message in messages],
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": _dump(tool.parameters),
            }
            for tool in tools
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ResponseCache:
    """A JSONL store of assistant messages keyed by request hash."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._entries: dict[str, dict[str, Any]] | None = None
        self.hits = 0
        self.misses = 0

    def _load(self) -> dict[str, dict[str, Any]]:
        if self._entries is not None:
            return self._entries
        entries: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            with self.path.open(encoding="utf-8") as handle:
                for line in handle:
                    text = line.strip()
                    if not text:
                        continue
                    row = json.loads(text)
                    entries[row["key"]] = row
        self._entries = entries
        return entries

    def get(self, key: str) -> tuple[AssistantMessage, str] | None:
        row = self._load().get(key)
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        return AssistantMessage.model_validate(row["message"]), row["reason"]

    def put(self, key: str, message: AssistantMessage, reason: str) -> None:
        entries = self._load()
        if key in entries:
            return
        row = {
            "key": key,
            "reason": reason,
            "message": message.model_dump(by_alias=True, mode="json"),
        }
        entries[key] = row
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


class CachingProvider:
    """Wrap a provider and replay stored responses when the request repeats."""

    def __init__(self, inner: ModelProvider, cache: ResponseCache) -> None:
        self.inner = inner
        self.cache = cache

    def stream_response(
        self,
        *,
        model: str,
        system: str,
        messages: list[AgentMessage],
        tools: list[AgentTool],
        signal: CancellationToken | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[AssistantMessageEvent]:
        key = cache_key(model=model, system=system, messages=messages, tools=tools)
        cached = self.cache.get(key)

        async def replay() -> AsyncIterator[AssistantMessageEvent]:
            if cached is not None:
                message, reason = cached
                yield AssistantStartEvent(partial=message)
                yield AssistantDoneEvent(reason=reason, message=message)  # type: ignore[arg-type]
                return

            final: AssistantMessage | None = None
            reason = "stop"
            async for event in self.inner.stream_response(
                model=model,
                system=system,
                messages=messages,
                tools=tools,
                signal=signal,
                session_id=session_id,
            ):
                if isinstance(event, AssistantDoneEvent):
                    final = event.message
                    reason = event.reason
                yield event
            if final is not None:
                self.cache.put(key, final, reason)

        return replay()
