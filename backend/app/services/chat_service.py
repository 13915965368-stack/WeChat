from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from inspect import Parameter, signature
import re
from typing import Any, Generator
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common import utc_now_iso
from app.config import get_settings
from app.llm.client_factory import create_client
from app.llm.endpoint_fallback import EndpointFallbackError, run_with_endpoint_fallback
from app.llm.schemas import AdapterCapabilities, AdapterConfig, AttachmentRef, ChatMessage, ChatRequest
from app.llm.validator import LLMValidationError
from app.models import Agent, Conversation, LLMSettings, Message, ModelConfig
from app.security import decrypt_secret


@dataclass
class MessageSendResult:
    user_message: Message
    agent_messages: list[Message]
    conversation_updated_at: str
    warnings: list[dict[str, str]]


@dataclass
class GroupRuntimeState:
    history_messages: list[ChatMessage]
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


MAX_HISTORY_MESSAGES = 12
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
GROUP_RUNTIME_PROTOCOL_TEXT = (
    "你正在参与一个固定顺序的群聊接力。你要承接当前讨论继续推进，而不是复述用户原话、"
    "前序 Agent 原话或整段上下文记录。请结合自己的角色定位，只补充当前轮次最有价值的新增判断；"
    "后续成员会继续接力，因此不要替别人一次性说完全部内容。内部主持说明只作为运行时协作约束，"
    "不要在公开回复里直接暴露或自称正在主持。公开回复只需要写出你这轮真正要表达的内容；"
    "发言者身份会由系统单独展示。若上下文中出现群聊记录，它们用于说明之前是谁说了什么，"
    "不等于公开回复模板。如果用户要求你做自我介绍，可以自然介绍自己的身份和角色，"
    "是否提到名字由你当前的人设和语境决定。"
)
GROUP_MODERATOR_NOTE_SYSTEM_TEXT = (
    "你现在不是在生成公开回复，而是在为当前群聊生成一次性内部主持说明。"
    "这段说明只写入群聊运行时元数据，不进入普通消息流。"
)
GROUP_REPLY_PREFIX_MAX_STRIPS = 3


def _build_runtime_adapter_config(db: Session) -> AdapterConfig:
    runtime_settings = db.get(LLMSettings, 1)
    if runtime_settings is not None:
        settings = get_settings()
        return AdapterConfig(
            provider=runtime_settings.provider,
            model=runtime_settings.model,
            api_key=decrypt_secret(runtime_settings.api_key, settings),
            api_format="openai",
            metadata={"source": "llm_settings"},
        )

    settings = get_settings()
    return AdapterConfig(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        api_format="openai",
        metadata={"source": "runtime_env"},
    )


