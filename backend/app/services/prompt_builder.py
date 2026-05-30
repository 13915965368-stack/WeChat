from __future__ import annotations

from typing import Any

from app.llm.protocols.agents import (
    build_group_moderator_note_instruction_message,
    build_group_moderator_note_prompt as build_agent_group_moderator_note_prompt,
    build_group_runtime_dispatch_system_message,
    build_group_runtime_identity_system_message,
    build_group_runtime_moderator_note_system_message,
    build_group_runtime_protocol_system_message,
)
from app.llm.protocols.common import build_markdown_output_system_prompt
from app.llm.schemas import ChatMessage
from app.models import Agent, Conversation
from app.services.group_runtime_state import (
    GROUP_RUNTIME_DEFAULT_DISPATCH_STRATEGY,
    GROUP_RUNTIME_DEFAULT_EVENT_VISIBILITY,
    MAX_GROUP_ROUND_MESSAGES,
    _get_group_moderator_note,
    _is_group_runtime_trigger_event,
    _resolve_group_trigger_event,
)


def _agent_system_content(agent: Agent) -> str:
    return build_markdown_output_system_prompt(agent.system_prompt)


def _render_member_order(member_summary: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{member['position']}. {member['agent_name']} ({member['agent_id']}) - {member['role_summary']}"
        for member in member_summary
    )


def _render_context_record(
    *,
    sender_type: str,
    sender_id: str,
    content: str,
    speaker_name: str,
    event_id: str | None = None,
    event_type: str | None = None,
    visibility: str | None = None,
    speaker_role: str | None = None,
    position: int | None = None,
    member_lookup: dict[str, dict[str, Any]] | None = None,
) -> str:
    lines = [
        "[record]",
        f"event_id={event_id or ''}",
        f"event_type={event_type or ''}",
        f"visibility={visibility or GROUP_RUNTIME_DEFAULT_EVENT_VISIBILITY}",
        f"speaker_type={sender_type}",
        f"speaker_id={sender_id}",
        f"speaker_name={speaker_name}",
    ]
    if speaker_role is None:
        member = (member_lookup or {}).get(sender_id)
        if member is not None:
            speaker_role = str(member.get("role_summary") or "") or None
            raw_position = member.get("position")
            position = raw_position if isinstance(raw_position, int) else position
    if speaker_role:
        lines.append(f"speaker_role={speaker_role}")
    if position is not None:
        lines.append(f"position={position}")
    lines.append(f"content={content}")
    lines.append("[/record]")
    return "\n".join(lines)


def _render_context_record_from_event(event: dict[str, Any]) -> str:
    return _render_context_record(
        sender_type=str(event.get("sender_type") or ""),
        sender_id=str(event.get("sender_id") or ""),
        content=str(event.get("content") or ""),
        speaker_name=str(event.get("speaker_name") or ""),
        event_id=str(event.get("event_id") or ""),
        event_type=str(event.get("event_type") or ""),
        visibility=str(event.get("visibility") or GROUP_RUNTIME_DEFAULT_EVENT_VISIBILITY),
        speaker_role=(
            str(event.get("speaker_role") or "")
            if event.get("speaker_role") is not None
            else None
        ),
        position=event.get("position") if isinstance(event.get("position"), int) else None,
    )


def _build_group_context_system_message(title: str, records: list[str]) -> ChatMessage | None:
    normalized_records = [record.strip() for record in records if record.strip()]
    if not normalized_records:
        return None
    return ChatMessage(role="system", content=f"{title}\n\n" + "\n\n".join(normalized_records))


def _build_group_context_preview_lines(
    history_messages: list[ChatMessage] | None = None,
    event_window: list[dict[str, Any]] | None = None,
) -> list[str]:
    if event_window is not None:
        return [
            str(event.get("content") or "").strip()
            for event in event_window
            if str(event.get("content") or "").strip()
        ]
    return [
        message.content.strip() for message in (history_messages or []) if message.content.strip()
    ]


