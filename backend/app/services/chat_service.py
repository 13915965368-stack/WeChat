from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from dataclasses import dataclass
from inspect import Parameter, signature
from typing import Any, Generator
from uuid import uuid4

import app.services.prompt_builder as prompt_builder_module
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common import utc_now_iso
from app.config import get_settings
from app.llm.client_factory import create_client
from app.llm.endpoint_fallback import EndpointFallbackError, run_with_endpoint_fallback
from app.llm.protocols.common import (
    resolve_render_format,
    split_content_and_thinking,
)
from app.llm.schemas import (
    AdapterCapabilities,
    AdapterConfig,
    AttachmentRef,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConversationUsageSummary,
    MessageMeta,
    MessageThinking,
    MessageUsage,
    ThinkingConfig,
    ToolRuntimeContext,
)
from app.llm.tool_loop import run_tool_loop
from app.llm.tools.registry import get_tool_definitions
from app.llm.tools.capabilities import SearchCapability, ToolCapabilities
from app.llm.tools.tool_services import ToolServices
from app.llm.usage import (
    add_usage_to_summary,
    clone_usage_summary,
    normalize_usage_summary,
    usage_summary_to_dict,
    usage_to_dict,
)
from app.llm.validator import LLMValidationError
from app.models import Agent, Conversation, LLMSettings, Message, ModelConfig
from app.security import decrypt_secret
from app.services.adapter_config_factory import build_adapter_config_from_model
from app.services.group_runtime_state import (
    GROUP_RUNTIME_DEFAULT_EVENT_VISIBILITY,
    GROUP_RUNTIME_DEFAULT_DISPATCH_STRATEGY,
    GROUP_RUNTIME_PROTOCOL_VERSION,
    GROUP_RUNTIME_RESERVED_DISPATCH_STRATEGIES,
    GROUP_RUNTIME_RESERVED_EVENT_TYPES,
    GROUP_RUNTIME_RESERVED_FUTURE_DISPATCH_STRATEGIES,
    GROUP_RUNTIME_RESERVED_FUTURE_EVENT_TYPES,
    GROUP_RUNTIME_THREAD_ID,
    GROUP_RUNTIME_USER_SPEAKER_NAME,
    GroupRuntimeState,
    _append_group_agent_reply,
    _append_group_public_event,
    _build_group_dispatch_state,
    _build_group_public_event,
    _build_group_reply_agent_ids,
    _build_group_trigger_event,
    _get_group_moderator_note,
    _is_group_runtime_trigger_event,
    _is_group_runtime_user_sender,
    _mark_group_agent_failure,
    _resolve_group_trigger_event,
    _serialize_group_event_window,
    _sync_group_dispatch_state,
    _update_group_default_thread_runtime,
    build_group_runtime_hooks,
    build_group_runtime_metadata,
    ensure_group_runtime_metadata,
)
from app.services.group_text_sanitizer import (
    GROUP_REPLY_PREFIX_MAX_STRIPS,
    sanitize_group_reply_content,
    strip_speaker_prefix_once,
)
from app.services.group_turn_runner import run_single_group_agent_turn
from app.services.search_service import build_search_runtime_config
from app.services.stream_errors import (
    build_contextual_error_payload as _build_contextual_error_payload,
    build_stream_error_payload as _build_stream_error_payload,
)


@dataclass
class MessageSendResult:
    user_message: Message
    agent_messages: list[Message]
    conversation_updated_at: str
    conversation_usage_summary: dict[str, Any]
    warnings: list[dict[str, str]]


MAX_HISTORY_MESSAGES = 12
MAX_GROUP_ROUND_MESSAGES = 64
def _message_thinking_to_dict(thinking: MessageThinking | None) -> dict[str, Any]:
    if thinking is None:
        return {}
    return {
        "available": thinking.available,
        "content": thinking.content,
        "default_collapsed": thinking.default_collapsed,
    }


def _message_meta_to_dict(meta: MessageMeta | None) -> dict[str, Any]:
    if meta is None:
        return {}
    payload: dict[str, Any] = {}
    if meta.provider:
        payload["provider"] = meta.provider
    if meta.model:
        payload["model"] = meta.model
    if meta.agent_id:
        payload["agent_id"] = meta.agent_id
    if meta.agent_name:
        payload["agent_name"] = meta.agent_name
    if meta.round_index is not None:
        payload["round_index"] = meta.round_index
    return payload


