from __future__ import annotations

import httpx
import pytest

import app.services.chat_service as chat_service_module
from app.llm.adapters.anthropic import AnthropicAdapter
from app.llm.adapters.custom import CustomCompatibleAdapter
from app.llm.adapters.gemini import GeminiAdapter
from app.llm.adapters.openai_compatible import OpenAICompatibleAdapter
from app.llm.client_factory import create_client
from app.llm.endpoint_fallback import EndpointFallbackError, resolve_endpoint_candidates, run_with_endpoint_fallback
from app.llm.schemas import (
    AdapterCapabilities,
    AdapterConfig,
    AttachmentRef,
    ChatMessage,
    ChatRequest,
    ChatResponse,
)
from app.llm.validator import (
    LLMStreamInterruptedError,
    LLMValidationError,
    normalize_adapter_config,
    validate_chat_request,
)


class FakeStreamResponse:
    def __init__(self, *, url_text: str, lines: list[str], status_code: int = 200, json_body=None) -> None:
        self.status_code = status_code
        self.headers = {"content-type": "text/event-stream"}
        self.text = "\n".join(lines)
        self._lines = lines
        self._json_body = json_body
        self.request = httpx.Request("POST", url_text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "stream request failed",
                request=self.request,
                response=httpx.Response(
                    self.status_code,
                    json=self._json_body,
                    request=self.request,
                ),
            )

    def iter_lines(self):
        return iter(self._lines)

    def json(self):
        if self._json_body is None:
            raise ValueError("no json body configured")
        return self._json_body


class FakeStreamContext:
    def __init__(self, response: FakeStreamResponse) -> None:
        self.response = response
        self.closed = False

    def __enter__(self) -> FakeStreamResponse:
        return self.response

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.closed = True
        return False


def test_create_client_prefers_api_format_mapping():
    client = create_client(
        AdapterConfig(
            provider="acme-provider",
            model="demo-model",
            api_format="anthropic",
        )
    )

    assert isinstance(client, AnthropicAdapter)


def test_create_client_falls_back_to_openai_compatible_adapter():
    client = create_client(
        AdapterConfig(
            provider="mock",
            model="mock-model",
        )
    )

    assert isinstance(client, OpenAICompatibleAdapter)


@pytest.mark.parametrize(
    ("provider", "expected_type"),
    [
        ("deepseek", OpenAICompatibleAdapter),
        ("glm", OpenAICompatibleAdapter),
        ("qwen", OpenAICompatibleAdapter),
        ("minimax", OpenAICompatibleAdapter),
        ("moonshot", OpenAICompatibleAdapter),
        ("kimi", OpenAICompatibleAdapter),
        ("custom_openai_compatible", CustomCompatibleAdapter),
    ],
)
def test_create_client_routes_provider_aliases(provider: str, expected_type: type):
    client = create_client(
        AdapterConfig(
            provider=provider,
            model="demo-model",
        )
    )

    assert isinstance(client, expected_type)


@pytest.mark.parametrize(
    ("api_format", "expected_type"),
    [
        ("openai_chat", OpenAICompatibleAdapter),
        ("anthropic_messages", AnthropicAdapter),
        ("gemini_generate_content", GeminiAdapter),
    ],
)
def test_create_client_routes_frontend_api_formats(api_format: str, expected_type: type):
    client = create_client(
        AdapterConfig(
            provider="acme-provider",
            model="demo-model",
            api_format=api_format,
        )
    )

    assert isinstance(client, expected_type)


def test_validate_chat_request_rejects_unsupported_images():
    request = ChatRequest(
        config=AdapterConfig(
            provider="openai",
            model="gpt-4o-mini",
            capabilities=AdapterCapabilities(supports_image_input=False),
        ),
        messages=[ChatMessage(role="user", content="hello")],
        agent_id="architect",
        agent_name="Architect",
        user_text="hello",
        attachments=[
            AttachmentRef(
                attachment_id="att-1",
                kind="image",
                mime_type="image/png",
            )
        ],
    )

    with pytest.raises(LLMValidationError, match="image attachments"):
        validate_chat_request(request)