def _build_group_event_window_messages(
    event_window: list[dict[str, Any]] | None,
) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    for event in event_window or []:
        content = str(event.get("content") or "").strip()
        if not content:
            continue
        if _is_group_runtime_trigger_event(event):
            messages.append(ChatMessage(role="user", content=content))
            continue
        messages.append(ChatMessage(role="system", content=_render_context_record_from_event(event)))
    return messages


def _build_group_identity_system_message(
    agent: Agent,
    member_summary: list[dict[str, Any]],
    replied_agent_ids: list[str] | None = None,
    include_style_summary: bool = False,
) -> ChatMessage | None:
    if not member_summary:
        return None

    current_member = next(
        (member for member in member_summary if member["agent_id"] == agent.id),
        None,
    )
    if current_member is None:
        return None

    replied_agent_ids = [agent_id for agent_id in (replied_agent_ids or []) if agent_id != agent.id]
    replied_names = [
        member["agent_name"]
        for member in member_summary
        if member["agent_id"] in replied_agent_ids
    ]
    upcoming_names = [
        member["agent_name"]
        for member in member_summary
        if member["position"] > current_member["position"]
    ]
    member_order_text = _render_member_order(member_summary) or "(空)"
    replied_text = "、".join(replied_names) if replied_names else "当前轮次暂无其他成员已发言"
    upcoming_text = "、".join(upcoming_names) if upcoming_names else "你是本轮最后一位发言成员"

    message = build_group_runtime_identity_system_message(
        agent_name=agent.name,
        agent_id=agent.id,
        role_summary=agent.role_summary,
        current_position=current_member["position"],
        member_count=len(member_summary),
        member_order_text=member_order_text,
        replied_text=replied_text,
        upcoming_text=upcoming_text,
    )
    style_summary = agent.style_summary.strip()
    if include_style_summary and style_summary:
        message.content = f"{message.content}\n- 你的表达风格：{style_summary}"
    return message


def _build_group_protocol_system_messages(
    conversation: Conversation,
    agent: Agent,
    member_summary: list[dict[str, Any]] | None = None,
    replied_agent_ids: list[str] | None = None,
    event_window: list[dict[str, Any]] | None = None,
    dispatch_state: dict[str, Any] | None = None,
    include_style_summary: bool = False,
) -> list[ChatMessage]:
    if conversation.type != "group":
        return []

    messages = [build_group_runtime_protocol_system_message()]
    identity_message = _build_group_identity_system_message(
        agent,
        member_summary or [],
        replied_agent_ids=replied_agent_ids,
        include_style_summary=include_style_summary,
    )
    if identity_message is not None:
        messages.append(identity_message)
    if dispatch_state is not None:
        trigger_event = _resolve_group_trigger_event(
            event_window=event_window,
            dispatch_state=dispatch_state,
        )
        messages.append(
            build_group_runtime_dispatch_system_message(
                strategy=dispatch_state.get("strategy") or GROUP_RUNTIME_DEFAULT_DISPATCH_STRATEGY,
                status=dispatch_state.get("status") or "running",
                trigger_event_type=(trigger_event or {}).get("event_type") or "unknown",
                completed_member_ids=list(dispatch_state.get("completed_member_ids") or []),
                failed_member_ids=list(dispatch_state.get("failed_member_ids") or []),
                pending_member_ids=list(dispatch_state.get("pending_member_ids") or []),
            )
        )
    moderator_note = _get_group_moderator_note(conversation)
    if moderator_note:
        messages.append(build_group_runtime_moderator_note_system_message(moderator_note))
    return messages


def build_group_context_messages(
    history_messages: list[ChatMessage] | None = None,
    event_window: list[dict[str, Any]] | None = None,
) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    history_records = [message.content for message in history_messages or [] if message.content.strip()]
    history_context = _build_group_context_system_message("以下是当前群聊的历史记录。", history_records)
    if history_context is not None:
        messages.append(history_context)

    current_round = _build_group_event_window_messages(event_window)
    current_round_records = [
        message.content
        for message in current_round
        if message.role == "system" and message.content.strip()
    ]
    if len(current_round_records) > MAX_GROUP_ROUND_MESSAGES:
        current_round_records = current_round_records[-MAX_GROUP_ROUND_MESSAGES:]
    round_context = _build_group_context_system_message(
        "在你回复前，本轮已有以下成员完成发言。",
        current_round_records,
    )
    if round_context is not None:
        messages.append(round_context)
    current_user_message = next((message for message in current_round if message.role == "user"), None)
    if current_user_message is not None and current_user_message.content.strip():
        messages.append(ChatMessage(role="user", content=current_user_message.content.strip()))
    return messages