def _build_agent_system_message_content(agent: Agent) -> str:
    return prompt_builder_module._agent_system_content(agent)


def get_conversation_usage_summary(conversation: Conversation) -> ConversationUsageSummary:
    runtime_metadata = deepcopy(conversation.runtime_metadata or {})
    return normalize_usage_summary(runtime_metadata.get("usage_summary"))


def _set_conversation_usage_summary(
    conversation: Conversation,
    summary: ConversationUsageSummary,
) -> ConversationUsageSummary:
    runtime_metadata = deepcopy(conversation.runtime_metadata or {})
    runtime_metadata["usage_summary"] = usage_summary_to_dict(summary)
    conversation.runtime_metadata = runtime_metadata
    return summary


def _build_message_meta(
    response: ChatResponse,
    *,
    agent: Agent | None = None,
    round_index: int | None = None,
) -> MessageMeta:
    return MessageMeta(
        provider=response.provider or None,
        model=response.model or None,
        agent_id=agent.id if agent is not None else None,
        agent_name=agent.name if agent is not None else None,
        round_index=round_index,
    )


def _coerce_chat_response(result: ChatResponse | str) -> ChatResponse:
    if isinstance(result, ChatResponse):
        return result
    if hasattr(result, "content"):
        return ChatResponse(content=str(getattr(result, "content") or ""), provider="", model="")
    return ChatResponse(content=str(result), provider="", model="")


def _prepare_agent_response_display(
    response: ChatResponse,
    *,
    allow_thinking_display: bool,
) -> tuple[str, MessageThinking | None]:
    render_content, thinking = split_content_and_thinking(
        response.content,
        reasoning_content=str((response.raw or {}).get("reasoning_content", "") or ""),
    )
    if not allow_thinking_display:
        thinking = None
    return render_content, thinking


def _ensure_agent_response_displayable(
    response: ChatResponse,
    *,
    allow_thinking_display: bool,
    agent_name: str,
) -> tuple[str, MessageThinking | None]:
    render_content, thinking = _prepare_agent_response_display(
        response,
        allow_thinking_display=allow_thinking_display,
    )
    if render_content.strip():
        return render_content, thinking
    if response.tool_calls:
        return render_content, thinking
    if allow_thinking_display and thinking is not None and thinking.content.strip():
        return render_content, thinking
    raise LLMValidationError(
        f"{agent_name} 未返回可展示回复",
        code="model_empty_reply",
        status_code=422,
    )


def _build_persisted_message(
    *,
    conversation_id: str,
    sender_type: str,
    sender_id: str,
    content: str,
    attachments: list[dict[str, Any]] | None = None,
    response: ChatResponse | None = None,
    created_at: str | None = None,
    round_index: int | None = None,
    agent: Agent | None = None,
    allow_thinking_display: bool = True,
) -> Message:
    thinking = None
    render_content = content.strip()
    usage = None
    message_meta = {}
    if response is not None:
        render_content, thinking = _prepare_agent_response_display(
            response,
            allow_thinking_display=allow_thinking_display,
        )
        usage = response.usage
        message_meta = _message_meta_to_dict(
            _build_message_meta(response, agent=agent, round_index=round_index)
        )

    return Message(
        id=uuid4().hex,
        conversation_id=conversation_id,
        sender_type=sender_type,
        sender_id=sender_id,
        content=render_content,
        render_format=resolve_render_format(sender_type=sender_type, content=render_content),
        thinking_payload=_message_thinking_to_dict(thinking),
        usage_payload=usage_to_dict(usage) or {},
        message_meta=message_meta,
        attachments=list(attachments or []),
        created_at=created_at or utc_now_iso(),
    )


def _update_conversation_usage_from_response(
    conversation: Conversation,
    response: ChatResponse | None,
    *,
    agent: Agent,
) -> ConversationUsageSummary:
    summary = add_usage_to_summary(
        get_conversation_usage_summary(conversation),
        response.usage if response is not None else None,
        agent_id=agent.id,
        agent_name=agent.name,
    )
    return _set_conversation_usage_summary(conversation, summary)


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
    return build_adapter_config_from_model(model_config, source="model_config")


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
    return prompt_builder_module._render_context_record(
        sender_type=sender_type,
        sender_id=sender_id,
        content=content,
        speaker_name=speaker_name,
        event_id=event_id,
        event_type=event_type,
        visibility=visibility,
        speaker_role=speaker_role,
        position=position,
        member_lookup=member_lookup,
    )