def test_openai_compatible_adapter_maps_remote_unsupported_image_error_to_uniform_code(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_stream(method, url, *args, **kwargs):
        return FakeStreamContext(
            FakeStreamResponse(
                url_text=str(url),
                lines=[],
                status_code=400,
                json_body={
                    "error": {
                        "message": "Invalid content type. image_url is only supported by certain models.",
                        "code": "unsupported_content_type",
                    }
                },
            )
        )

    monkeypatch.setattr(httpx, "stream", fake_stream)

    adapter = OpenAICompatibleAdapter(
        AdapterConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="secret-key",
            api_format="openai",
            base_url="https://api.openai.com/v1",
            capabilities=AdapterCapabilities(supports_image_input=True),
        )
    )

    with pytest.raises(LLMValidationError) as exc_info:
        adapter.chat(
            ChatRequest(
                config=adapter.config,
                messages=[ChatMessage(role="user", content="请看这张图")],
                agent_id="architect",
                agent_name="Architect",
                user_text="请看这张图",
                attachments=[
                    AttachmentRef(
                        attachment_id="att-remote-image",
                        kind="image",
                        mime_type="image/png",
                    )
                ],
            )
        )

    assert exc_info.value.code == "IMAGE_NOT_SUPPORTED"
    assert exc_info.value.status_code == 422


def test_normalize_adapter_config_trims_provider_and_model():
    normalized = normalize_adapter_config(
        AdapterConfig(
            provider="  OpenAI  ",
            model="  gpt-4o-mini  ",
            api_format="  OPENAI  ",
        )
    )

    assert normalized.provider == "openai"
    assert normalized.model == "gpt-4o-mini"
    assert normalized.api_format == "openai_chat"


def test_normalize_adapter_config_canonicalizes_provider_and_api_format_aliases():
    normalized = normalize_adapter_config(
        AdapterConfig(
            provider="  Kimi  ",
            model="  kimi-k2.6  ",
            api_format="  OPENAI_CHAT  ",
        )
    )

    assert normalized.provider == "moonshot"
    assert normalized.model == "kimi-k2.6"
    assert normalized.api_format == "openai_chat"


