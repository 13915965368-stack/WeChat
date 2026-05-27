from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.common import error_response, utc_now_iso
from app.db import get_db
from app.models import Agent, Conversation, ConversationMember, Message, ModelConfig
from app.schemas import (
    ConversationBulkDeleteRequest,
    ConversationBulkDeleteResponse,
    ConversationPinUpdateRequest,
    ConversationResponse,
    DirectConversationCreate,
    GroupConversationCreate,
)
from app.services.chat_service import build_group_runtime_metadata

router = APIRouter(tags=["conversations"])


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _resolve_model_config(db: Session, model_config_id: str | None) -> ModelConfig | None | bool:
    normalized = _normalize_optional(model_config_id)
    if normalized is None:
        return None

    model_config = db.get(ModelConfig, normalized)
    if model_config is None:
        return False
    return model_config


def _load_recent_source_messages(db: Session, conversation_id: str, rounds: int) -> list[Message]:
    message_limit = max(rounds, 0) * 2
    if message_limit <= 0:
        return []
    recent_messages = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(message_limit)
    ).all()
    return list(reversed(recent_messages))


def serialize_conversation(conversation: Conversation) -> ConversationResponse:
    member_ids = [member.member_id for member in sorted(conversation.members, key=lambda item: item.sort_order)]
    runtime_metadata = (
        build_group_runtime_metadata(conversation)
        if conversation.type == "group"
        else dict(conversation.runtime_metadata or {})
    )
    return ConversationResponse.model_validate(
        {
            "id": conversation.id,
            "type": conversation.type,
            "title": conversation.title,
            "member_ids": member_ids,
            "agent_id": conversation.agent_id,
            "source_conversation_id": conversation.source_conversation_id,
            "model_config_id": conversation.model_config_id,
            "runtime_metadata": runtime_metadata,
            "is_disabled": conversation.is_disabled,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "pinned": conversation.pinned,
            "pinned_at": conversation.pinned_at,
        }
    )


@router.get("/conversations", response_model=list[ConversationResponse])
def get_conversations(db: Session = Depends(get_db)) -> list[ConversationResponse]:
    conversations = db.scalars(
        select(Conversation)
        .options(selectinload(Conversation.members))
        .order_by(desc(Conversation.pinned), desc(Conversation.pinned_at), desc(Conversation.updated_at))
    ).all()
    return [serialize_conversation(conversation) for conversation in conversations]


@router.post("/conversations/direct", response_model=ConversationResponse, status_code=201)
def create_direct_conversation(payload: DirectConversationCreate, db: Session = Depends(get_db)):
    agent_id = payload.agent_id.strip()
    if not agent_id:
        return error_response(422, "validation_error", "agentId is required")

    title = payload.title.strip() if payload.title is not None else None
    if payload.title is not None and not title:
        return error_response(422, "validation_error", "title cannot be empty")

    model_config = _resolve_model_config(db, payload.model_config_id)
    if model_config is False:
        return error_response(404, "model_config_not_found", "Model config not found")

    agent = db.get(Agent, agent_id)
    if agent is None:
        return error_response(404, "agent_not_found", "Agent not found")

    existing = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.members))
        .where(Conversation.type == "direct", Conversation.agent_id == agent_id)
    )
    if existing is not None:
        existing.model_config_id = model_config.id if model_config is not None else None
        if title is not None:
            existing.title = title
        db.commit()
        db.refresh(existing)
        return JSONResponse(content=serialize_conversation(existing).model_dump(by_alias=True), status_code=200)

    now = utc_now_iso()
    conversation = Conversation(
        id=uuid4().hex,
        type="direct",
        title=title or f"与 {agent.name} 的新对话",
        agent_id=agent.id,
        model_config_id=model_config.id if model_config is not None else None,
        runtime_metadata={},
        is_disabled=False,
        pinned=False,
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    db.flush()
    db.add_all(
        [
            ConversationMember(conversation_id=conversation.id, member_id="user", sort_order=0),
            ConversationMember(conversation_id=conversation.id, member_id=agent.id, sort_order=1),
        ]
    )
    db.commit()
    created = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.members))
        .where(Conversation.id == conversation.id)
    )
    return serialize_conversation(created)


