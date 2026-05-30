from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.llm.schemas import ConversationUsageSummary
from app.models import Agent, Conversation, Message


@dataclass
class GroupRuntimeState:
    history_messages: list[Any]
    normalized_attachments: list[dict[str, Any]]
    reply_agent_ids: list[str]
    agent_map: dict[str, Agent]
    member_summary: list[dict[str, Any]]
    member_lookup: dict[str, dict[str, Any]]
    event_window: list[dict[str, Any]]
    dispatch_state: dict[str, Any]
    attempted_agent_ids: list[str]
    emitted_agent_ids: list[str]
    failed_agent_ids: list[str]
    conversation_usage_summary: ConversationUsageSummary


MAX_GROUP_ROUND_MESSAGES = 64
GROUP_RUNTIME_PROTOCOL_VERSION = "group_runtime_v1"
GROUP_RUNTIME_THREAD_ID = "default"
GROUP_RUNTIME_EVENT_WINDOW_VERSION = "group_event_window_v1"
GROUP_RUNTIME_DEFAULT_DISPATCH_STRATEGY = "broadcast_chain"
GROUP_RUNTIME_DEFAULT_EVENT_VISIBILITY = "public"
GROUP_RUNTIME_USER_MEMBER_ID = "user"
GROUP_RUNTIME_USER_SENDER_TYPE = "user"
GROUP_RUNTIME_USER_SPEAKER_NAME = "用户"
GROUP_RUNTIME_TRIGGER_EVENT_TYPE = "user_message"
GROUP_RUNTIME_RESERVED_EVENT_TYPES = (
    GROUP_RUNTIME_TRIGGER_EVENT_TYPE,
    "moderator_note_ready",
    "agent_message",
    "conversation_updated",
    "done",
    "error",
)
GROUP_RUNTIME_RESERVED_FUTURE_EVENT_TYPES = (
    "agent_thinking",
    "tool_call",
    "tool_result",
    "dispatch_progress",
)
GROUP_RUNTIME_RESERVED_DISPATCH_STRATEGIES = (GROUP_RUNTIME_DEFAULT_DISPATCH_STRATEGY,)
GROUP_RUNTIME_RESERVED_FUTURE_DISPATCH_STRATEGIES = (
    "round_robin",
    "parallel_fan_out",
    "manual_handoff",
)


def build_group_runtime_metadata(conversation: Conversation) -> dict[str, Any]:
    metadata = deepcopy(conversation.runtime_metadata or {})
    if conversation.type != "group":
        return metadata

    group_runtime = deepcopy(metadata.get("group_runtime") or {})
    protocol = deepcopy(group_runtime.get("protocol") or {})
    default_thread = deepcopy(group_runtime.get("default_thread") or {})
    moderator_note = deepcopy(default_thread.get("moderator_note") or {})
    event_window = deepcopy(default_thread.get("event_window") or {})
    dispatch_state = deepcopy(default_thread.get("dispatch_state") or {})

    protocol.update(
        {
            "version": GROUP_RUNTIME_PROTOCOL_VERSION,
            "mode": "fixed_group_chat",
            "thread_id": GROUP_RUNTIME_THREAD_ID,
            "scope": "conversation_default_thread",
        }
    )
    moderator_note.setdefault("status", "pending")
    moderator_note.setdefault("content", None)
    moderator_note.setdefault("generated_by_agent_id", None)
    moderator_note.setdefault("generated_at", None)
    moderator_note.setdefault("input", None)
    event_window.setdefault("version", GROUP_RUNTIME_EVENT_WINDOW_VERSION)
    event_window.setdefault("events", [])
    event_window.setdefault("last_event_id", None)
    event_window.setdefault("last_event_type", None)
    dispatch_state.setdefault("status", "idle")
    dispatch_state.setdefault("strategy", GROUP_RUNTIME_DEFAULT_DISPATCH_STRATEGY)
    dispatch_state.setdefault("trigger_event_id", None)
    dispatch_state.setdefault("cursor", 0)
    dispatch_state.setdefault("pending_member_ids", [])
    dispatch_state.setdefault("completed_member_ids", [])
    dispatch_state.setdefault("failed_member_ids", [])
    dispatch_state.setdefault("last_completed_event_id", None)
    default_thread.update(
        {
            "thread_id": GROUP_RUNTIME_THREAD_ID,
            "kind": "conversation_default_thread",
            "moderator_note": moderator_note,
            "event_window": event_window,
            "dispatch_state": dispatch_state,
        }
    )
    group_runtime.update(
        {
            "protocol": protocol,
            "default_thread": default_thread,
        }
    )
    metadata["group_runtime"] = group_runtime
    return metadata


def ensure_group_runtime_metadata(conversation: Conversation) -> dict[str, Any]:
    metadata = build_group_runtime_metadata(conversation)
    if metadata != (conversation.runtime_metadata or {}):
        conversation.runtime_metadata = metadata
    return metadata