def test_resolve_endpoint_candidates_prefers_domestic_then_global_for_supported_provider():
    candidates = resolve_endpoint_candidates(
        AdapterConfig(
            provider="qwen",
            model="qwen-plus",
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
    )

    assert [candidate.base_url for _, candidate in candidates] == [
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    ]


def test_resolve_endpoint_candidates_keeps_manual_base_url_without_fallback():
    candidates = resolve_endpoint_candidates(
        AdapterConfig(
            provider="moonshot",
            model="kimi-k2.6",
            base_url="https://proxy.example.com/v1",
        )
    )

    assert len(candidates) == 1
    assert candidates[0][0] == "手填地址"
    assert candidates[0][1].base_url == "https://proxy.example.com/v1"


def test_run_with_endpoint_fallback_aggregates_domestic_and_global_errors():
    attempts: list[str] = []

    def fail(candidate: AdapterConfig) -> str:
        attempts.append(candidate.base_url or "")
        raise ValueError(f"{candidate.base_url} unauthorized")

    with pytest.raises(EndpointFallbackError) as exc_info:
        run_with_endpoint_fallback(
            AdapterConfig(
                provider="minimax",
                model="MiniMax-M2.7",
                base_url="https://api.minimax.io/v1",
            ),
            fail,
        )

    assert attempts == [
        "https://api.minimaxi.com/v1",
        "https://api.minimax.io/v1",
    ]
    assert "国内和国外地址都调用失败" in str(exc_info.value)
    assert "https://api.minimaxi.com/v1 unauthorized" in str(exc_info.value)
    assert "https://api.minimax.io/v1 unauthorized" in str(exc_info.value)


def test_run_with_endpoint_fallback_does_not_retry_after_stream_interrupted():
    attempts: list[str] = []

    def fail(candidate: AdapterConfig) -> str:
        attempts.append(candidate.base_url or "")
        raise LLMStreamInterruptedError("stream interrupted")

    with pytest.raises(LLMStreamInterruptedError, match="stream interrupted"):
        run_with_endpoint_fallback(
            AdapterConfig(
                provider="qwen",
                model="qwen-plus",
                base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            ),
            fail,
        )

    assert attempts == ["https://dashscope.aliyuncs.com/compatible-mode/v1"]


def test_openai_compatible_adapter_posts_real_chat_payload(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_stream(method, url, *args, **kwargs):
        captured["url"] = str(url)
        captured["method"] = method
        captured["json"] = kwargs["json"]
        captured["headers"] = kwargs["headers"]
        captured["timeout"] = kwargs["timeout"]
        return FakeStreamContext(
            FakeStreamResponse(
                url_text=str(url),
                lines=[
                    'data: {"choices":[{"delta":{"content":"remote openai reply"},"finish_reason":"stop"}]}',
                    "data: [DONE]",
                ],
            )
        )

    monkeypatch.setattr(httpx, "stream", fake_stream)

    adapter = OpenAICompatibleAdapter(
        AdapterConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="secret-key",
            api_format="openai",
            base_url="https://api.openai.com/v1",
        )
    )
    response = adapter.chat(
        ChatRequest(
            config=adapter.config,
            messages=[
                ChatMessage(role="system", content="你是一个助手。"),
                ChatMessage(role="user", content="你好"),
            ],
            agent_id="architect",
            agent_name="Architect",
            user_text="你好",
        )
    )

    assert response.content == "remote openai reply"
    assert response.raw["mode"] == "remote"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer secret-key",
    }
    assert captured["json"] == {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "你是一个助手。"},
            {"role": "user", "content": "你好"},
        ],
        "stream": True,
    }
    assert isinstance(captured["timeout"], httpx.Timeout)


def test_openai_compatible_adapter_merges_multiple_system_messages_into_single_prefixed_system(
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, object] = {}

    def fake_stream(method, url, *args, **kwargs):
        captured["json"] = kwargs["json"]
        return FakeStreamContext(
            FakeStreamResponse(
                url_text=str(url),
                lines=[
                    'data: {"choices":[{"delta":{"content":"merged system reply"},"finish_reason":"stop"}]}',
                    "data: [DONE]",
                ],
            )
        )

    monkeypatch.setattr(httpx, "stream", fake_stream)

    adapter = OpenAICompatibleAdapter(
        AdapterConfig(
            provider="minimax",
            model="MiniMax-M2.7",
            api_key="secret-key",
            api_format="openai_chat",
            base_url="https://api.minimaxi.com/v1",
        )
    )
    response = adapter.chat(
        ChatRequest(
            config=adapter.config,
            messages=[
                ChatMessage(role="system", content="你是一个群聊成员。"),
                ChatMessage(role="system", content="以下是当前群聊的历史记录。"),
                ChatMessage(role="user", content="请继续接力。"),
                ChatMessage(role="system", content="在你回复前，本轮已有以下成员完成发言。"),
            ],
            agent_id="critic",
            agent_name="Critic",
            user_text="请继续接力。",
        )
    )

    assert response.content == "merged system reply"
    assert captured["json"] == {
        "model": "MiniMax-M2.7",
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个群聊成员。\n\n"
                    "以下是当前群聊的历史记录。\n\n"
                    "在你回复前，本轮已有以下成员完成发言。"
                ),
            },
            {"role": "user", "content": "请继续接力。"},
        ],
        "stream": True,
    }


