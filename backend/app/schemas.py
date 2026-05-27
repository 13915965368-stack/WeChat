from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class APIModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AgentResponse(APIModel):
    id: str
    name: str
    role_summary: str
    style_summary: str
    system_prompt: str
    avatar: str
    avatar_image: str | None = None
    theme_color: str | None = None
    theme_light: str | None = None
    theme_soft: str | None = None
    model_config_id: str | None = None
    model_unavailable: bool = False
    is_template: bool = False
    pinned: bool = False
    pinned_at: str | None = None


class AgentUpdateRequest(APIModel):
    name: str
    role_summary: str
    style_summary: str
    system_prompt: str
    avatar: str
    avatar_image: str | None = None
    theme_color: str | None = None
    theme_light: str | None = None
    theme_soft: str | None = None


class ConversationResponse(APIModel):
    id: str
    type: str
    title: str
    member_ids: list[str]
    agent_id: str | None = None
    source_conversation_id: str | None = None
    model_config_id: str | None = None
    runtime_metadata: dict[str, Any] = Field(default_factory=dict)
    is_disabled: bool = False
    created_at: str
    updated_at: str
    pinned: bool = False
    pinned_at: str | None = None


class ConversationPinUpdateRequest(APIModel):
    pinned: bool


class ConversationBulkDeleteRequest(APIModel):
    conversation_ids: list[str] = Field(alias="conversationIds")


class ConversationBulkDeleteResponse(APIModel):
    deleted_count: int
    remaining_conversation_ids: list[str]


class AttachmentResponse(APIModel):
    attachment_id: str = Field(alias="attachmentId")
    kind: str = "image"
    mime_type: str = Field(alias="mimeType")
    name: str | None = None
    size: int | None = None
    preview_url: str | None = Field(default=None, alias="previewUrl")
    expires_at: str | None = Field(default=None, alias="expiresAt")
    metadata: dict[str, Any] = Field(default_factory=dict)


class MessageResponse(APIModel):
    id: str
    conversation_id: str
    sender_type: str
    sender_id: str
    content: str
    attachments: list[AttachmentResponse] = Field(default_factory=list)
    created_at: str


class MessagesPageResponse(APIModel):
    items: list[MessageResponse]
    limit: int
    offset: int
    has_more: bool


class DirectConversationCreate(APIModel):
    agent_id: str = Field(alias="agentId")
    title: str | None = None
    model_config_id: str | None = Field(default=None, alias="modelConfigId")


class GroupConversationCreate(APIModel):
    title: str
    member_ids: list[str] = Field(alias="memberIds")
    source_conversation_id: str | None = Field(default=None, alias="sourceConversationId")
    include_context: bool = Field(default=False, alias="includeContext")
    context_rounds: int = Field(default=0, alias="contextRounds")


class MessageCreate(APIModel):
    conversation_id: str = Field(alias="conversationId")
    content: str
    attachments: list[AttachmentResponse] = Field(default_factory=list)


class MessageSendResponse(APIModel):
    user_message: MessageResponse
    agent_messages: list[MessageResponse]
    conversation_updated_at: str
    warnings: list[ErrorDetail] = Field(default_factory=list)


CurrentMessageStreamEventType: TypeAlias = Literal[
    "user_message",
    "moderator_note_ready",
    "agent_message",
    "conversation_updated",
    "done",
    "error",
]
ReservedFutureMessageStreamEventType: TypeAlias = Literal[
    "agent_thinking",
    "tool_call",
    "tool_result",
    "dispatch_progress",
]
MessageStreamEventType: TypeAlias = (
    CurrentMessageStreamEventType | ReservedFutureMessageStreamEventType
)
CurrentMessageStreamDispatchStrategy: TypeAlias = Literal["broadcast_chain"]
ReservedFutureMessageStreamDispatchStrategy: TypeAlias = Literal[
    "round_robin",
    "parallel_fan_out",
    "manual_handoff",
]
MessageStreamDispatchStrategy: TypeAlias = (
    CurrentMessageStreamDispatchStrategy | ReservedFutureMessageStreamDispatchStrategy
)


