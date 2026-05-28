from __future__ import annotations

from abc import ABC
import json
from typing import Any, Iterator

import httpx

from app.llm.schemas import ChatRequest, ChatResponse, ValidationRequest, ValidationResult
from app.llm.validator import (
    LLMStreamProtocolError,
    LLMValidationError,
    validate_chat_request,
    validate_validation_request,
)

STYLE_PREFIX = {
    "architect": "我先从结构上拆一下：",
    "critic": "我先提醒几个风险点：",
    "writer": "我先帮你整理表达：",
}

IMAGE_INPUT_HINTS = ("image", "image_url", "vision", "multimodal")
UNSUPPORTED_HINTS = (
    "not support",
    "unsupported",
    "only support",
    "text-only",
    "text only",
    "not enabled",
    "cannot process",
)


def build_local_reply(
    agent_id: str,
    agent_name: str,
    user_text: str,
    is_group: bool,
    *,
    has_system_prompt: bool = False,
    history_count: int = 0,
) -> str:
    prefix = STYLE_PREFIX.get(agent_id, f"{agent_name}：")
    if agent_id == "architect":
        suffix = f"先把问题拆成几个可执行部分，再围绕“{user_text}”推进。"
    elif agent_id == "critic":
        suffix = f"这件事里最需要先看的，是“{user_text}”背后的风险和边界。"
    elif agent_id == "writer":
        suffix = f"我先帮你把“{user_text}”整理成更顺的表达，再往下展开。"
    else:
        suffix = f"我先围绕“{user_text}”给出一个可执行回应。"
    context_hints = []
    if has_system_prompt:
        context_hints.append("已参考系统提示词")
    if history_count > 0:
        context_hints.append(f"已参考{history_count}条历史消息")

    reply = f"{prefix}{suffix}" if not is_group else f"{agent_name}：{prefix}{suffix}"
    if not context_hints:
        return reply
    return f"{reply}（{'，'.join(context_hints)}）"