def test_openai_compatible_adapter_validate_uses_same_endpoint(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_post(url, *, json, headers, timeout):
        captured["url"] = str(url)
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "ok",
                        }
                    }
                ]
            },
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    adapter = OpenAICompatibleAdapter(
        AdapterConfig(
            provider="openai",
            model="gpt-4o-mini",
            api_key="secret-key",
            api_format="openai",
            base_url="https://api.openai.com/v1",
        )
    )
    result = adapter.validate()

    assert result.ok is True
    assert result.status_message == "Model config validated successfully"
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["json"] == {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 8,
    }


def test_openai_compatible_adapter_validate_accepts_reasoning_only_response(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_post(url, *, json, headers, timeout):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "The",
                        },
                        "finish_reason": "length",
                    }
                ]
            },
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    adapter = OpenAICompatibleAdapter(
        AdapterConfig(
            provider="moonshot",
            model="kimi-k2.6",
            api_key="secret-key",
            api_format="openai_chat",
            base_url="https://api.moonshot.cn/v1",
        )
    )

    result = adapter.validate()

    assert result.ok is True
    assert result.status_message == "Model config validated successfully"


def test_openai_compatible_adapter_chat_still_requires_displayable_content(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_stream(method, url, *args, **kwargs):
        return FakeStreamContext(
            FakeStreamResponse(
                url_text=str(url),
                lines=[
                    'data: {"choices":[{"delta":{"reasoning_content":"The"}}]}',
                    "data: [DONE]",
                ],
            )
        )

    monkeypatch.setattr(httpx, "stream", fake_stream)

    adapter = OpenAICompatibleAdapter(
        AdapterConfig(
            provider="moonshot",
            model="kimi-k2.6",
            api_key="secret-key",
            api_format="openai_chat",
            base_url="https://api.moonshot.cn/v1",
        )
    )

    with pytest.raises(ValueError, match="missing assistant content"):
        adapter.chat(
            ChatRequest(
                config=adapter.config,
                messages=[ChatMessage(role="user", content="你好")],
                agent_id="writer",
                agent_name="Writer",
                user_text="你好",
            )
        )


def test_anthropic_adapter_posts_messages_payload(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_stream(method, url, *args, **kwargs):
        captured["url"] = str(url)
        captured["json"] = kwargs["json"]
        captured["headers"] = kwargs["headers"]
        captured["timeout"] = kwargs["timeout"]
        return FakeStreamContext(
            FakeStreamResponse(
                url_text=str(url),
                lines=[
                    'data: {"type":"message_start","message":{"id":"msg_123"}}',
                    'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"remote anthropic reply"}}',
                    'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}',
                    'data: {"type":"message_stop"}',
                    "data: [DONE]",
                ],
            )
        )

    monkeypatch.setattr(httpx, "stream", fake_stream)

    adapter = AnthropicAdapter(
        AdapterConfig(
            provider="anthropic",
            model="claude-3-5-sonnet",
            api_key="secret-key",
            api_format="anthropic",
            base_url="https://api.anthropic.com/v1",
        )
    )
    response = adapter.chat(
        ChatRequest(
            config=adapter.config,
            messages=[
                ChatMessage(role="system", content="你是一个助手。"),
                ChatMessage(role="user", content="你好"),
            ],
            agent_id="critic",
            agent_name="Critic",
            user_text="你好",
        )
    )

    assert response.content == "remote anthropic reply"
    assert response.raw["mode"] == "remote"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"] == {
        "Content-Type": "application/json",
        "x-api-key": "secret-key",
        "anthropic-version": "2023-06-01",
    }
    assert captured["json"] == {
        "model": "claude-3-5-sonnet",
        "max_tokens": 256,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": "你好"}],
            }
        ],
        "system": "你是一个助手。",
        "stream": True,
    }


