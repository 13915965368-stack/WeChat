from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    role_summary: Mapped[str] = mapped_column(Text, nullable=False)
    style_summary: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    avatar: Mapped[str] = mapped_column(String(32), nullable=False)
    avatar_image: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    theme_color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    theme_light: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    theme_soft: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    model_config_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    model_unavailable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pinned_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_conversation_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    model_config_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    runtime_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pinned_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)

    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMember.sort_order",
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class ConversationMember(Base):
    __tablename__ = "conversation_members"
    __table_args__ = (UniqueConstraint("conversation_id", "member_id", name="uq_conversation_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="members")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type: Mapped[str] = mapped_column(String(16), nullable=False)
    sender_id: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    api_format: Mapped[str] = mapped_column(String(32), nullable=False, default="openai")
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    use_full_url: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Stored as encrypted ciphertext with an in-band version prefix.
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    status_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    last_validated_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False, default="")


class LLMSettings(Base):
    __tablename__ = "llm_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    # Legacy column name is preserved for SQLite compatibility; values are encrypted.
    api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False, default="")