@router.patch("/conversations/{conversation_id}/pin", response_model=ConversationResponse)
def update_conversation_pin(
    conversation_id: str,
    payload: ConversationPinUpdateRequest,
    db: Session = Depends(get_db),
):
    conversation = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.members))
        .where(Conversation.id == conversation_id)
    )
    if conversation is None:
        return error_response(404, "conversation_not_found", "Conversation not found")

    conversation.pinned = payload.pinned
    conversation.pinned_at = utc_now_iso() if payload.pinned else None
    db.commit()
    db.refresh(conversation)

    refreshed = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.members))
        .where(Conversation.id == conversation_id)
    )
    return serialize_conversation(refreshed)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conversation = db.scalar(
        select(Conversation)
        .options(
            selectinload(Conversation.members),
            selectinload(Conversation.messages),
        )
        .where(Conversation.id == conversation_id)
    )
    if conversation is None:
        return error_response(404, "conversation_not_found", "Conversation not found")

    db.delete(conversation)
    db.commit()
    return None


@router.post("/conversations/bulk-delete", response_model=ConversationBulkDeleteResponse)
def bulk_delete_conversations(payload: ConversationBulkDeleteRequest, db: Session = Depends(get_db)):
    cleaned_ids = []
    for conversation_id in payload.conversation_ids:
        trimmed = conversation_id.strip()
        if trimmed and trimmed not in cleaned_ids:
            cleaned_ids.append(trimmed)

    if not cleaned_ids:
        return error_response(422, "validation_error", "conversationIds cannot be empty")

    conversations = db.scalars(
        select(Conversation)
        .options(
            selectinload(Conversation.members),
            selectinload(Conversation.messages),
        )
        .where(Conversation.id.in_(cleaned_ids))
    ).all()
    if len(conversations) != len(cleaned_ids):
        return error_response(404, "conversation_not_found", "Conversation not found")

    for conversation in conversations:
        db.delete(conversation)
    db.commit()

    remaining_ids = db.scalars(
        select(Conversation.id)
        .order_by(desc(Conversation.pinned), desc(Conversation.pinned_at), desc(Conversation.updated_at))
    ).all()
    return ConversationBulkDeleteResponse(
        deleted_count=len(cleaned_ids),
        remaining_conversation_ids=remaining_ids,
    )


@router.post("/conversations/group", response_model=ConversationResponse, status_code=201)
def create_group_conversation(payload: GroupConversationCreate, db: Session = Depends(get_db)):
    title = payload.title.strip()
    if not title:
        return error_response(422, "validation_error", "title cannot be empty")

    cleaned_member_ids = [member_id.strip() for member_id in payload.member_ids if member_id.strip()]
    if len(cleaned_member_ids) < 2 or len(cleaned_member_ids) != len(set(cleaned_member_ids)):
        return error_response(422, "validation_error", "memberIds must contain at least two unique agent ids")

    source_conversation_id = _normalize_optional(payload.source_conversation_id)
    source_conversation = None
    if source_conversation_id is not None:
        source_conversation = db.scalar(
            select(Conversation)
            .options(selectinload(Conversation.members))
            .where(Conversation.id == source_conversation_id)
        )
        if source_conversation is None or source_conversation.type != "direct":
            return error_response(422, "validation_error", "sourceConversationId must reference a direct conversation")

    agents = db.scalars(select(Agent).where(Agent.id.in_(cleaned_member_ids))).all()
    if len(agents) != len(cleaned_member_ids):
        return error_response(422, "validation_error", "memberIds contains invalid agent ids")

    now = utc_now_iso()
    conversation = Conversation(
        id=uuid4().hex,
        type="group",
        title=title,
        agent_id=None,
        source_conversation_id=source_conversation_id,
        runtime_metadata={},
        is_disabled=False,
        pinned=False,
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    db.flush()
    conversation.runtime_metadata = build_group_runtime_metadata(conversation)
    members = [ConversationMember(conversation_id=conversation.id, member_id="user", sort_order=0)]
    members.extend(
        ConversationMember(conversation_id=conversation.id, member_id=member_id, sort_order=index)
        for index, member_id in enumerate(cleaned_member_ids, start=1)
    )
    db.add_all(members)
    if source_conversation is not None and payload.include_context and payload.context_rounds > 0:
        copied_messages = [
            Message(
                id=uuid4().hex,
                conversation_id=conversation.id,
                sender_type=message.sender_type,
                sender_id=message.sender_id,
                content=message.content,
                attachments=list(message.attachments or []),
                created_at=message.created_at,
            )
            for message in _load_recent_source_messages(db, source_conversation.id, payload.context_rounds)
        ]
        if copied_messages:
            db.add_all(copied_messages)
            conversation.updated_at = copied_messages[-1].created_at
    db.commit()
    created = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.members))
        .where(Conversation.id == conversation.id)
    )
    return serialize_conversation(created)