def test_gemini_adapter_posts_generate_content_payload(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_stream(method, url, *args, **kwargs):
        captured["url"] = str(url)
        captured["json"] = kwargs["json"]
        captured["headers"] = kwargs["headers"]
        captured["timeout"] = kwargs["timeout"]
        return FakeStreamContext(
            FakeStreamResponse(
                url_text=str(url),
                lines=[
                    'data: {"candidates":[{"content":{"parts":[{"text":"remote gemini reply"}]},"finishReason":"STOP"}]}',
                    "data: [DONE]",
                ],
            )
        )

    monkeypatch.setattr(httpx, "stream", fake_stream)

    adapter = GeminiAdapter(
        AdapterConfig(
            provider="gemini",
            model="gemini-1.5-flash",
            api_key="secret-key",
            api_format="gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta",
        )
    )
    response = adapter.chat(
        ChatRequest(
            config=adapter.config,
            messages=[
                ChatMessage(role="system", content="你是一个助手。"),
                ChatMessage(role="user", content="你好"),
                ChatMessage(role="assistant", content="上一轮回复"),
                ChatMessage(role="user", content="继续"),
            ],
            agent_id="writer",
            agent_name="Writer",
            user_text="继续",
        )
    )

    assert response.content == "remote gemini reply"
    assert response.raw["mode"] == "remote"
    assert (
        captured["url"]
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:streamGenerateContent?alt=sse&key=secret-key"
    )
    assert captured["headers"] == {"Content-Type": "application/json"}
    assert captured["json"] == {
        "contents": [
            {"role": "user", "parts": [{"text": "你好"}]},
            {"role": "model", "parts": [{"text": "上一轮回复"}]},
            {"role": "user", "parts": [{"text": "继续"}]},
        ],
        "systemInstruction": {"parts": [{"text": "你是一个助手。"}]},
    }


def test_post_message_uses_factory_adapter(client, monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class FakeAdapter:
        def __init__(self, config: AdapterConfig):
            captured["config"] = config

        def chat(self, request: ChatRequest) -> ChatResponse:
            captured["request"] = request
            return ChatResponse(
                content="工厂适配器已接管回复",
                provider=request.config.provider,
                model=request.config.model,
            )

    def fake_create_client(config: AdapterConfig) -> FakeAdapter:
        return FakeAdapter(config)

    monkeypatch.setattr(chat_service_module, "create_client", fake_create_client)

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "请验证 chat_service 是否通过工厂调用",
        },
    )

    assert response.status_code == 201
    assert response.json()["agentMessages"][0]["content"] == "工厂适配器已接管回复"

    request = captured["request"]
    assert isinstance(request, ChatRequest)
    assert request.agent_id == "architect"
    assert request.agent_name == "Architect"
    assert request.user_text == "请验证 chat_service 是否通过工厂调用"

    config = captured["config"]
    assert isinstance(config, AdapterConfig)
    assert config.provider == "mock"
    assert config.model == "mock-model"


def test_post_message_prefers_conversation_model_and_passes_attachments(client, monkeypatch: pytest.MonkeyPatch):
    agent_model_response = client.post(
        "/api/v1/model-configs",
        json={
            "provider": "agent-provider",
            "model": "agent-model",
            "displayName": "Agent Provider - Agent Model",
            "apiFormat": "openai",
            "baseUrl": "https://agent.example.com/v1",
            "useFullUrl": False,
            "apiKey": "agent-secret",
            "capabilities": {
                "supportsImageInput": True,
                "supportsFileInput": False,
                "supportsStreaming": False,
                "contextWindow": 32000,
            },
        },
    )
    session_model_response = client.post(
        "/api/v1/model-configs",
        json={
            "provider": "session-provider",
            "model": "session-model",
            "displayName": "Session Provider - Session Model",
            "apiFormat": "openai",
            "baseUrl": "https://session.example.com/v1",
            "useFullUrl": False,
            "apiKey": "session-secret",
            "capabilities": {
                "supportsImageInput": True,
                "supportsFileInput": False,
                "supportsStreaming": True,
                "contextWindow": 64000,
            },
        },
    )
    agent_model_id = agent_model_response.json()["id"]
    session_model_id = session_model_response.json()["id"]

    with client.app.state.session_factory() as db:
        agent = db.get(chat_service_module.Agent, "architect")
        conversation = db.get(chat_service_module.Conversation, "direct-architect-default")
        agent.model_config_id = agent_model_id
        agent.model_unavailable = False
        conversation.model_config_id = session_model_id
        db.commit()

    captured: dict[str, object] = {}

    class FakeAdapter:
        def __init__(self, config: AdapterConfig):
            captured["config"] = config

        def chat(self, request: ChatRequest) -> ChatResponse:
            captured["request"] = request
            return ChatResponse(
                content="会话模型已优先生效",
                provider=request.config.provider,
                model=request.config.model,
            )

    def fake_create_client(config: AdapterConfig) -> FakeAdapter:
        return FakeAdapter(config)

    monkeypatch.setattr(chat_service_module, "create_client", fake_create_client)

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "请验证会话级模型优先级",
            "attachments": [
                {
                    "attachmentId": "att-1",
                    "kind": "image",
                    "mimeType": "image/png",
                    "name": "diagram.png",
                    "size": 1024,
                    "previewUrl": "https://example.com/diagram.png",
                    "metadata": {"source": "unit-test"},
                }
            ],
        },
    )

    assert response.status_code == 201
    assert response.json()["agentMessages"][0]["content"] == "会话模型已优先生效"

    config = captured["config"]
    assert isinstance(config, AdapterConfig)
    assert config.provider == "session-provider"
    assert config.model == "session-model"

    request = captured["request"]
    assert isinstance(request, ChatRequest)
    assert request.attachments[0].attachment_id == "att-1"
    assert request.attachments[0].mime_type == "image/png"