def _get_group_runtime_metadata(conversation: Conversation) -> dict[str, Any]:
    if conversation.type != "group":
        return {}
    return ensure_group_runtime_metadata(conversation)


def _get_group_moderator_note(conversation: Conversation) -> str | None:
    runtime_metadata = _get_group_runtime_metadata(conversation)
    content = (
        runtime_metadata.get("group_runtime", {})
        .get("default_thread", {})
        .get("moderator_note", {})
        .get("content")
    )
    if not isinstance(content, str):
        return None
    normalized_content = content.strip()
    return normalized_content or None


def _update_group_default_thread_runtime(
    conversation: Conversation,
    *,
    moderator_note: dict[str, Any] | None = None,
    event_window: dict[str, Any] | None = None,
    dispatch_state: dict[str, Any] | None = None,
) -> None:
    runtime_metadata = _get_group_runtime_metadata(conversation)
    group_runtime = deepcopy(runtime_metadata.get("group_runtime") or {})
    default_thread = deepcopy(group_runtime.get("default_thread") or {})
    if moderator_note is not None:
        default_thread["moderator_note"] = moderator_note
    if event_window is not None:
        default_thread["event_window"] = event_window
    if dispatch_state is not None:
        default_thread["dispatch_state"] = dispatch_state
    group_runtime["default_thread"] = default_thread
    updated_metadata = deepcopy(runtime_metadata)
    updated_metadata["group_runtime"] = group_runtime
    conversation.runtime_metadata = updated_metadata


def _is_group_runtime_user_member_id(member_id: str) -> bool:
    return member_id.strip() == GROUP_RUNTIME_USER_MEMBER_ID


def _is_group_runtime_user_sender(sender_type: str, sender_id: str) -> bool:
    return sender_type == GROUP_RUNTIME_USER_SENDER_TYPE and _is_group_runtime_user_member_id(sender_id)


def _build_group_reply_agent_ids(sorted_members: list[Any]) -> list[str]:
    return [
        member.member_id
        for member in sorted_members
        if not _is_group_runtime_user_member_id(member.member_id)
    ]


