from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.llm.schemas import ConversationUsageByAgent, ConversationUsageSummary, MessageUsage


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError:
            return 0
    return 0


def _sum_optional(current: int | None, value: int | None) -> int | None:
    if current is None and value is None:
        return None
    return (current or 0) + (value or 0)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def normalize_usage(raw_usage: Any) -> MessageUsage | None:
    usage = _mapping(raw_usage)
    if not usage:
        return None

    completion_details = _mapping(
        usage.get("completion_tokens_details")
        or usage.get("output_tokens_details")
        or usage.get("completionTokensDetails")
    )
    prompt_details = _mapping(usage.get("prompt_tokens_details") or usage.get("input_tokens_details"))

    prompt_tokens = _as_int(
        usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or usage.get("promptTokenCount")
        or usage.get("inputTokenCount")
    )
    completion_tokens = _as_int(
        usage.get("completion_tokens")
        or usage.get("output_tokens")
        or usage.get("candidates_token_count")
        or usage.get("candidatesTokenCount")
        or usage.get("outputTokenCount")
    )
    total_tokens = _as_int(
        usage.get("total_tokens")
        or usage.get("totalTokenCount")
        or usage.get("total_token_count")
    )
    reasoning_tokens = _as_int(
        completion_details.get("reasoning_tokens")
        or completion_details.get("reasoningTokens")
        or completion_details.get("reasoning_token_count")
        or usage.get("reasoning_tokens")
        or usage.get("reasoningTokens")
        or prompt_details.get("reasoning_tokens")
    )

    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens
    if prompt_tokens <= 0 and total_tokens > 0 and completion_tokens > 0:
        prompt_tokens = max(total_tokens - completion_tokens, 0)

    if prompt_tokens <= 0 and completion_tokens <= 0 and total_tokens <= 0 and reasoning_tokens <= 0:
        return None

    return MessageUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        reasoning_tokens=reasoning_tokens or None,
        total_tokens=total_tokens,
    )


def normalize_usage_summary(raw_summary: Any) -> ConversationUsageSummary:
    summary = _mapping(raw_summary)
    by_agent_items = summary.get("by_agent") or summary.get("byAgent") or []
    by_agent: list[ConversationUsageByAgent] = []
    if isinstance(by_agent_items, list):
        for item in by_agent_items:
            mapping = _mapping(item)
            agent_id = str(mapping.get("agent_id") or mapping.get("agentId") or "").strip()
            agent_name = str(mapping.get("agent_name") or mapping.get("agentName") or "").strip()
            if not agent_id or not agent_name:
                continue
            by_agent.append(
                ConversationUsageByAgent(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    total_tokens=_as_int(mapping.get("total_tokens") or mapping.get("totalTokens")),
                    total_prompt_tokens=_as_int(
                        mapping.get("total_prompt_tokens") or mapping.get("totalPromptTokens")
                    ),
                    total_completion_tokens=_as_int(
                        mapping.get("total_completion_tokens") or mapping.get("totalCompletionTokens")
                    ),
                    total_reasoning_tokens=(
                        _as_int(mapping.get("total_reasoning_tokens") or mapping.get("totalReasoningTokens"))
                        or None
                    ),
                )
            )
    return ConversationUsageSummary(
        total_tokens=_as_int(summary.get("total_tokens") or summary.get("totalTokens")),
        total_prompt_tokens=_as_int(summary.get("total_prompt_tokens") or summary.get("totalPromptTokens")),
        total_completion_tokens=_as_int(
            summary.get("total_completion_tokens") or summary.get("totalCompletionTokens")
        ),
        total_reasoning_tokens=(
            _as_int(summary.get("total_reasoning_tokens") or summary.get("totalReasoningTokens")) or None
        ),
        by_agent=by_agent,
    )


def usage_to_dict(usage: MessageUsage | None) -> dict[str, Any] | None:
    if usage is None:
        return None
    payload = {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }
    if usage.reasoning_tokens is not None:
        payload["reasoning_tokens"] = usage.reasoning_tokens
    return payload


def usage_summary_to_dict(summary: ConversationUsageSummary | None) -> dict[str, Any]:
    if summary is None:
        return {
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "by_agent": [],
        }
    payload: dict[str, Any] = {
        "total_tokens": summary.total_tokens,
        "total_prompt_tokens": summary.total_prompt_tokens,
        "total_completion_tokens": summary.total_completion_tokens,
        "by_agent": [
            {
                "agent_id": item.agent_id,
                "agent_name": item.agent_name,
                "total_tokens": item.total_tokens,
                "total_prompt_tokens": item.total_prompt_tokens,
                "total_completion_tokens": item.total_completion_tokens,
                **(
                    {"total_reasoning_tokens": item.total_reasoning_tokens}
                    if item.total_reasoning_tokens is not None
                    else {}
                ),
            }
            for item in summary.by_agent
        ],
    }
    if summary.total_reasoning_tokens is not None:
        payload["total_reasoning_tokens"] = summary.total_reasoning_tokens
    return payload


def merge_usage(*items: MessageUsage | None) -> MessageUsage | None:
    merged: MessageUsage | None = None
    for item in items:
        if item is None:
            continue
        if merged is None:
            merged = MessageUsage(
                prompt_tokens=item.prompt_tokens,
                completion_tokens=item.completion_tokens,
                reasoning_tokens=item.reasoning_tokens,
                total_tokens=item.total_tokens,
            )
            continue
        merged.prompt_tokens += item.prompt_tokens
        merged.completion_tokens += item.completion_tokens
        merged.total_tokens += item.total_tokens
        merged.reasoning_tokens = _sum_optional(merged.reasoning_tokens, item.reasoning_tokens)
    return merged


def add_usage_to_summary(
    summary: ConversationUsageSummary | None,
    usage: MessageUsage | None,
    *,
    agent_id: str,
    agent_name: str,
) -> ConversationUsageSummary:
    current = normalize_usage_summary(usage_summary_to_dict(summary))
    if usage is None or not agent_id.strip() or not agent_name.strip():
        return current

    current.total_tokens += usage.total_tokens
    current.total_prompt_tokens += usage.prompt_tokens
    current.total_completion_tokens += usage.completion_tokens
    current.total_reasoning_tokens = _sum_optional(current.total_reasoning_tokens, usage.reasoning_tokens)

    matched = next((item for item in current.by_agent if item.agent_id == agent_id), None)
    if matched is None:
        matched = ConversationUsageByAgent(agent_id=agent_id, agent_name=agent_name)
        current.by_agent.append(matched)
    matched.total_tokens += usage.total_tokens
    matched.total_prompt_tokens += usage.prompt_tokens
    matched.total_completion_tokens += usage.completion_tokens
    matched.total_reasoning_tokens = _sum_optional(matched.total_reasoning_tokens, usage.reasoning_tokens)
    return current


def clone_usage_summary(summary: ConversationUsageSummary | None) -> ConversationUsageSummary:
    return normalize_usage_summary(deepcopy(usage_summary_to_dict(summary)))