def test_post_message_passes_system_prompt_and_trimmed_history_to_adapter(client, monkeypatch: pytest.MonkeyPatch):
    with client.app.state.session_factory() as db:
        for index in range(13):
            db.add(
                chat_service_module.Message(
                    id=f"history-direct-{index:02d}",
                    conversation_id="direct-architect-default",
                    sender_type="user" if index % 2 == 0 else "agent",
                    sender_id="user" if index % 2 == 0 else "architect",
                    content=f"history-{index:02d}",
                    attachments=[],
                    created_at=f"2026-05-10T10:{index:02d}:00.000Z",
                )
            )
        db.commit()

    captured: dict[str, object] = {}

    class FakeAdapter:
        def __init__(self, config: AdapterConfig):
            captured["config"] = config

        def chat(self, request: ChatRequest) -> ChatResponse:
            captured["request"] = request
            return ChatResponse(
                content="已收到裁剪后的历史上下文",
                provider=request.config.provider,
                model=request.config.model,
            )

    def fake_create_client(config: AdapterConfig) -> FakeAdapter:
        return FakeAdapter(config)

    monkeypatch.setattr(chat_service_module, "create_client", fake_create_client)

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "direct-architect-default",
            "content": "请基于最近上下文继续",
        },
    )

    assert response.status_code == 201
    request = captured["request"]
    assert isinstance(request, ChatRequest)
    assert request.system_prompt == "你是一个偏系统性与结构化思考的智能助手。"
    assert request.messages[0].role == "system"
    assert request.messages[-1].role == "user"
    assert request.messages[-1].content == "请基于最近上下文继续"

    history_messages = request.messages[1:-1]
    assert len(history_messages) == chat_service_module.MAX_HISTORY_MESSAGES
    assert [message.content for message in history_messages[:2]] == ["history-01", "history-02"]
    assert history_messages[-1].content == "history-12"
    assert "我们可以先把产品目标压缩成最小可运行版本。" not in [message.content for message in history_messages]
    assert "history-00" not in [message.content for message in history_messages]