def _build_group_public_event(
    *,
    event_type: str,
    sender_type: str,
    sender_id: str,
    content: str,
    speaker_name: str,
    member_lookup: dict[str, dict[str, Any]] | None = None,
    event_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    member = (member_lookup or {}).get(sender_id)
    return {
        "event_id": event_id or uuid4().hex,
        "event_type": event_type,
        "visibility": GROUP_RUNTIME_DEFAULT_EVENT_VISIBILITY,
        "sender_type": sender_type,
        "sender_id": sender_id,
        "speaker_name": speaker_name,
        "speaker_role": member.get("role_summary") if member else None,
        "position": member.get("position") if member else None,
        "content": content.strip(),
        "created_at": created_at,
    }


def _build_group_trigger_event(
    *,
    content: str,
    member_lookup: dict[str, dict[str, Any]] | None = None,
    event_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    return _build_group_public_event(
        event_type=GROUP_RUNTIME_TRIGGER_EVENT_TYPE,
        sender_type=GROUP_RUNTIME_USER_SENDER_TYPE,
        sender_id=GROUP_RUNTIME_USER_MEMBER_ID,
        content=content,
        speaker_name=GROUP_RUNTIME_USER_SPEAKER_NAME,
        member_lookup=member_lookup,
        event_id=event_id,
        created_at=created_at,
    )


def _append_group_public_event(
    event_window: list[dict[str, Any]],
    event: dict[str, Any],
) -> list[dict[str, Any]]:
    updated_window = [*event_window, deepcopy(event)]
    if len(updated_window) > MAX_GROUP_ROUND_MESSAGES:
        updated_window = updated_window[-MAX_GROUP_ROUND_MESSAGES:]
    return updated_window


def _serialize_group_event_window(event_window: list[dict[str, Any]]) -> dict[str, Any]:
    last_event = event_window[-1] if event_window else {}
    return {
        "version": GROUP_RUNTIME_EVENT_WINDOW_VERSION,
        "events": deepcopy(event_window),
        "last_event_id": last_event.get("event_id"),
        "last_event_type": last_event.get("event_type"),
    }


def _is_group_runtime_trigger_event(event: dict[str, Any] | None) -> bool:
    if event is None:
        return False
    return event.get("event_type") == GROUP_RUNTIME_TRIGGER_EVENT_TYPE and _is_group_runtime_user_sender(
        str(event.get("sender_type") or ""),
        str(event.get("sender_id") or ""),
    )


def _resolve_group_trigger_event(
    event_window: list[dict[str, Any]] | None = None,
    dispatch_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    trigger_event_id = (dispatch_state or {}).get("trigger_event_id")
    if trigger_event_id:
        matched_event = next(
            (
                event
                for event in event_window or []
                if event.get("event_id") == trigger_event_id
            ),
            None,
        )
        if matched_event is not None:
            return matched_event
    return next((event for event in event_window or [] if _is_group_runtime_trigger_event(event)), None)


def build_group_runtime_hooks(
    *,
    event_window: list[dict[str, Any]] | None = None,
    dispatch_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trigger_event = _resolve_group_trigger_event(
        event_window=event_window,
        dispatch_state=dispatch_state,
    )
    return {
        "dispatch_strategy": (dispatch_state or {}).get(
            "strategy",
            GROUP_RUNTIME_DEFAULT_DISPATCH_STRATEGY,
        ),
        "trigger_event_type": (trigger_event or {}).get(
            "event_type",
            GROUP_RUNTIME_TRIGGER_EVENT_TYPE,
        ),
        "reserved_event_types": list(GROUP_RUNTIME_RESERVED_EVENT_TYPES),
        "reserved_dispatch_strategies": list(GROUP_RUNTIME_RESERVED_DISPATCH_STRATEGIES),
        "reserved_future_event_types": list(GROUP_RUNTIME_RESERVED_FUTURE_EVENT_TYPES),
        "reserved_future_dispatch_strategies": list(
            GROUP_RUNTIME_RESERVED_FUTURE_DISPATCH_STRATEGIES
        ),
    }


def _build_group_dispatch_state(
    *,
    trigger_event_id: str | None,
    reply_agent_ids: list[str],
    completed_member_ids: list[str] | None = None,
    failed_member_ids: list[str] | None = None,
    status: str = "running",
    strategy: str = GROUP_RUNTIME_DEFAULT_DISPATCH_STRATEGY,
    last_completed_event_id: str | None = None,
) -> dict[str, Any]:
    completed = list(completed_member_ids or [])
    failed = list(failed_member_ids or [])
    processed = [*completed, *(agent_id for agent_id in failed if agent_id not in completed)]
    pending = [agent_id for agent_id in reply_agent_ids if agent_id not in processed]
    return {
        "status": status,
        "strategy": strategy,
        "trigger_event_id": trigger_event_id,
        "cursor": len(processed),
        "pending_member_ids": pending,
        "completed_member_ids": completed,
        "failed_member_ids": failed,
        "last_completed_event_id": last_completed_event_id,
    }


def _sync_group_dispatch_state(
    conversation: Conversation,
    runtime_state: GroupRuntimeState,
    *,
    last_completed_event_id: str | None = None,
) -> None:
    runtime_state.dispatch_state = _build_group_dispatch_state(
        trigger_event_id=runtime_state.dispatch_state.get("trigger_event_id"),
        reply_agent_ids=runtime_state.reply_agent_ids,
        completed_member_ids=runtime_state.emitted_agent_ids,
        failed_member_ids=runtime_state.failed_agent_ids,
        status=(
            "completed"
            if len(runtime_state.attempted_agent_ids) == len(runtime_state.reply_agent_ids)
            else "running"
        ),
        last_completed_event_id=last_completed_event_id,
    )
    _update_group_default_thread_runtime(
        conversation,
        event_window=_serialize_group_event_window(runtime_state.event_window),
        dispatch_state=runtime_state.dispatch_state,
    )


def _append_group_agent_reply(
    conversation: Conversation,
    runtime_state: GroupRuntimeState,
    agent: Agent,
    reply_message: Message,
) -> None:
    reply_event = _build_group_public_event(
        event_type="agent_message",
        sender_type="agent",
        sender_id=agent.id,
        content=reply_message.content,
        speaker_name=agent.name,
        member_lookup=runtime_state.member_lookup,
        event_id=reply_message.id,
        created_at=reply_message.created_at,
    )
    runtime_state.event_window = _append_group_public_event(runtime_state.event_window, reply_event)
    if agent.id not in runtime_state.attempted_agent_ids:
        runtime_state.attempted_agent_ids.append(agent.id)
    if agent.id not in runtime_state.emitted_agent_ids:
        runtime_state.emitted_agent_ids.append(agent.id)
    if agent.id in runtime_state.failed_agent_ids:
        runtime_state.failed_agent_ids = [
            failed_agent_id
            for failed_agent_id in runtime_state.failed_agent_ids
            if failed_agent_id != agent.id
        ]
    _sync_group_dispatch_state(
        conversation,
        runtime_state,
        last_completed_event_id=reply_message.id,
    )


def _mark_group_agent_failure(
    conversation: Conversation,
    runtime_state: GroupRuntimeState,
    agent: Agent,
) -> None:
    if agent.id not in runtime_state.attempted_agent_ids:
        runtime_state.attempted_agent_ids.append(agent.id)
    if agent.id not in runtime_state.failed_agent_ids:
        runtime_state.failed_agent_ids.append(agent.id)
    _sync_group_dispatch_state(
        conversation,
        runtime_state,
        last_completed_event_id=runtime_state.dispatch_state.get("last_completed_event_id"),
    )
