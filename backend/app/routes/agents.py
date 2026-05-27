from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.common import error_response, utc_now_iso
from app.db import get_db
from app.models import Agent, Conversation, ConversationMember, ModelConfig
from app.schemas import (
    AgentCreateRequest,
    AgentModelBindingRequest,
    AgentPinUpdateRequest,
    AgentResponse,
    AgentUpdateRequest,
)

PROTECTED_AGENT_IDS = {"architect", "critic", "writer", "blank-agent"}

router = APIRouter(tags=["agents"])


def _serialize_agent(agent: Agent) -> AgentResponse:
    return AgentResponse.model_validate(agent)


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _validate_agent_payload(payload: AgentUpdateRequest | AgentCreateRequest, *, require_system_prompt: bool) -> str | None:
    if not payload.name.strip():
        return "name cannot be empty"
    if not payload.role_summary.strip():
        return "roleSummary cannot be empty"
    if not payload.style_summary.strip():
        return "styleSummary cannot be empty"
    if require_system_prompt and not payload.system_prompt.strip():
        return "systemPrompt cannot be empty"
    if not payload.avatar.strip():
        return "avatar cannot be empty"
    return None


def _resolve_model_config(db: Session, model_config_id: str | None) -> ModelConfig | None | bool:
    normalized = _normalize_optional(model_config_id)
    if normalized is None:
        return None

    model_config = db.get(ModelConfig, normalized)
    if model_config is None:
        return False
    return model_config


def _apply_model_binding(agent: Agent, model_config: ModelConfig | None) -> None:
    if model_config is None:
        agent.model_config_id = None
        agent.model_unavailable = False
        return

    agent.model_config_id = model_config.id
    agent.model_unavailable = model_config.status != "available"


@router.get("/agents", response_model=list[AgentResponse])
def get_agents(db: Session = Depends(get_db)) -> list[AgentResponse]:
    agents = db.scalars(
        select(Agent).order_by(desc(Agent.pinned), desc(Agent.pinned_at), Agent.id.asc())
    ).all()
    return [_serialize_agent(agent) for agent in agents]


@router.post("/agents", response_model=AgentResponse, status_code=201)
def create_agent(payload: AgentCreateRequest, db: Session = Depends(get_db)):
    validation_error = _validate_agent_payload(payload, require_system_prompt=False)
    if validation_error is not None:
        return error_response(422, "validation_error", validation_error)

    model_config = _resolve_model_config(db, payload.model_config_id)
    if model_config is False:
        return error_response(404, "model_config_not_found", "Model config not found")

    agent = Agent(
        id=f"agent-{uuid4().hex}",
        name=payload.name.strip(),
        role_summary=payload.role_summary.strip(),
        style_summary=payload.style_summary.strip(),
        system_prompt=payload.system_prompt.strip(),
        avatar=payload.avatar.strip(),
        avatar_image=_normalize_optional(payload.avatar_image),
        theme_color=_normalize_optional(payload.theme_color),
        theme_light=_normalize_optional(payload.theme_light),
        theme_soft=_normalize_optional(payload.theme_soft),
        is_template=False,
        pinned=False,
        pinned_at=None,
    )
    _apply_model_binding(agent, model_config)

    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _serialize_agent(agent)


@router.put("/agents/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: str, payload: AgentUpdateRequest, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        return error_response(404, "agent_not_found", "Agent not found")

    validation_error = _validate_agent_payload(payload, require_system_prompt=True)
    if validation_error is not None:
        return error_response(422, "validation_error", validation_error)

    agent.name = payload.name.strip()
    agent.role_summary = payload.role_summary.strip()
    agent.style_summary = payload.style_summary.strip()
    agent.system_prompt = payload.system_prompt.strip()
    agent.avatar = payload.avatar.strip()
    agent.avatar_image = _normalize_optional(payload.avatar_image)
    agent.theme_color = _normalize_optional(payload.theme_color)
    agent.theme_light = _normalize_optional(payload.theme_light)
    agent.theme_soft = _normalize_optional(payload.theme_soft)

    db.commit()
    db.refresh(agent)
    return _serialize_agent(agent)


@router.patch("/agents/{agent_id}/model", response_model=AgentResponse)
def update_agent_model_binding(
    agent_id: str,
    payload: AgentModelBindingRequest,
    db: Session = Depends(get_db),
):
    agent = db.get(Agent, agent_id)
    if agent is None:
        return error_response(404, "agent_not_found", "Agent not found")

    model_config = _resolve_model_config(db, payload.model_config_id)
    if model_config is False:
        return error_response(404, "model_config_not_found", "Model config not found")

    _apply_model_binding(agent, model_config)
    db.commit()
    db.refresh(agent)
    return _serialize_agent(agent)


@router.delete("/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        return error_response(404, "agent_not_found", "Agent not found")
    if agent.id in PROTECTED_AGENT_IDS:
        return error_response(403, "agent_protected", "Seed agents cannot be deleted")

    direct_conversations = db.scalars(
        select(Conversation)
        .options(selectinload(Conversation.members), selectinload(Conversation.messages))
        .where(Conversation.type == "direct", Conversation.agent_id == agent.id)
    ).all()
    for conversation in direct_conversations:
        db.delete(conversation)

    group_conversation_ids = db.scalars(
        select(Conversation.id)
        .join(Conversation.members)
        .where(Conversation.type == "group", ConversationMember.member_id == agent.id)
    ).all()
    if group_conversation_ids:
        group_conversations = db.scalars(
            select(Conversation)
            .options(selectinload(Conversation.members))
            .where(Conversation.id.in_(group_conversation_ids))
        ).all()
        for conversation in group_conversations:
            remaining_agent_members = [
                member for member in conversation.members if member.member_id not in {"user", agent.id}
            ]
            for member in list(conversation.members):
                if member.member_id == agent.id:
                    db.delete(member)
            conversation.is_disabled = len(remaining_agent_members) == 0
            conversation.updated_at = utc_now_iso()

    db.delete(agent)
    db.commit()
    return None


@router.patch("/agents/{agent_id}/pin", response_model=AgentResponse)
def update_agent_pin(agent_id: str, payload: AgentPinUpdateRequest, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        return error_response(404, "agent_not_found", "Agent not found")

    agent.pinned = payload.pinned
    agent.pinned_at = utc_now_iso() if payload.pinned else None

    db.commit()
    db.refresh(agent)
    return _serialize_agent(agent)