def _build_model_adapter_config(model_config: ModelConfig) -> AdapterConfig:
    settings = get_settings()
    return AdapterConfig(
        provider=model_config.provider,
        model=model_config.model,
        api_key=decrypt_secret(model_config.api_key_encrypted, settings),
        api_format=model_config.api_format,
        base_url=model_config.base_url,
        use_full_url=model_config.use_full_url,
        capabilities=AdapterCapabilities.from_mapping(model_config.capabilities),
        metadata={
            "model_config_id": model_config.id,
            "source": "model_config",
            "status": model_config.status,
        },
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


def _build_group_context_record(
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


def _build_group_context_record_from_event(event: dict[str, Any]) -> str:
    return _build_group_context_record(
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
        messages.append(ChatMessage(role="system", content=_build_group_context_record_from_event(event)))
    return messages


def _build_group_member_summary(
    reply_agent_ids: list[str],
    agent_map: dict[str, Agent],
) -> list[dict[str, Any]]:
    return [
        {
            "position": index,
            "agent_id": agent_id,
            "agent_name": agent_map[agent_id].name,
            "role_summary": agent_map[agent_id].role_summary,
        }
        for index, agent_id in enumerate(reply_agent_ids, start=1)
        if agent_id in agent_map
    ]


def _format_group_member_order(member_summary: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{member['position']}. {member['agent_name']} ({member['agent_id']}) - {member['role_summary']}"
        for member in member_summary
    )


def _build_group_member_lookup(member_summary: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {
        str(member["agent_id"]): member
        for member in member_summary or []
        if str(member.get("agent_id", "")).strip()
    }


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


def _build_group_identity_system_message(
    agent: Agent,
    member_summary: list[dict[str, Any]],
    replied_agent_ids: list[str] | None = None,
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
    member_order_text = _format_group_member_order(member_summary) or "(空)"
    replied_text = "、".join(replied_names) if replied_names else "当前轮次暂无其他成员已发言"
    upcoming_text = "、".join(upcoming_names) if upcoming_names else "你是本轮最后一位发言成员"

    return ChatMessage(
        role="system",
        content=(
            "当前公开回复身份说明：\n"
            f"- 你的显示名：{agent.name} ({agent.id})\n"
            f"- 你的角色定位：{agent.role_summary}\n"
            f"- 你的当前顺位：第 {current_member['position']} 位，共 {len(member_summary)} 位成员\n"
            f"- 当前群聊成员与顺序：\n{member_order_text}\n"
            f"- 在你之前已完成当前轮次发言的成员：{replied_text}\n"
            f"- 在你之后将继续接力的成员：{upcoming_text}\n"
            "- 你不能只靠转录稿猜身份；以上顺序和身份信息就是当前群结构。\n"
            "- 发言者身份会由显示层单独展示；公开回复只需要写出你这轮真正要表达的内容。\n"
            "- 如果下方出现群聊上下文记录，其中的 speaker 字段是运行时元数据，不是公开回复模板。"
        ),
    )


def _build_group_protocol_system_messages(
    conversation: Conversation,
    agent: Agent,
    member_summary: list[dict[str, Any]] | None = None,
    replied_agent_ids: list[str] | None = None,
    event_window: list[dict[str, Any]] | None = None,
    dispatch_state: dict[str, Any] | None = None,
) -> list[ChatMessage]:
    if conversation.type != "group":
        return []

    messages = [ChatMessage(role="system", content=GROUP_RUNTIME_PROTOCOL_TEXT)]
    identity_message = _build_group_identity_system_message(
        agent,
        member_summary or [],
        replied_agent_ids=replied_agent_ids,
    )
    if identity_message is not None:
        messages.append(identity_message)
    if dispatch_state is not None:
        trigger_event = _resolve_group_trigger_event(
            event_window=event_window,
            dispatch_state=dispatch_state,
        )
        messages.append(
            ChatMessage(
                role="system",
                content=(
                    "当前群聊运行段信息：\n"
                    f"- 调度策略：{dispatch_state.get('strategy') or GROUP_RUNTIME_DEFAULT_DISPATCH_STRATEGY}\n"
                    f"- 运行状态：{dispatch_state.get('status') or 'running'}\n"
                    f"- 触发事件类型：{(trigger_event or {}).get('event_type') or 'unknown'}\n"
                    f"- 当前已完成成员：{', '.join(dispatch_state.get('completed_member_ids') or []) or '(空)'}\n"
                    f"- 当前失败成员：{', '.join(dispatch_state.get('failed_member_ids') or []) or '(空)'}\n"
                    f"- 当前待发言成员：{', '.join(dispatch_state.get('pending_member_ids') or []) or '(空)'}\n"
                    "- 你需要承接当前公开事件窗口里最新的状态继续推进，不要把窗口里的记录当成公开回复模板。"
                ),
            )
        )
    moderator_note = _get_group_moderator_note(conversation)
    if moderator_note:
        messages.append(
            ChatMessage(
                role="system",
                content=f"群聊内部主持说明（仅内部使用，不要直接说出来）：{moderator_note}",
            )
        )
    return messages


def _build_group_moderator_note_prompt(
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
    return (
        "请生成一段只供群聊内部使用的一次性主持说明。\n"
        f"当前用户输入：{content.strip()}\n"
        f"成员数量：{len(member_summary)}\n"
        f"成员顺序：\n{_format_group_member_order(member_summary) or '(空)'}\n"
        f"当前 Agent 身份：{agent.name} ({agent.id})，位于第 {agent_position} 位\n"
        f"是否存在来源上下文：{'是' if conversation.source_conversation_id else '否'}\n"
        f"当前上下文记录：\n{context_preview_text}\n\n"
        "输出要求：\n"
        "1. 用 2-5 句中文概括当前群聊要完成的事和协作方式。\n"
        "2. 明确后续成员要按顺序承接，不要重复上下文记录。\n"
        "3. 不要写成对用户可见的发言，不要自称主持人已经发言。\n"
        "4. 不要输出 Markdown 标题或列表符号。"
    )


def _persist_group_moderator_note(
    conversation: Conversation,
    note_content: str,
    agent: Agent,
    content: str,
    member_summary: list[dict[str, Any]],
    history_messages: list[ChatMessage] | None = None,
    event_window: list[dict[str, Any]] | None = None,
) -> None:
    updated_moderator_note = {
        "status": "ready",
        "content": note_content.strip(),
        "generated_by_agent_id": agent.id,
        "generated_at": utc_now_iso(),
        "input": {
            "current_user_input": content.strip(),
            "member_count": len(member_summary),
            "member_order": deepcopy(member_summary),
            "current_agent_id": agent.id,
            "current_agent_name": agent.name,
            "has_source_context": bool(conversation.source_conversation_id),
            "transcript": _build_group_context_preview_lines(
                history_messages,
                event_window=event_window,
            ),
        },
    }
    _update_group_default_thread_runtime(conversation, moderator_note=updated_moderator_note)


def resolve_adapter_config(db: Session, conversation: Conversation, agent: Agent) -> AdapterConfig:
    model_config_id = (conversation.model_config_id or agent.model_config_id or "").strip()
    if not model_config_id:
        return _build_runtime_adapter_config(db)

    model_config = db.get(ModelConfig, model_config_id)
    if model_config is None:
        # Task2 keeps the current chat flow stable even when Task3+ state is incomplete.
        return _build_runtime_adapter_config(db)

    return _build_model_adapter_config(model_config)


def load_recent_history_messages(
    db: Session,
    conversation_id: str,
    limit: int = MAX_HISTORY_MESSAGES,
) -> list[Message]:
    recent_messages = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    ).all()
    return list(reversed(recent_messages))


def _build_agent_name_map(db: Session, sender_ids: set[str]) -> dict[str, str]:
    if not sender_ids:
        return {}
    return {
        agent.id: agent.name
        for agent in db.scalars(select(Agent).where(Agent.id.in_(sender_ids))).all()
    }


def _build_agent_runtime_map(db: Session, sender_ids: set[str]) -> dict[str, dict[str, str]]:
    if not sender_ids:
        return {}
    return {
        agent.id: {
            "name": agent.name,
            "role_summary": agent.role_summary,
        }
        for agent in db.scalars(select(Agent).where(Agent.id.in_(sender_ids))).all()
    }


def _resolve_group_speaker_name(
    sender_type: str,
    sender_id: str,
    agent_name_map: dict[str, str],
) -> str:
    if sender_type == "agent":
        return agent_name_map.get(sender_id, sender_id)
    if _is_group_runtime_user_sender(sender_type, sender_id):
        return GROUP_RUNTIME_USER_SPEAKER_NAME
    return sender_id


def _strip_group_speaker_prefix_once(content: str, prefix_candidates: list[str]) -> str:
    for prefix in prefix_candidates:
        normalized_prefix = prefix.strip()
        if not normalized_prefix:
            continue
        escaped_prefix = re.escape(normalized_prefix)
        patterns = (
            rf"^{escaped_prefix}\s*[：:]\s*",
            rf"^{escaped_prefix}\s+(?:updated|update)\s*[：:]\s*",
        )
        for pattern in patterns:
            stripped = re.sub(pattern, "", content, count=1, flags=re.IGNORECASE).strip()
            if stripped and stripped != content:
                return stripped
    return content


def _normalize_legacy_group_content(
    sender_type: str,
    sender_id: str,
    content: str,
    runtime_map: dict[str, dict[str, str]],
) -> str:
    cleaned = content.strip()
    if sender_type != "agent" or not cleaned:
        return cleaned

    runtime_info = runtime_map.get(sender_id, {})
    prefix_candidates = [runtime_info.get("name", ""), sender_id]
    for _ in range(GROUP_REPLY_PREFIX_MAX_STRIPS):
        updated = _strip_group_speaker_prefix_once(cleaned, prefix_candidates)
        if updated == cleaned:
            break
        cleaned = updated
    return cleaned


def build_history_messages(
    db: Session,
    conversation: Conversation,
    history_records: list[Message],
) -> list[ChatMessage]:
    is_group = conversation.type == "group"
    sender_ids = {message.sender_id for message in history_records if message.sender_type == "agent"}
    agent_name_map = _build_agent_name_map(db, sender_ids)
    agent_runtime_map = _build_agent_runtime_map(db, sender_ids)
    history_messages: list[ChatMessage] = []
    for message in history_records:
        content = message.content.strip()
        if not content:
            continue
        if is_group:
            speaker_name = _resolve_group_speaker_name(
                message.sender_type,
                message.sender_id,
                agent_name_map,
            )
            normalized_content = _normalize_legacy_group_content(
                message.sender_type,
                message.sender_id,
                content,
                agent_runtime_map,
            )
            history_messages.append(
                ChatMessage(
                    role="system",
                    content=_build_group_context_record(
                        sender_type=message.sender_type,
                        sender_id=message.sender_id,
                        content=normalized_content,
                        speaker_name=speaker_name,
                        member_lookup=agent_runtime_map,
                    ),
                )
            )
            continue
        if message.sender_type == "agent":
            history_messages.append(ChatMessage(role="assistant", content=content))
            continue
        history_messages.append(ChatMessage(role="user", content=content))
    return history_messages


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


def build_chat_request(
    config: AdapterConfig,
    conversation: Conversation,
    agent: Agent,
    content: str,
    is_group: bool,
    attachments: list[dict[str, Any]] | None = None,
    history_messages: list[ChatMessage] | None = None,
    member_summary: list[dict[str, Any]] | None = None,
    replied_agent_ids: list[str] | None = None,
    event_window: list[dict[str, Any]] | None = None,
    dispatch_state: dict[str, Any] | None = None,
) -> ChatRequest:
    messages: list[ChatMessage] = []
    if agent.system_prompt.strip():
        messages.append(ChatMessage(role="system", content=agent.system_prompt.strip()))
    if is_group:
        messages.extend(
            _build_group_protocol_system_messages(
                conversation,
                agent,
                member_summary=member_summary,
                replied_agent_ids=replied_agent_ids,
                event_window=event_window,
                dispatch_state=dispatch_state,
            )
        )
        messages.extend(
            build_group_context_messages(
                history_messages,
                event_window=event_window,
            )
        )
    else:
        messages.extend(history_messages or [])
        messages.append(ChatMessage(role="user", content=content))
    attachment_refs = [AttachmentRef.from_mapping(attachment) for attachment in attachments or []]
    return ChatRequest(
        config=config,
        messages=messages,
        agent_id=agent.id,
        agent_name=agent.name,
        user_text=content,
        system_prompt=agent.system_prompt,
        is_group=is_group,
        attachments=attachment_refs,
        metadata=(
            {
                "group_protocol_version": GROUP_RUNTIME_PROTOCOL_VERSION,
                "thread_id": GROUP_RUNTIME_THREAD_ID,
                "moderator_note_present": bool(_get_group_moderator_note(conversation)),
                **build_group_runtime_hooks(
                    event_window=event_window,
                    dispatch_state=dispatch_state,
                ),
            }
            if is_group
            else {}
        ),
    )


def generate_group_moderator_note(
    db: Session,
    conversation: Conversation,
    agent: Agent,
    content: str,
    member_summary: list[dict[str, Any]],
    history_messages: list[ChatMessage] | None = None,
    event_window: list[dict[str, Any]] | None = None,
) -> str:
    adapter_config = resolve_adapter_config(db, conversation, agent)
    moderator_prompt = _build_group_moderator_note_prompt(
        conversation=conversation,
        agent=agent,
        content=content,
        member_summary=member_summary,
        history_messages=history_messages,
        event_window=event_window,
    )
    return run_with_endpoint_fallback(
        adapter_config,
        lambda candidate_config: create_client(candidate_config)
        .chat(
            ChatRequest(
                config=candidate_config,
                messages=[
                    *(
                        [ChatMessage(role="system", content=agent.system_prompt.strip())]
                        if agent.system_prompt.strip()
                        else []
                    ),
                    ChatMessage(role="system", content=GROUP_RUNTIME_PROTOCOL_TEXT),
                    ChatMessage(role="system", content=GROUP_MODERATOR_NOTE_SYSTEM_TEXT),
                    ChatMessage(role="user", content=moderator_prompt),
                ],
                agent_id=agent.id,
                agent_name=agent.name,
                user_text=content,
                system_prompt=agent.system_prompt,
                is_group=True,
                metadata={
                    "purpose": "group_moderator_note",
                    "group_protocol_version": GROUP_RUNTIME_PROTOCOL_VERSION,
                    "thread_id": GROUP_RUNTIME_THREAD_ID,
                },
            )
        )
        .content,
    )


def generate_agent_reply(
    db: Session,
    conversation: Conversation,
    agent: Agent,
    content: str,
    attachments: list[dict[str, Any]] | None = None,
    history_messages: list[ChatMessage] | None = None,
    member_summary: list[dict[str, Any]] | None = None,
    replied_agent_ids: list[str] | None = None,
    event_window: list[dict[str, Any]] | None = None,
    dispatch_state: dict[str, Any] | None = None,
) -> str:
    adapter_config = resolve_adapter_config(db, conversation, agent)
    return run_with_endpoint_fallback(
        adapter_config,
        lambda candidate_config: create_client(candidate_config)
        .chat(
            build_chat_request(
                config=candidate_config,
                conversation=conversation,
                agent=agent,
                content=content,
                is_group=conversation.type == "group",
                attachments=attachments,
                history_messages=history_messages,
                member_summary=member_summary,
                replied_agent_ids=replied_agent_ids,
                event_window=event_window,
                dispatch_state=dispatch_state,
            )
        )
        .content,
    )


def _get_runtime_hooks_payload(
    *,
    event_window: list[dict[str, Any]] | None = None,
    dispatch_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_group_runtime_hooks(
        event_window=event_window,
        dispatch_state=dispatch_state,
    )


def _initialize_group_runtime_state(
    db: Session,
    conversation: Conversation,
    user_message: Message,
    content: str,
    normalized_attachments: list[dict[str, Any]],
    history_messages: list[ChatMessage],
) -> GroupRuntimeState:
    if "members" not in conversation.__dict__:
        db.refresh(conversation, ["members"])
    sorted_members = sorted(conversation.members, key=lambda item: item.sort_order)
    reply_agent_ids = _build_group_reply_agent_ids(sorted_members)
    agent_map = {agent.id: agent for agent in db.scalars(select(Agent).where(Agent.id.in_(reply_agent_ids))).all()}
    member_summary = _build_group_member_summary(reply_agent_ids, agent_map)
    member_lookup = _build_group_member_lookup(member_summary)
    trigger_event = _build_group_trigger_event(
        content=content,
        member_lookup=member_lookup,
        event_id=user_message.id,
        created_at=user_message.created_at,
    )
    event_window = _append_group_public_event([], trigger_event)
    dispatch_state = _build_group_dispatch_state(
        trigger_event_id=trigger_event["event_id"],
        reply_agent_ids=reply_agent_ids,
        completed_member_ids=[],
        failed_member_ids=[],
        status="running",
    )
    ensure_group_runtime_metadata(conversation)
    _update_group_default_thread_runtime(
        conversation,
        event_window=_serialize_group_event_window(event_window),
        dispatch_state=dispatch_state,
    )
    return GroupRuntimeState(
        history_messages=history_messages,
        normalized_attachments=normalized_attachments,
        reply_agent_ids=reply_agent_ids,
        agent_map=agent_map,
        member_summary=member_summary,
        member_lookup=member_lookup,
        event_window=event_window,
        dispatch_state=dispatch_state,
        attempted_agent_ids=[],
        emitted_agent_ids=[],
        failed_agent_ids=[],
    )


def _ensure_group_moderator_note(
    db: Session,
    conversation: Conversation,
    content: str,
    runtime_state: GroupRuntimeState,
) -> bool:
    if not runtime_state.reply_agent_ids or _get_group_moderator_note(conversation):
        return False
    first_agent = runtime_state.agent_map[runtime_state.reply_agent_ids[0]]
    moderator_note = generate_group_moderator_note(
        db,
        conversation,
        first_agent,
        content,
        runtime_state.member_summary,
        history_messages=runtime_state.history_messages,
        event_window=runtime_state.event_window,
    )
    _persist_group_moderator_note(
        conversation,
        moderator_note,
        first_agent,
        content,
        runtime_state.member_summary,
        history_messages=runtime_state.history_messages,
        event_window=runtime_state.event_window,
    )
    return True


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


def _run_group_agent_sequence(
    db: Session,
    conversation: Conversation,
    content: str,
    runtime_state: GroupRuntimeState,
) -> Generator[tuple[Agent, Message], None, None]:
    for reply_agent_id in runtime_state.reply_agent_ids:
        agent = runtime_state.agent_map[reply_agent_id]
        reply_kwargs: dict[str, Any] = {
            "attachments": runtime_state.normalized_attachments,
            "history_messages": runtime_state.history_messages,
            "member_summary": runtime_state.member_summary,
            "replied_agent_ids": list(runtime_state.emitted_agent_ids),
            "event_window": runtime_state.event_window,
            "dispatch_state": runtime_state.dispatch_state,
        }
        reply_kwargs = _filter_callable_kwargs(generate_agent_reply, reply_kwargs)
        reply_content = generate_agent_reply(
            db,
            conversation,
            agent,
            content,
            **reply_kwargs,
        )
        reply_content = sanitize_group_reply_content(agent, reply_content)
        reply_message = Message(
            id=uuid4().hex,
            conversation_id=conversation.id,
            sender_type="agent",
            sender_id=agent.id,
            content=reply_content,
            attachments=[],
            created_at=utc_now_iso(),
        )
        db.add(reply_message)
        conversation.updated_at = reply_message.created_at
        _append_group_agent_reply(conversation, runtime_state, agent, reply_message)
        yield agent, reply_message


def _strip_current_agent_reply_prefix_once(content: str, agent: Agent) -> str:
    prefix_candidates = [agent.name.strip(), agent.id.strip()]
    for prefix in prefix_candidates:
        if not prefix:
            continue
        escaped_prefix = re.escape(prefix)
        patterns = (
            rf"^{escaped_prefix}\s*[：:]\s*",
            rf"^{escaped_prefix}\s+(?:updated|update)\s*[：:]\s*",
        )
        for pattern in patterns:
            stripped = re.sub(pattern, "", content, count=1, flags=re.IGNORECASE).strip()
            if stripped and stripped != content:
                return stripped
    return content


def sanitize_group_reply_content(agent: Agent, reply_content: str) -> str:
    cleaned = reply_content.strip()
    if not cleaned:
        return cleaned

    for _ in range(GROUP_REPLY_PREFIX_MAX_STRIPS):
        updated = _strip_current_agent_reply_prefix_once(cleaned, agent)
        if updated == cleaned:
            break
        cleaned = updated
    return cleaned


def _filter_callable_kwargs(func: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    parameters = signature(func).parameters.values()
    if any(parameter.kind == Parameter.VAR_KEYWORD for parameter in parameters):
        return kwargs

    accepted_names = {
        parameter.name
        for parameter in parameters
        if parameter.kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
    }
    return {key: value for key, value in kwargs.items() if key in accepted_names}


def send_message(
    db: Session,
    conversation: Conversation,
    content: str,
    attachments: list[dict[str, Any]] | None = None,
) -> MessageSendResult:
    if "members" not in conversation.__dict__:
        db.refresh(conversation, ["members"])

    base_time = utc_now_iso()
    normalized_attachments = [dict(attachment) for attachment in attachments or []]
    history_records = load_recent_history_messages(db, conversation.id)
    history_messages = build_history_messages(db, conversation, history_records)
    user_message = Message(
        id=uuid4().hex,
        conversation_id=conversation.id,
        sender_type="user",
        sender_id="user",
        content=content,
        attachments=normalized_attachments,
        created_at=base_time,
    )
    db.add(user_message)

    if conversation.type == "group":
        warnings: list[dict[str, str]] = []
        runtime_state = _initialize_group_runtime_state(
            db,
            conversation,
            user_message,
            content,
            normalized_attachments,
            history_messages,
        )
        try:
            _ensure_group_moderator_note(db, conversation, content, runtime_state)
        except Exception as exc:
            warnings.append(_build_contextual_error_payload("群聊主持说明生成失败", exc))
        agent_messages = []
        for reply_agent_id in runtime_state.reply_agent_ids:
            agent = runtime_state.agent_map[reply_agent_id]
            reply_kwargs: dict[str, Any] = {
                "attachments": runtime_state.normalized_attachments,
                "history_messages": runtime_state.history_messages,
                "member_summary": runtime_state.member_summary,
                "replied_agent_ids": list(runtime_state.emitted_agent_ids),
                "event_window": runtime_state.event_window,
                "dispatch_state": runtime_state.dispatch_state,
            }
            reply_kwargs = _filter_callable_kwargs(generate_agent_reply, reply_kwargs)
            try:
                reply_content = generate_agent_reply(
                    db,
                    conversation,
                    agent,
                    content,
                    **reply_kwargs,
                )
                reply_content = sanitize_group_reply_content(agent, reply_content)
                reply_message = Message(
                    id=uuid4().hex,
                    conversation_id=conversation.id,
                    sender_type="agent",
                    sender_id=agent.id,
                    content=reply_content,
                    attachments=[],
                    created_at=utc_now_iso(),
                )
                db.add(reply_message)
                conversation.updated_at = reply_message.created_at
                _append_group_agent_reply(conversation, runtime_state, agent, reply_message)
                agent_messages.append(reply_message)
            except Exception as exc:
                _mark_group_agent_failure(conversation, runtime_state, agent)
                warnings.append(_build_contextual_error_payload(f"{agent.name} 回复失败", exc))
                continue
    else:
        warnings = []
        reply_agent_ids = [conversation.agent_id] if conversation.agent_id else []
        agent_map = {
            agent.id: agent
            for agent in db.scalars(select(Agent).where(Agent.id.in_(reply_agent_ids))).all()
        }
        agent_messages = []
        for reply_agent_id in reply_agent_ids:
            agent = agent_map[reply_agent_id]
            reply_content = generate_agent_reply(
                db,
                conversation,
                agent,
                content,
                attachments=normalized_attachments,
                history_messages=history_messages,
            )
            reply_message = Message(
                id=uuid4().hex,
                conversation_id=conversation.id,
                sender_type="agent",
                sender_id=agent.id,
                content=reply_content,
                attachments=[],
                created_at=utc_now_iso(),
            )
            db.add(reply_message)
            agent_messages.append(reply_message)

    conversation.updated_at = agent_messages[-1].created_at if agent_messages else base_time
    db.commit()
    db.refresh(user_message)
    for agent_message in agent_messages:
        db.refresh(agent_message)
    db.refresh(conversation)

    return MessageSendResult(
        user_message=user_message,
        agent_messages=agent_messages,
        conversation_updated_at=conversation.updated_at,
        warnings=warnings,
    )


def _build_stream_error_payload(exc: Exception) -> dict[str, str]:
    if isinstance(exc, LLMValidationError):
        return {"code": exc.code, "message": str(exc)}
    if isinstance(exc, EndpointFallbackError):
        return {"code": "model_endpoint_failed", "message": str(exc)}
    if isinstance(exc, ValueError):
        return {"code": "model_request_failed", "message": str(exc)}
    return {"code": "stream_generation_failed", "message": str(exc) or "群聊运行失败"}


def _build_contextual_error_payload(prefix: str, exc: Exception) -> dict[str, str]:
    payload = _build_stream_error_payload(exc)
    message = payload.get("message", "").strip() or "群聊运行失败"
    payload["message"] = f"{prefix}：{message}"
    return payload


def stream_group_message(
    db: Session,
    conversation: Conversation,
    content: str,
    attachments: list[dict[str, Any]] | None = None,
) -> Generator[tuple[str, dict[str, Any]], None, None]:
    if conversation.type != "group":
        raise ValueError("message streaming is only supported for group conversations")

    if "members" not in conversation.__dict__:
        db.refresh(conversation, ["members"])

    base_time = utc_now_iso()
    normalized_attachments = [dict(attachment) for attachment in attachments or []]
    history_records = load_recent_history_messages(db, conversation.id)
    history_messages = build_history_messages(db, conversation, history_records)

    user_message = Message(
        id=uuid4().hex,
        conversation_id=conversation.id,
        sender_type="user",
        sender_id="user",
        content=content,
        attachments=normalized_attachments,
        created_at=base_time,
    )
    db.add(user_message)
    conversation.updated_at = base_time
    runtime_state = _initialize_group_runtime_state(
        db,
        conversation,
        user_message,
        content,
        normalized_attachments,
        history_messages,
    )
    db.commit()
    db.refresh(user_message)
    db.refresh(conversation)
    yield (
        "user_message",
        {
            "conversation_id": conversation.id,
            "message": user_message,
            "conversation_updated_at": conversation.updated_at,
            "runtime_hooks": _get_runtime_hooks_payload(
                event_window=runtime_state.event_window,
                dispatch_state=runtime_state.dispatch_state,
            ),
        },
    )

    if runtime_state.reply_agent_ids and not _get_group_moderator_note(conversation):
        try:
            _ensure_group_moderator_note(db, conversation, content, runtime_state)
            db.commit()
            db.refresh(conversation)
            yield (
                "moderator_note_ready",
                {
                    "conversation_id": conversation.id,
                    "conversation_updated_at": conversation.updated_at,
                    "runtime_hooks": _get_runtime_hooks_payload(
                        event_window=runtime_state.event_window,
                        dispatch_state=runtime_state.dispatch_state,
                    ),
                },
            )
        except Exception as exc:
            db.rollback()
            db.refresh(conversation)
            yield (
                "error",
                {
                    "conversation_id": conversation.id,
                    "conversation_updated_at": conversation.updated_at,
                    "error": _build_contextual_error_payload("群聊主持说明生成失败", exc),
                    "runtime_hooks": _get_runtime_hooks_payload(
                        event_window=runtime_state.event_window,
                        dispatch_state=runtime_state.dispatch_state,
                    ),
                },
            )
    for reply_agent_id in runtime_state.reply_agent_ids:
        agent = runtime_state.agent_map[reply_agent_id]
        reply_kwargs: dict[str, Any] = {
            "attachments": runtime_state.normalized_attachments,
            "history_messages": runtime_state.history_messages,
            "member_summary": runtime_state.member_summary,
            "replied_agent_ids": list(runtime_state.emitted_agent_ids),
            "event_window": runtime_state.event_window,
            "dispatch_state": runtime_state.dispatch_state,
        }
        reply_kwargs = _filter_callable_kwargs(generate_agent_reply, reply_kwargs)
        try:
            reply_content = generate_agent_reply(
                db,
                conversation,
                agent,
                content,
                **reply_kwargs,
            )
            reply_content = sanitize_group_reply_content(agent, reply_content)
            reply_message = Message(
                id=uuid4().hex,
                conversation_id=conversation.id,
                sender_type="agent",
                sender_id=agent.id,
                content=reply_content,
                attachments=[],
                created_at=utc_now_iso(),
            )
            db.add(reply_message)
            conversation.updated_at = reply_message.created_at
            _append_group_agent_reply(conversation, runtime_state, agent, reply_message)
        except Exception as exc:
            db.rollback()
            db.refresh(conversation)
            _mark_group_agent_failure(conversation, runtime_state, agent)
            try:
                db.commit()
                db.refresh(conversation)
            except Exception as persistence_exc:
                db.rollback()
                yield (
                    "error",
                    {
                        "conversation_id": conversation.id,
                        "conversation_updated_at": conversation.updated_at,
                        "error": _build_stream_error_payload(persistence_exc),
                        "runtime_hooks": _get_runtime_hooks_payload(
                            event_window=runtime_state.event_window,
                            dispatch_state=runtime_state.dispatch_state,
                        ),
                    },
                )
                return
            yield (
                "error",
                {
                    "conversation_id": conversation.id,
                    "conversation_updated_at": conversation.updated_at,
                    "error": _build_contextual_error_payload(
                        f"{agent.name} 回复失败",
                        exc,
                    ),
                    "runtime_hooks": _get_runtime_hooks_payload(
                        event_window=runtime_state.event_window,
                        dispatch_state=runtime_state.dispatch_state,
                    ),
                },
            )
            continue
        try:
            db.commit()
            db.refresh(reply_message)
            db.refresh(conversation)
            yield (
                "agent_message",
                {
                    "conversation_id": conversation.id,
                    "message": reply_message,
                    "conversation_updated_at": conversation.updated_at,
                    "runtime_hooks": _get_runtime_hooks_payload(
                        event_window=runtime_state.event_window,
                        dispatch_state=runtime_state.dispatch_state,
                    ),
                },
            )
        except Exception as exc:
            db.rollback()
            yield (
                "error",
                {
                    "conversation_id": conversation.id,
                    "conversation_updated_at": conversation.updated_at,
                    "error": _build_stream_error_payload(exc),
                    "runtime_hooks": _get_runtime_hooks_payload(
                        event_window=runtime_state.event_window,
                        dispatch_state=runtime_state.dispatch_state,
                    ),
                },
            )
            return

    yield (
        "conversation_updated",
        {
            "conversation_id": conversation.id,
            "conversation_updated_at": conversation.updated_at,
            "runtime_hooks": _get_runtime_hooks_payload(
                event_window=runtime_state.event_window,
                dispatch_state=runtime_state.dispatch_state,
            ),
        },
    )
    yield (
        "done",
        {
            "conversation_id": conversation.id,
            "conversation_updated_at": conversation.updated_at,
            "runtime_hooks": _get_runtime_hooks_payload(
                event_window=runtime_state.event_window,
                dispatch_state=runtime_state.dispatch_state,
            ),
        },
    )
