from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.common import error_response
from app.db import get_db
from app.llm.endpoint_fallback import EndpointFallbackError
from app.llm.validator import LLMStreamInterruptedError, LLMValidationError
from app.models import Conversation, Message
from app.schemas import (
    ErrorDetail,
    MessageCreate,
    MessageResponse,
    MessageSendResponse,
    MessageStreamEvent,
    MessageStreamPayload,
    MessageStreamRuntimeHooks,
    MessagesPageResponse,
)
from app.services.chat_service import send_message, stream_group_message

router = APIRouter(tags=["messages"])


def serialize_message(message: Message) -> MessageResponse:
    return MessageResponse.model_validate(message)


def serialize_stream_event(
    *,
    event: str,
    conversation_id: str,
    message: Message | None = None,
    conversation_updated_at: str | None = None,
    error: dict[str, str] | None = None,
    runtime_hooks: dict[str, object] | None = None,
) -> str:
    payload = MessageStreamPayload(
        conversation_id=conversation_id,
        message=serialize_message(message) if message is not None else None,
        conversation_updated_at=conversation_updated_at,
        error=ErrorDetail(**error) if error is not None else None,
        runtime_hooks=MessageStreamRuntimeHooks(**runtime_hooks) if runtime_hooks is not None else None,
    )
    stream_event = MessageStreamEvent(event=event, payload=payload)
    return f"event: {event}\ndata: {json.dumps(stream_event.model_dump(by_alias=True), ensure_ascii=False)}\n\n"


@router.get("/messages", response_model=MessagesPageResponse)
def get_messages(
    conversation_id: str = Query(..., alias="conversationId"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    trimmed_conversation_id = conversation_id.strip()
    if not trimmed_conversation_id:
        return error_response(422, "validation_error", "conversationId is required")

    conversation = db.get(Conversation, trimmed_conversation_id)
    if conversation is None:
        return error_response(404, "conversation_not_found", "Conversation not found")

    total = db.scalar(
        select(func.count()).where(Message.conversation_id == trimmed_conversation_id)
    )
    page_items = db.scalars(
        select(Message)
        .where(Message.conversation_id == trimmed_conversation_id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MessagesPageResponse(
        items=[serialize_message(message) for message in page_items],
        limit=limit,
        offset=offset,
        has_more=offset + len(page_items) < total,
    )


@router.post("/messages", response_model=MessageSendResponse, status_code=201)
def post_message(payload: MessageCreate, db: Session = Depends(get_db)):
    conversation_id = payload.conversation_id.strip()
    content = payload.content.strip()
    attachments = [attachment.model_dump(by_alias=True) for attachment in payload.attachments]

    if not conversation_id:
        return error_response(422, "validation_error", "conversationId is required")
    if not content:
        return error_response(422, "validation_error", "content cannot be empty")
    if len(content) > 4000:
        return error_response(422, "validation_error", "content is too long")

    conversation = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.members))
        .where(Conversation.id == conversation_id)
    )
    if conversation is None:
        return error_response(404, "conversation_not_found", "Conversation not found")
    if conversation.is_disabled:
        return error_response(409, "conversation_inactive", "Conversation is inactive")

    try:
        result = send_message(db, conversation, content, attachments=attachments)
    except LLMValidationError as exc:
        return error_response(exc.status_code, exc.code, str(exc))
    except LLMStreamInterruptedError as exc:
        return error_response(422, "model_stream_interrupted", str(exc))
    except EndpointFallbackError as exc:
        return error_response(422, "model_endpoint_failed", str(exc))
    except ValueError as exc:
        return error_response(422, "model_request_failed", str(exc))

    return MessageSendResponse(
        user_message=serialize_message(result.user_message),
        agent_messages=[serialize_message(message) for message in result.agent_messages],
        conversation_updated_at=result.conversation_updated_at,
        warnings=result.warnings,
    )


@router.post("/messages/stream")
def post_message_stream(payload: MessageCreate, db: Session = Depends(get_db)):
    conversation_id = payload.conversation_id.strip()
    content = payload.content.strip()
    attachments = [attachment.model_dump(by_alias=True) for attachment in payload.attachments]

    if not conversation_id:
        return error_response(422, "validation_error", "conversationId is required")
    if not content:
        return error_response(422, "validation_error", "content cannot be empty")
    if len(content) > 4000:
        return error_response(422, "validation_error", "content is too long")

    conversation = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.members))
        .where(Conversation.id == conversation_id)
    )
    if conversation is None:
        return error_response(404, "conversation_not_found", "Conversation not found")
    if conversation.is_disabled:
        return error_response(409, "conversation_inactive", "Conversation is inactive")
    if conversation.type != "group":
        return error_response(
            409,
            "conversation_not_streamable",
            "Streaming is only supported for group conversations",
        )

    def event_generator():
        for event_name, payload_data in stream_group_message(
            db,
            conversation,
            content,
            attachments=attachments,
        ):
            yield serialize_stream_event(
                event=event_name,
                conversation_id=payload_data["conversation_id"],
                message=payload_data.get("message"),
                conversation_updated_at=payload_data.get("conversation_updated_at"),
                error=payload_data.get("error"),
                runtime_hooks=payload_data.get("runtime_hooks"),
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