def _build_group_messages(
    *,
    conversation: Conversation,
    agent: Agent,
    history_messages: list[ChatMessage] | None = None,
    member_summary: list[dict[str, Any]] | None = None,
    replied_agent_ids: list[str] | None = None,
    event_window: list[dict[str, Any]] | None = None,
    dispatch_state: dict[str, Any] | None = None,
    include_style_summary: bool = False,
) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    messages.extend(
        _build_group_protocol_system_messages(
            conversation,
            agent,
            member_summary=member_summary,
            replied_agent_ids=replied_agent_ids,
            event_window=event_window,
            dispatch_state=dispatch_state,
            include_style_summary=include_style_summary,
        )
    )
    messages.extend(
        build_group_context_messages(
            history_messages=history_messages,
            event_window=event_window,
        )
    )
    return messages


def _build_moderator_note_user_prompt(
    *,
    conversation: Conversation,
    agent: Agent,
    content: str,
    member_summary: list[dict[str, Any]],
    history_messages: list[ChatMessage] | None = None,
    event_window: list[dict[str, Any]] | None = None,
) -> str:
    context_preview_lines = _build_group_context_preview_lines(
        history_messages,
        event_window=event_window,
    )
    context_preview_text = "\n".join(context_preview_lines) if context_preview_lines else "(空)"
    agent_position = next(
        (
            member["position"]
            for member in member_summary
            if member["agent_id"] == agent.id
        ),
        1,
    )
    return build_agent_group_moderator_note_prompt(
        user_content=content,
        member_count=len(member_summary),
        member_order_text=_render_member_order(member_summary) or "(空)",
        current_agent_name=agent.name,
        current_agent_id=agent.id,
        current_agent_position=agent_position,
        has_source_context=bool(conversation.source_conversation_id),
        context_preview_text=context_preview_text,
    )


def build_moderator_note_messages(
    *,
    conversation: Conversation,
    agent: Agent,
    content: str,
    member_summary: list[dict[str, Any]],
    history_messages: list[ChatMessage] | None = None,
    event_window: list[dict[str, Any]] | None = None,
) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    system_content = _agent_system_content(agent)
    if system_content.strip():
        messages.append(ChatMessage(role="system", content=system_content))
    messages.append(build_group_runtime_protocol_system_message())
    messages.append(build_group_moderator_note_instruction_message())
    messages.append(
        ChatMessage(
            role="user",
            content=_build_moderator_note_user_prompt(
                conversation=conversation,
                agent=agent,
                content=content,
                member_summary=member_summary,
                history_messages=history_messages,
                event_window=event_window,
            ),
        )
    )
    return messages


def build_chat_messages(
    *,
    conversation: Conversation,
    agent: Agent,
    content: str,
    is_group: bool,
    history_messages: list[ChatMessage] | None = None,
    member_summary: list[dict[str, Any]] | None = None,
    replied_agent_ids: list[str] | None = None,
    event_window: list[dict[str, Any]] | None = None,
    dispatch_state: dict[str, Any] | None = None,
    include_style_summary: bool = False,
) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    system_content = _agent_system_content(agent)
    if system_content.strip():
        messages.append(ChatMessage(role="system", content=system_content))
    if is_group:
        messages.extend(
            _build_group_messages(
                conversation=conversation,
                agent=agent,
                history_messages=history_messages,
                member_summary=member_summary,
                replied_agent_ids=replied_agent_ids,
                event_window=event_window,
                dispatch_state=dispatch_state,
                include_style_summary=include_style_summary,
            )
        )
    else:
        messages.extend(history_messages or [])
        messages.append(ChatMessage(role="user", content=content))
    return messages