def test_post_group_message_uses_shared_history_for_each_agent_and_fixed_member_order(
    client,
    monkeypatch: pytest.MonkeyPatch,
):
    captured_requests: list[dict[str, object]] = []

    class FakeAdapter:
        def __init__(self, config: AdapterConfig):
            self.config = config

        def chat(self, request: ChatRequest) -> ChatResponse:
            captured_requests.append(
                {
                    "agent_id": request.agent_id,
                    "system_prompt": request.system_prompt,
                    "messages": [(message.role, message.content) for message in request.messages],
                    "metadata": dict(request.metadata),
                }
            )
            return ChatResponse(
                content=f"{request.agent_id}-reply",
                provider=request.config.provider,
                model=request.config.model,
            )

    def fake_create_client(config: AdapterConfig) -> FakeAdapter:
        return FakeAdapter(config)

    monkeypatch.setattr(chat_service_module, "create_client", fake_create_client)

    response = client.post(
        "/api/v1/messages",
        json={
            "conversationId": "group-product-discussion-default",
            "content": "请继续围绕第一版范围展开。",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert [message["senderId"] for message in body["agentMessages"]] == [
        "architect",
        "critic",
        "writer",
    ]
    assert [message["content"] for message in body["agentMessages"]] == [
        "architect-reply",
        "critic-reply",
        "writer-reply",
    ]

    assert [item["agent_id"] for item in captured_requests] == [
        "architect",
        "architect",
        "critic",
        "writer",
    ]
    assert captured_requests[0]["metadata"]["purpose"] == "group_moderator_note"
    public_requests = captured_requests[1:]
    assert {
        item["system_prompt"] for item in public_requests
    } == {
        "你是一个偏系统性与结构化思考的智能助手。",
        "你是一个偏风险识别和问题质疑的智能助手。",
        "你是一个偏表达整理和内容组织的智能助手。",
    }
    assert all(
        item["metadata"]["group_protocol_version"] == "group_runtime_v1"
        and item["metadata"]["moderator_note_present"] is True
        for item in public_requests
    )
    assert all(item["metadata"]["dispatch_strategy"] == "broadcast_chain" for item in public_requests)
    assert all(item["metadata"]["trigger_event_type"] == "user_message" for item in public_requests)

    moderator_system_messages = [
        content for role, content in captured_requests[0]["messages"] if role == "system"
    ]
    assert any("固定顺序的群聊接力" in content for content in moderator_system_messages)
    assert any("一次性内部主持说明" in content for content in moderator_system_messages)
    assert "当前用户输入：请继续围绕第一版范围展开。" in captured_requests[0]["messages"][-1][1]

    architect_non_system_messages = [message for message in public_requests[0]["messages"] if message[0] != "system"]
    critic_non_system_messages = [message for message in public_requests[1]["messages"] if message[0] != "system"]
    writer_non_system_messages = [message for message in public_requests[2]["messages"] if message[0] != "system"]
    assert architect_non_system_messages == [("user", "请继续围绕第一版范围展开。")]
    assert critic_non_system_messages == [("user", "请继续围绕第一版范围展开。")]
    assert writer_non_system_messages == [("user", "请继续围绕第一版范围展开。")]

    architect_system_messages = [content for role, content in public_requests[0]["messages"] if role == "system"]
    critic_system_messages = [content for role, content in public_requests[1]["messages"] if role == "system"]
    writer_system_messages = [content for role, content in public_requests[2]["messages"] if role == "system"]
    assert any("当前群聊运行段信息" in content for content in architect_system_messages)
    assert any("当前群聊运行段信息" in content for content in critic_system_messages)
    assert any("当前群聊运行段信息" in content for content in writer_system_messages)
    assert any("speaker_name=用户" in content and "content=我们来讨论一下第一版产品的核心功能吧。" in content for content in architect_system_messages)
    assert any("speaker_name=Architect" in content and "content=我先从结构上拆一下：第一版应该优先跑通主链路。" in content for content in architect_system_messages)
    assert any("speaker_name=Architect" in content and "content=architect-reply" in content for content in critic_system_messages)
    assert any("speaker_name=Architect" in content and "content=architect-reply" in content for content in writer_system_messages)
    assert any("speaker_name=Critic" in content and "content=critic-reply" in content for content in writer_system_messages)
    assert any("event_type=agent_message" in content for content in critic_system_messages)
    assert any("event_type=agent_message" in content for content in writer_system_messages)
