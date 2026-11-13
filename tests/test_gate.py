"""Tests for the promotion gate and the response cache.

The gate tests are the important ones: each case is a decision a team will
actually face, and the expected verdict is the one the evaluation guide argues
for.
"""

from __future__ import annotations

import pytest
from tau_agent.messages import AssistantMessage, TextContent, ToolCall
from tau_ai import FakeProvider
from tau_ai.events import AssistantDoneEvent

from evo_bench.cache import CachingProvider, ResponseCache, cache_key
from evo_bench.gate import (
    INCONCLUSIVE,
    PROMOTE,
    REJECT,
    Policy,
    evaluate,
    report,
)


def rows(scores: dict[str, float], *, split: str = "train", cost: float = 1.0) -> list[dict]:
    return [
        {"task_id": task_id, "score": score, "cost": cost, "split": split}
        for task_id, score in scores.items()
    ]


def baseline_and_candidate(
    *, both_pass: int, both_fail: int, a_only: int, b_only: int, split: str = "train"
) -> tuple[list[dict], list[dict]]:
    a: dict[str, float] = {}
    b: dict[str, float] = {}
    index = 0
    for _ in range(both_pass):
        a[f"t{index}"] = 1.0
        b[f"t{index}"] = 1.0
        index += 1
    for _ in range(both_fail):
        a[f"t{index}"] = 0.0
        b[f"t{index}"] = 0.0
        index += 1
    for _ in range(a_only):
        a[f"t{index}"] = 1.0
        b[f"t{index}"] = 0.0
        index += 1
    for _ in range(b_only):
        a[f"t{index}"] = 0.0
        b[f"t{index}"] = 1.0
        index += 1
    return rows(a, split=split), rows(b, split=split)


def test_too_few_tasks_is_inconclusive():
    a, b = baseline_and_candidate(both_pass=1, both_fail=0, a_only=0, b_only=6)
    decision = evaluate(a, b, policy=Policy(min_tasks=20))

    assert decision.verdict == INCONCLUSIVE
    assert "needs 20" in decision.reasons[0]


def test_a_clear_win_is_promoted():
    a, b = baseline_and_candidate(both_pass=10, both_fail=10, a_only=2, b_only=18)
    decision = evaluate(a, b, policy=Policy(min_tasks=20))

    assert decision.verdict == PROMOTE
    assert decision.paired.b_only == 18
    assert decision.paired.p_value < 0.05


def test_a_small_difference_is_inside_noise():
    a, b = baseline_and_candidate(both_pass=10, both_fail=10, a_only=9, b_only=11)
    decision = evaluate(a, b, policy=Policy(min_tasks=20))

    assert decision.verdict == INCONCLUSIVE
    assert "inside noise" in " ".join(decision.reasons)


def test_a_significant_regression_is_rejected():
    a, b = baseline_and_candidate(both_pass=10, both_fail=10, a_only=18, b_only=2)
    decision = evaluate(a, b, policy=Policy(min_tasks=20))

    assert decision.verdict == REJECT
    assert "worse" in decision.reasons[0]


def test_identical_variants_are_inconclusive():
    a, b = baseline_and_candidate(both_pass=20, both_fail=10, a_only=0, b_only=0)
    decision = evaluate(a, b, policy=Policy(min_tasks=20))

    assert decision.verdict == INCONCLUSIVE
    assert "agree on every task" in decision.reasons[0]


def test_a_cost_blowout_is_rejected():
    a, b = baseline_and_candidate(both_pass=10, both_fail=10, a_only=2, b_only=18)
    for row in a:
        row["cost"] = 1.0
    for row in b:
        row["cost"] = 5.0

    decision = evaluate(a, b, policy=Policy(min_tasks=20, max_cost_increase=0.20))

    assert decision.verdict == REJECT
    assert "cost per success" in " ".join(decision.reasons)


def test_a_holdout_regression_blocks_promotion():
    a, b = baseline_and_candidate(both_pass=10, both_fail=10, a_only=2, b_only=18)
    hold_a, hold_b = baseline_and_candidate(both_pass=0, both_fail=0, a_only=6, b_only=0, split="holdout")

    decision = evaluate(a + hold_a, b + hold_b, policy=Policy(min_tasks=20))

    assert decision.verdict == REJECT
    assert "holdout regressed" in " ".join(decision.reasons)


def test_the_holdout_can_be_ignored():
    a, b = baseline_and_candidate(both_pass=10, both_fail=10, a_only=2, b_only=18)
    hold_a, hold_b = baseline_and_candidate(both_pass=0, both_fail=0, a_only=6, b_only=0, split="holdout")

    decision = evaluate(a + hold_a, b + hold_b, policy=Policy(min_tasks=20), use_holdout=False)

    assert decision.verdict == PROMOTE


def test_min_effect_blocks_a_technically_significant_win():
    a, b = baseline_and_candidate(both_pass=200, both_fail=200, a_only=10, b_only=25)
    decision = evaluate(a, b, policy=Policy(min_tasks=20, min_effect=0.10))

    assert decision.verdict == INCONCLUSIVE
    assert "minimum effect" in " ".join(decision.reasons)


def test_policy_rejects_impossible_values():
    with pytest.raises(ValueError):
        Policy(alpha=0)
    with pytest.raises(ValueError):
        Policy(min_tasks=0)


def test_cost_ratio_is_not_defined_when_nothing_passed():
    a, b = baseline_and_candidate(both_pass=0, both_fail=10, a_only=0, b_only=18)
    decision = evaluate(a, b, policy=Policy(min_tasks=20))

    # A baseline with no successes has no cost per success. The gate must not
    # reject on an undefined ratio.
    assert decision.verdict == PROMOTE
    assert decision.cost_ratio == 1.0
    assert "not comparable" in " ".join(decision.reasons)


def test_report_mentions_the_verdict_and_the_reasons():
    a, b = baseline_and_candidate(both_pass=10, both_fail=10, a_only=2, b_only=18)
    text = report(evaluate(a, b, policy=Policy(min_tasks=20)))

    assert "PROMOTE" in text
    assert "reasons:" in text
    assert "mcnemar p" in text


def stream(text: str) -> list:
    message = AssistantMessage(content=[TextContent(text=text)], stop_reason="stop")
    return [AssistantDoneEvent(reason="stop", message=message)]


def test_cache_replays_without_calling_the_provider(tmp_path):
    cache = ResponseCache(tmp_path / "cache.jsonl")
    inner = FakeProvider([stream("first answer")])
    provider = CachingProvider(inner, cache)

    async def run_once():
        events = []
        async for event in provider.stream_response(
            model="m", system="s", messages=[], tools=[]
        ):
            events.append(event)
        return events

    import asyncio

    asyncio.run(run_once())
    asyncio.run(run_once())

    assert len(inner.calls) == 1
    assert cache.hits == 1
    assert cache.misses == 1


def test_cache_key_covers_system_prompt_messages_and_tools(tmp_path):
    base = dict(model="m", system="s", messages=[], tools=[])
    key = cache_key(**base)

    assert cache_key(**{**base, "system": "other"}) != key
    assert cache_key(**{**base, "model": "other"}) != key
    assert cache_key(**{**base, "messages": [AssistantMessage(content=[TextContent(text="x")])]}) != key


def test_cache_persists_across_instances(tmp_path):
    path = tmp_path / "cache.jsonl"
    first = ResponseCache(path)
    first.put("key", AssistantMessage(content=[TextContent(text="stored")]), "stop")

    second = ResponseCache(path)
    hit = second.get("key")

    assert hit is not None
    assert hit[0].content[0].text == "stored"
    assert hit[1] == "stop"
