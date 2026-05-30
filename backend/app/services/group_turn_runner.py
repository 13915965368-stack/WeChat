from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.common import utc_now_iso
from app.models import Agent, Conversation, Message
from app.services.group_runtime_state import (
    GroupRuntimeState,
    _append_group_agent_reply,
    _mark_group_agent_failure,
)
from app.services.group_text_sanitizer import sanitize_group_reply_content


@dataclass
class GroupTurnOutcome:
    reply_message: Message | None
    failed: bool
    error: Exception | None = None


def run_single_group_agent_turn(
    db: Session,
    conversation: Conversation,
    agent: Agent,
    content: str,
    runtime_state: GroupRuntimeState,
    *,
    thinking_enabled: bool,
    generate_agent_reply: Callable[..., Any],
    coerce_chat_response: Callable[[Any], Any],
    ensure_displayable: Callable[..., Any],
    build_persisted_message: Callable[..., Message],
    update_usage: Callable[..., Any],
    filter_callable_kwargs: Callable[[Any, dict[str, Any]], dict[str, Any]],
    on_tool_call: Callable[..., Any] | None = None,
    on_tool_result: Callable[..., Any] | None = None,
) -> GroupTurnOutcome:
    reply_kwargs: dict[str, Any] = {
        "thinking_enabled": thinking_enabled,
        "attachments": runtime_state.normalized_attachments,
        "history_messages": runtime_state.history_messages,
        "member_summary": runtime_state.member_summary,
        "replied_agent_ids": list(runtime_state.emitted_agent_ids),
        "event_window": runtime_state.event_window,
        "dispatch_state": runtime_state.dispatch_state,
        "on_tool_call": on_tool_call,
        "on_tool_result": on_tool_result,
    }
    reply_kwargs = filter_callable_kwargs(generate_agent_reply, reply_kwargs)

    try:
        reply_response = coerce_chat_response(
            generate_agent_reply(
                db,
                conversation,
                agent,
                content,
                **reply_kwargs,
            )
        )
        reply_response.content = sanitize_group_reply_content(agent, reply_response.content)
        ensure_displayable(
            reply_response,
            allow_thinking_display=thinking_enabled,
            agent_name=agent.name,
        )
        reply_message = build_persisted_message(
            conversation_id=conversation.id,
            sender_type="agent",
            sender_id=agent.id,
            content=reply_response.content,
            attachments=[],
            response=reply_response,
            created_at=utc_now_iso(),
            round_index=len(runtime_state.emitted_agent_ids) + 1,
            agent=agent,
            allow_thinking_display=thinking_enabled,
        )
        db.add(reply_message)
        runtime_state.conversation_usage_summary = update_usage(
            conversation,
            reply_response,
            agent=agent,
        )
        conversation.updated_at = reply_message.created_at
        _append_group_agent_reply(conversation, runtime_state, agent, reply_message)
        return GroupTurnOutcome(reply_message=reply_message, failed=False)
    except Exception as exc:  # noqa: BLE001
        _mark_group_agent_failure(conversation, runtime_state, agent)
        return GroupTurnOutcome(reply_message=None, failed=True, error=exc)
