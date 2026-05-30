from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Callable

from app.llm.schemas import ChatMessage, ChatRequest, ChatResponse, ToolCall, ToolRuntimeContext
from app.llm.tools.registry import execute_tool_full
from app.llm.usage import merge_usage

MAX_TOOL_ROUNDS = 5


def _coerce_loop_response(result) -> ChatResponse:
    if isinstance(result, ChatResponse):
        return result
    raw = getattr(result, "raw", {})
    if not isinstance(raw, dict):
        raw = {}
    tool_calls = getattr(result, "tool_calls", [])
    if not isinstance(tool_calls, list):
        tool_calls = []
    usage = getattr(result, "usage", None)
    return ChatResponse(
        content=str(getattr(result, "content", "") or ""),
        provider=str(getattr(result, "provider", "") or ""),
        model=str(getattr(result, "model", "") or ""),
        finish_reason=str(getattr(result, "finish_reason", "stop") or "stop"),
        raw=raw,
        tool_calls=tool_calls,
        usage=usage,
    )


def run_tool_loop(
    client,
    request: ChatRequest,
    *,
    tool_context: ToolRuntimeContext | None = None,
    on_tool_call: Callable[[ToolCall], None] | None = None,
    on_tool_result: Callable[[ToolCall, str], None] | None = None,
) -> ChatResponse:
    if not request.tools:
        return client.chat(request)

    working_request = deepcopy(request)
    accumulated_usage = None

    for _ in range(MAX_TOOL_ROUNDS):
        response = _coerce_loop_response(client.chat(working_request))
        accumulated_usage = merge_usage(accumulated_usage, response.usage)

        if not getattr(response, "tool_calls", None):
            if accumulated_usage is None:
                return response
            return replace(response, usage=accumulated_usage)

        working_request.messages.append(
            ChatMessage(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
                reasoning_content=str((response.raw or {}).get("reasoning_content", "") or ""),
            )
        )

        for tc in response.tool_calls:
            if on_tool_call:
                on_tool_call(tc)

            result = execute_tool_full(tc.name, tc.arguments, context=tool_context)

            if on_tool_result:
                on_tool_result(tc, result.text)

            working_request.messages.append(
                ChatMessage(
                    role="tool",
                    content=result.text,
                    tool_call_id=tc.id,
                )
            )

    working_request.tools = []
    response = _coerce_loop_response(client.chat(working_request))
    accumulated_usage = merge_usage(accumulated_usage, response.usage)
    if accumulated_usage is None:
        return response
    return replace(response, usage=accumulated_usage)