def _build_group_context_record_from_event(event: dict[str, Any]) -> str:
    return prompt_builder_module._render_context_record_from_event(event)


def _build_group_event_window_messages(
    event_window: list[dict[str, Any]] | None,
) -> list[ChatMessage]:
    return prompt_builder_module._build_group_event_window_messages(event_window)


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
    return prompt_builder_module._render_member_order(member_summary)


def _build_group_member_lookup(member_summary: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {
        str(member["agent_id"]): member
        for member in member_summary or []
        if str(member.get("agent_id", "")).strip()
    }


def _build_group_context_system_message(title: str, records: list[str]) -> ChatMessage | None:
    return prompt_builder_module._build_group_context_system_message(title, records)


def _build_group_context_preview_lines(
    history_messages: list[ChatMessage] | None = None,
    event_window: list[dict[str, Any]] | None = None,
) -> list[str]:
    return prompt_builder_module._build_group_context_preview_lines(
        history_messages=history_messages,
        event_window=event_window,
    )


def _build_group_identity_system_message(
    agent: Agent,
    member_summary: list[dict[str, Any]],
    replied_agent_ids: list[str] | None = None,
) -> ChatMessage | None:
    return prompt_builder_module._build_group_identity_system_message(
        agent,
        member_summary,
        replied_agent_ids=replied_agent_ids,
    )


def _build_group_protocol_system_messages(
    conversation: Conversation,
    agent: Agent,
    member_summary: list[dict[str, Any]] | None = None,
    replied_agent_ids: list[str] | None = None,
    event_window: list[dict[str, Any]] | None = None,
    dispatch_state: dict[str, Any] | None = None,
) -> list[ChatMessage]:
    return prompt_builder_module._build_group_protocol_system_messages(
        conversation,
        agent,
        member_summary=member_summary,
        replied_agent_ids=replied_agent_ids,
        event_window=event_window,
        dispatch_state=dispatch_state,
    )


def _build_group_moderator_note_prompt(
    conversation: Conversation,
    agent: Agent,
    content: str,
    member_summary: list[dict[str, Any]],
    history_messages: list[ChatMessage] | None = None,
    event_window: list[dict[str, Any]] | None = None,
) -> str:
    return prompt_builder_module._build_moderator_note_user_prompt(
        conversation=conversation,
        agent=agent,
        content=content,
        member_summary=member_summary,
        history_messages=history_messages,
        event_window=event_window,
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
        updated = strip_speaker_prefix_once(cleaned, prefix_candidates)
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
    return prompt_builder_module.build_group_context_messages(
        history_messages=history_messages,
        event_window=event_window,
    )


def build_chat_request(
    config: AdapterConfig,
    conversation: Conversation,
    agent: Agent,
    content: str,
    is_group: bool,
    thinking_enabled: bool = False,
    attachments: list[dict[str, Any]] | None = None,
    history_messages: list[ChatMessage] | None = None,
    member_summary: list[dict[str, Any]] | None = None,
    replied_agent_ids: list[str] | None = None,
    event_window: list[dict[str, Any]] | None = None,
    dispatch_state: dict[str, Any] | None = None,
) -> ChatRequest:
    messages = prompt_builder_module.build_chat_messages(
        conversation=conversation,
        agent=agent,
        content=content,
        is_group=is_group,
        history_messages=history_messages,
        member_summary=member_summary,
        replied_agent_ids=replied_agent_ids,
        event_window=event_window,
        dispatch_state=dispatch_state,
    )
    attachment_refs = [AttachmentRef.from_mapping(attachment) for attachment in attachments or []]
    return ChatRequest(
        config=config,
        messages=messages,
        agent_id=agent.id,
        agent_name=agent.name,
        user_text=content,
        is_group=is_group,
        attachments=attachment_refs,
        thinking=ThinkingConfig(enabled=thinking_enabled),
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
    messages = prompt_builder_module.build_moderator_note_messages(
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
                messages=messages,
                agent_id=agent.id,
                agent_name=agent.name,
                user_text=content,
                is_group=True,
                thinking=ThinkingConfig(enabled=False),
                metadata={
                    "purpose": "group_moderator_note",
                    "group_protocol_version": GROUP_RUNTIME_PROTOCOL_VERSION,
                    "thread_id": GROUP_RUNTIME_THREAD_ID,
                },
            )
        )
        .content,
    )


def _replace_chat_request_config(request: ChatRequest, config: AdapterConfig) -> ChatRequest:
    """Return a new ChatRequest with the config replaced (for endpoint fallback)."""
    return replace(request, config=config)


def _build_tool_runtime_context(
    db: Session,
    conversation: Conversation,
    agent: Agent,
) -> ToolRuntimeContext:
    settings = get_settings()
    search_config = build_search_runtime_config(settings)
    services = ToolServices(db_session_factory=lambda: db)
    return ToolRuntimeContext(
        conversation_id=conversation.id,
        agent_id=agent.id,
        agent_name=agent.name,
        is_group=conversation.type == "group",
        search_config=search_config,
        services=services,
        capabilities=ToolCapabilities(
            search=SearchCapability(config=search_config),
            services=services,
        ),
    )


def generate_agent_reply(
    db: Session,
    conversation: Conversation,
    agent: Agent,
    content: str,
    thinking_enabled: bool = False,
    attachments: list[dict[str, Any]] | None = None,
    history_messages: list[ChatMessage] | None = None,
    member_summary: list[dict[str, Any]] | None = None,
    replied_agent_ids: list[str] | None = None,
    event_window: list[dict[str, Any]] | None = None,
    dispatch_state: dict[str, Any] | None = None,
    on_tool_call: Any | None = None,
    on_tool_result: Any | None = None,
) -> ChatResponse | str:
    adapter_config = resolve_adapter_config(db, conversation, agent)
    tool_context = _build_tool_runtime_context(db, conversation, agent)
    chat_request = build_chat_request(
        config=adapter_config,
        conversation=conversation,
        agent=agent,
        content=content,
        is_group=conversation.type == "group",
        thinking_enabled=thinking_enabled,
        attachments=attachments,
        history_messages=history_messages,
        member_summary=member_summary,
        replied_agent_ids=replied_agent_ids,
        event_window=event_window,
        dispatch_state=dispatch_state,
    )
    chat_request.tools = get_tool_definitions(tool_context)

    return run_with_endpoint_fallback(
        adapter_config,
        lambda candidate_config: run_tool_loop(
            create_client(candidate_config),
            _replace_chat_request_config(chat_request, candidate_config),
            tool_context=tool_context,
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
        ),
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
        conversation_usage_summary=get_conversation_usage_summary(conversation),
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
    thinking_enabled: bool = False,
) -> MessageSendResult:
    if "members" not in conversation.__dict__:
        db.refresh(conversation, ["members"])

    base_time = utc_now_iso()
    normalized_attachments = [dict(attachment) for attachment in attachments or []]
    history_records = load_recent_history_messages(db, conversation.id)
    history_messages = build_history_messages(db, conversation, history_records)
    user_message = _build_persisted_message(
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
            outcome = run_single_group_agent_turn(
                db,
                conversation,
                agent,
                content,
                runtime_state,
                thinking_enabled=thinking_enabled,
                generate_agent_reply=generate_agent_reply,
                coerce_chat_response=_coerce_chat_response,
                ensure_displayable=_ensure_agent_response_displayable,
                build_persisted_message=_build_persisted_message,
                update_usage=_update_conversation_usage_from_response,
                filter_callable_kwargs=_filter_callable_kwargs,
            )
            if outcome.failed:
                warnings.append(
                    _build_contextual_error_payload(f"{agent.name} 回复失败", outcome.error or Exception())
                )
                continue
            if outcome.reply_message is not None:
                agent_messages.append(outcome.reply_message)
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
            reply_kwargs = _filter_callable_kwargs(
                generate_agent_reply,
                {
                    "thinking_enabled": thinking_enabled,
                    "attachments": normalized_attachments,
                    "history_messages": history_messages,
                },
            )
            reply_response = _coerce_chat_response(generate_agent_reply(
                db,
                conversation,
                agent,
                content,
                **reply_kwargs,
            ))
            _ensure_agent_response_displayable(
                reply_response,
                allow_thinking_display=thinking_enabled,
                agent_name=agent.name,
            )
            reply_message = _build_persisted_message(
                conversation_id=conversation.id,
                sender_type="agent",
                sender_id=agent.id,
                content=reply_response.content,
                attachments=[],
                response=reply_response,
                created_at=utc_now_iso(),
                agent=agent,
                allow_thinking_display=thinking_enabled,
            )
            db.add(reply_message)
            _update_conversation_usage_from_response(conversation, reply_response, agent=agent)
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
        conversation_usage_summary=usage_summary_to_dict(get_conversation_usage_summary(conversation)),
        warnings=warnings,
    )


def stream_group_message(
    db: Session,
    conversation: Conversation,
    content: str,
    attachments: list[dict[str, Any]] | None = None,
    thinking_enabled: bool = False,
) -> Generator[tuple[str, dict[str, Any]], None, None]:
    if conversation.type != "group":
        raise ValueError("message streaming is only supported for group conversations")

    if "members" not in conversation.__dict__:
        db.refresh(conversation, ["members"])

    base_time = utc_now_iso()
    normalized_attachments = [dict(attachment) for attachment in attachments or []]
    history_records = load_recent_history_messages(db, conversation.id)
    history_messages = build_history_messages(db, conversation, history_records)

    user_message = _build_persisted_message(
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
            "conversation_usage_summary": usage_summary_to_dict(runtime_state.conversation_usage_summary),
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
                    "conversation_usage_summary": usage_summary_to_dict(
                        get_conversation_usage_summary(conversation)
                    ),
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
                    "conversation_usage_summary": usage_summary_to_dict(
                        get_conversation_usage_summary(conversation)
                    ),
                    "error": _build_contextual_error_payload("群聊主持说明生成失败", exc),
                    "runtime_hooks": _get_runtime_hooks_payload(
                        event_window=runtime_state.event_window,
                        dispatch_state=runtime_state.dispatch_state,
                    ),
                },
            )
    for reply_agent_id in runtime_state.reply_agent_ids:
        agent = runtime_state.agent_map[reply_agent_id]
        tool_events_buffer: list[tuple[str, dict[str, Any]]] = []

        def on_tool_call(tc):
            tool_events_buffer.append(("tool_call", {
                "conversation_id": conversation.id,
                "agent_id": agent.id,
                "agent_name": agent.name,
                "tool_call_id": tc.id,
                "tool_name": tc.name,
                "tool_args": tc.arguments,
            }))

        def on_tool_result(tc, result):
            tool_events_buffer.append(("tool_result", {
                "conversation_id": conversation.id,
                "agent_id": agent.id,
                "agent_name": agent.name,
                "tool_call_id": tc.id,
                "tool_name": tc.name,
                "result_preview": result[:500],
            }))

        outcome = run_single_group_agent_turn(
            db,
            conversation,
            agent,
            content,
            runtime_state,
            thinking_enabled=thinking_enabled,
            generate_agent_reply=generate_agent_reply,
            coerce_chat_response=_coerce_chat_response,
            ensure_displayable=_ensure_agent_response_displayable,
            build_persisted_message=_build_persisted_message,
            update_usage=_update_conversation_usage_from_response,
            filter_callable_kwargs=_filter_callable_kwargs,
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
        )

        if outcome.failed:
            exc = outcome.error or Exception()
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
                        "conversation_usage_summary": usage_summary_to_dict(
                            get_conversation_usage_summary(conversation)
                        ),
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
                    "conversation_usage_summary": usage_summary_to_dict(
                        get_conversation_usage_summary(conversation)
                    ),
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
        reply_message = outcome.reply_message
        if reply_message is None:
            continue
        try:
            db.commit()
            db.refresh(reply_message)
            db.refresh(conversation)
            for event_type, event_payload in tool_events_buffer:
                yield (
                    event_type,
                    {
                        **event_payload,
                        "conversation_updated_at": conversation.updated_at,
                        "conversation_usage_summary": usage_summary_to_dict(
                            runtime_state.conversation_usage_summary
                        ),
                        "runtime_hooks": _get_runtime_hooks_payload(
                            event_window=runtime_state.event_window,
                            dispatch_state=runtime_state.dispatch_state,
                        ),
                    },
                )
            tool_events_buffer.clear()
            yield (
                "agent_message",
                {
                    "conversation_id": conversation.id,
                    "message": reply_message,
                    "conversation_updated_at": conversation.updated_at,
                    "conversation_usage_summary": usage_summary_to_dict(
                        runtime_state.conversation_usage_summary
                    ),
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
                    "conversation_usage_summary": usage_summary_to_dict(
                        runtime_state.conversation_usage_summary
                    ),
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
            "conversation_usage_summary": usage_summary_to_dict(runtime_state.conversation_usage_summary),
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
            "conversation_usage_summary": usage_summary_to_dict(runtime_state.conversation_usage_summary),
            "runtime_hooks": _get_runtime_hooks_payload(
                event_window=runtime_state.event_window,
                dispatch_state=runtime_state.dispatch_state,
            ),
        },
    )
