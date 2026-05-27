from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(slots=True)
class AdapterCapabilities:
    supports_image_input: bool = False
    supports_file_input: bool = False
    supports_streaming: bool = False
    context_window: int | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "AdapterCapabilities":
        if not value:
            return cls()
        return cls(
            supports_image_input=bool(value.get("supports_image_input", value.get("supportsImageInput", False))),
            supports_file_input=bool(value.get("supports_file_input", value.get("supportsFileInput", False))),
            supports_streaming=bool(value.get("supports_streaming", value.get("supportsStreaming", False))),
            context_window=value.get("context_window", value.get("contextWindow")),
        )


@dataclass(slots=True)
class AttachmentRef:
    attachment_id: str = ""
    kind: str = "image"
    mime_type: str = ""
    name: str | None = None
    size: int | None = None
    preview_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "AttachmentRef":
        return cls(
            attachment_id=str(value.get("attachment_id", value.get("attachmentId", ""))),
            kind=str(value.get("kind", "image")),
            mime_type=str(value.get("mime_type", value.get("mimeType", ""))),
            name=value.get("name"),
            size=value.get("size"),
            preview_url=value.get("preview_url", value.get("previewUrl")),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass(slots=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(slots=True)
class AdapterConfig:
    provider: str
    model: str
    api_key: str = ""
    api_format: str | None = None
    base_url: str | None = None
    use_full_url: bool = False
    capabilities: AdapterCapabilities = field(default_factory=AdapterCapabilities)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ValidationRequest:
    config: AdapterConfig


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    provider: str
    model: str
    status_message: str
    capabilities: AdapterCapabilities = field(default_factory=AdapterCapabilities)


@dataclass(slots=True)
class ChatRequest:
    config: AdapterConfig
    messages: list[ChatMessage]
    agent_id: str
    agent_name: str
    user_text: str
    system_prompt: str = ""
    is_group: bool = False
    attachments: list[AttachmentRef] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatResponse:
    content: str
    model: str
    provider: str
    finish_reason: str = "stop"
    raw: dict[str, Any] = field(default_factory=dict)