class MessageStreamRuntimeHooks(APIModel):
    dispatch_strategy: MessageStreamDispatchStrategy
    trigger_event_type: MessageStreamEventType
    reserved_event_types: list[CurrentMessageStreamEventType] = Field(default_factory=list)
    reserved_dispatch_strategies: list[CurrentMessageStreamDispatchStrategy] = Field(default_factory=list)
    reserved_future_event_types: list[ReservedFutureMessageStreamEventType] = Field(default_factory=list)
    reserved_future_dispatch_strategies: list[ReservedFutureMessageStreamDispatchStrategy] = Field(
        default_factory=list
    )


class MessageStreamPayload(APIModel):
    conversation_id: str
    message: MessageResponse | None = None
    conversation_updated_at: str | None = None
    error: ErrorDetail | None = None
    runtime_hooks: MessageStreamRuntimeHooks | None = None


class MessageStreamEvent(APIModel):
    event: MessageStreamEventType
    payload: MessageStreamPayload


class LLMRuntimeConfigResponse(APIModel):
    provider: str
    model: str
    has_api_key: bool


class LLMSettingsUpdateRequest(APIModel):
    provider: str
    model: str
    api_key: str = Field(default="", alias="apiKey")


class AgentPinUpdateRequest(APIModel):
    pinned: bool


class ModelConfigCapabilities(APIModel):
    supports_image_input: bool = Field(default=False, alias="supportsImageInput")
    supports_file_input: bool = Field(default=False, alias="supportsFileInput")
    supports_streaming: bool = Field(default=False, alias="supportsStreaming")
    context_window: int | None = Field(default=None, alias="contextWindow")


class ModelConfigResponse(APIModel):
    id: str
    provider: str
    model: str
    display_name: str = Field(alias="displayName")
    api_format: str = Field(alias="apiFormat")
    base_url: str | None = Field(default=None, alias="baseUrl")
    use_full_url: bool = Field(default=False, alias="useFullUrl")
    status: str
    status_message: str | None = Field(default=None, alias="statusMessage")
    capabilities: ModelConfigCapabilities = Field(default_factory=ModelConfigCapabilities)
    api_key_configured: bool = Field(default=False, alias="apiKeyConfigured")
    last_validated_at: str | None = Field(default=None, alias="lastValidatedAt")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ModelConfigCreateRequest(APIModel):
    provider: str
    model: str
    display_name: str = Field(alias="displayName")
    api_format: str = Field(default="openai", alias="apiFormat")
    base_url: str | None = Field(default=None, alias="baseUrl")
    use_full_url: bool = Field(default=False, alias="useFullUrl")
    api_key: str = Field(default="", alias="apiKey")
    capabilities: ModelConfigCapabilities = Field(default_factory=ModelConfigCapabilities)


class ModelConfigUpdateRequest(APIModel):
    provider: str | None = None
    model: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")
    api_format: str | None = Field(default=None, alias="apiFormat")
    base_url: str | None = Field(default=None, alias="baseUrl")
    use_full_url: bool | None = Field(default=None, alias="useFullUrl")
    api_key: str | None = Field(default=None, alias="apiKey")
    capabilities: ModelConfigCapabilities | None = None


class AgentCreateRequest(APIModel):
    name: str
    role_summary: str = Field(alias="roleSummary")
    style_summary: str = Field(alias="styleSummary")
    system_prompt: str = Field(alias="systemPrompt")
    avatar: str
    avatar_image: str | None = Field(default=None, alias="avatarImage")
    theme_color: str | None = Field(default=None, alias="themeColor")
    theme_light: str | None = Field(default=None, alias="themeLight")
    theme_soft: str | None = Field(default=None, alias="themeSoft")
    model_config_id: str | None = Field(default=None, alias="modelConfigId")


class AgentModelBindingRequest(APIModel):
    model_config_id: str | None = Field(default=None, alias="modelConfigId")


class AttachmentUploadResponse(APIModel):
    attachment_id: str = Field(alias="attachmentId")
    mime_type: str = Field(alias="mimeType")
    preview_url: str = Field(alias="previewUrl")
    expires_at: str | None = Field(default=None, alias="expiresAt")
