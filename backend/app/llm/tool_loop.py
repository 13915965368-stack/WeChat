from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Callable

from app.llm.schemas import ChatMessage, ChatRequest, ChatResponse, ToolCall, ToolRuntimeContext
from app.llm.tools.registry import execute_tool

MAX_TOOL_ROUNDS = 5


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

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat(working_request)

        if not getattr(response, "tool_calls", None):
            return response

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

            result = execute_tool(tc.name, tc.arguments, context=tool_context)

            if on_tool_result:
                on_tool_result(tc, result)

            working_request.messages.append(
                ChatMessage(
                    role="tool",
                    content=result,
                    tool_call_id=tc.id,
                )
            )

    working_request.tools = []
    return client.chat(working_request)