class BaseLLMAdapter(ABC):
    adapter_name = "base"
    request_timeout = 60.0
    stream_connect_timeout = 10.0
    stream_read_timeout = 30.0
    stream_write_timeout = 10.0
    stream_pool_timeout = 10.0

    def __init__(self, config):
        self.config = config

    def validate(self, request: ValidationRequest | None = None) -> ValidationResult:
        target_request = request or ValidationRequest(config=self.config)
        validated = validate_validation_request(target_request)
        return ValidationResult(
            ok=True,
            provider=validated.config.provider,
            model=validated.config.model,
            status_message="Validation skipped in local mock mode",
            capabilities=validated.config.capabilities,
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        validated = validate_chat_request(request)
        has_system_prompt = any(message.role == "system" for message in validated.messages)
        history_count = max(sum(1 for message in validated.messages if message.role != "system") - 1, 0)
        return ChatResponse(
            content=build_local_reply(
                agent_id=validated.agent_id,
                agent_name=validated.agent_name,
                user_text=validated.user_text,
                is_group=validated.is_group,
                has_system_prompt=has_system_prompt,
                history_count=history_count,
            ),
            provider=validated.config.provider,
            model=validated.config.model,
            raw={"adapter": self.adapter_name, "mode": "local-mock"},
        )

    def chat_with_images(self, request: ChatRequest) -> ChatResponse:
        validated = validate_chat_request(request)
        return self.chat(validated)

    def _build_default_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def _require_api_key(self) -> str:
        api_key = self.config.api_key.strip()
        if not api_key:
            raise LLMValidationError("apiKey cannot be empty")
        return api_key

    def _resolve_url(self, path: str) -> str:
        base_url = (self.config.base_url or "").strip()
        if not base_url:
            raise LLMValidationError("baseUrl cannot be empty")
        if self.config.use_full_url:
            return base_url
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        try:
            response = httpx.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.request_timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self._raise_http_error(exc)
        except httpx.RequestError as exc:
            raise ValueError(f"{self.adapter_name} request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ValueError(f"{self.adapter_name} returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise ValueError(f"{self.adapter_name} returned unexpected response shape")
        return data

    def _build_stream_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self.stream_connect_timeout,
            read=self.stream_read_timeout,
            write=self.stream_write_timeout,
            pool=self.stream_pool_timeout,
        )

    def _stream_sse_events(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> Iterator[dict[str, Any]]:
        try:
            with httpx.stream(
                "POST",
                url,
                json=payload,
                headers=headers,
                timeout=self._build_stream_timeout(),
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" not in content_type.lower():
                    raise LLMStreamProtocolError(
                        f"{self.adapter_name} returned non-SSE response: {content_type or 'unknown content-type'}"
                    )
                for raw_line in response.iter_lines():
                    line = raw_line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    data_text = line[5:].strip()
                    if not data_text or data_text == "[DONE]":
                        continue
                    try:
                        parsed = json.loads(data_text)
                    except ValueError as exc:
                        raise LLMStreamProtocolError(f"{self.adapter_name} returned invalid SSE JSON") from exc
                    if not isinstance(parsed, dict):
                        raise LLMStreamProtocolError(
                            f"{self.adapter_name} returned unexpected SSE event shape"
                        )
                    yield parsed
        except httpx.HTTPStatusError as exc:
            self._raise_http_error(exc)
        except httpx.RequestError as exc:
            raise LLMStreamProtocolError(f"{self.adapter_name} request failed: {exc}") from exc

    def _raise_http_error(self, exc: httpx.HTTPStatusError) -> None:
        detail = self._extract_error_detail(exc.response)
        if self._is_remote_image_unsupported(exc.response, detail):
            raise LLMValidationError(
                "image attachments are not supported by the current model",
                code="IMAGE_NOT_SUPPORTED",
            ) from exc
        if detail:
            raise ValueError(
                f"{self.adapter_name} request failed with status {exc.response.status_code}: {detail}"
            ) from exc
        raise ValueError(
            f"{self.adapter_name} request failed with status {exc.response.status_code}"
        ) from exc

    def _extract_error_detail(self, response: httpx.Response) -> str:
        details: list[str] = []

        def collect(value: Any) -> None:
            if isinstance(value, str):
                text = value.strip()
                if text:
                    details.append(text)
                return
            if isinstance(value, dict):
                preferred_keys = ("message", "code", "type", "detail", "error")
                for key in preferred_keys:
                    if key in value:
                        collect(value[key])
                for key, item in value.items():
                    if key not in preferred_keys:
                        collect(item)
                return
            if isinstance(value, list):
                for item in value:
                    collect(item)

        try:
            collect(response.json())
        except ValueError:
            pass

        raw_text = response.text.strip()
        if raw_text:
            details.append(raw_text)
        return " | ".join(dict.fromkeys(details))

    def _is_remote_image_unsupported(self, response: httpx.Response, detail: str) -> bool:
        if response.status_code not in (400, 415, 422):
            return False
        normalized_detail = detail.lower()
        return any(token in normalized_detail for token in IMAGE_INPUT_HINTS) and any(
            token in normalized_detail for token in UNSUPPORTED_HINTS
        )

    def _serialize_messages(self, request: ChatRequest) -> list[dict[str, str]]:
        return [
            {"role": message.role, "content": message.content.strip()}
            for message in request.messages
            if message.content.strip()
        ]

    def _split_system_and_messages(self, request: ChatRequest) -> tuple[str | None, list[dict[str, str]]]:
        system_parts: list[str] = []
        messages: list[dict[str, str]] = []
        for message in request.messages:
            content = message.content.strip()
            if not content and not message.tool_calls:
                continue
            if message.role == "system":
                system_parts.append(content)
                continue
            if message.role == "tool" or message.tool_calls:
                continue
            messages.append({"role": message.role, "content": content})
        system_prompt = "\n\n".join(system_parts).strip()
        return (system_prompt or None, messages)

    def _extract_text_content(self, value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str):
                    text = item.strip()
                elif isinstance(item, dict):
                    text = str(item.get("text", "")).strip()
                else:
                    text = ""
                if text:
                    parts.append(text)
            return "\n".join(parts).strip()
        if isinstance(value, dict):
            return str(value.get("text", "")).strip()
        return ""
