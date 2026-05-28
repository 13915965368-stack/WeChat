from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.seed import seed_default_data


@pytest.fixture
def test_db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "test_agent_mvp.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock-model")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv(
        "MODEL_CONFIG_ENCRYPTION_KEY",
        "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    )
    yield db_path
    for suffix in ("", "-wal", "-shm"):
        file_path = Path(f"{db_path}{suffix}")
        if file_path.exists():
            file_path.unlink()


@pytest.fixture
def client(test_db_path: Path):
    app = create_app()
    with TestClient(app) as test_client:
        with app.state.session_factory() as db:
            seed_default_data(db)
        yield test_client


@pytest.fixture(autouse=True)
def stub_external_llm_provider_calls(monkeypatch: pytest.MonkeyPatch):
    original_post = httpx.post
    original_stream = httpx.stream

    class FakeStreamResponse:
        def __init__(self, *, lines: list[str], url_text: str, content_type: str = "text/event-stream") -> None:
            self._lines = lines
            self.status_code = 200
            self.headers = {"content-type": content_type}
            self.text = "\n".join(lines)
            self._request = httpx.Request("POST", url_text)

        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            return iter(self._lines)

        def json(self):
            raise ValueError("stream responses do not expose a single JSON payload")

    class FakeStreamContext:
        def __init__(self, response: FakeStreamResponse) -> None:
            self.response = response
            self.closed = False

        def __enter__(self) -> FakeStreamResponse:
            return self.response

        def __exit__(self, exc_type, exc, tb) -> bool:
            self.closed = True
            return False

    def fake_post(url, *args, **kwargs):
        url_text = str(url)
        if url_text.startswith(("http://localhost", "http://127.0.0.1")):
            return original_post(url, *args, **kwargs)

        request = httpx.Request("POST", url_text)
        if "/chat/completions" in url_text:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "stubbed openai response",
                            }
                        }
                    ]
                },
                request=request,
            )
        if url_text.rstrip("/").endswith("/messages"):
            return httpx.Response(
                200,
                json={
                    "content": [
                        {
                            "type": "text",
                            "text": "stubbed anthropic response",
                        }
                    ]
                },
                request=request,
            )
        if ":generateContent" in url_text:
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": "stubbed gemini response",
                                    }
                                ]
                            }
                        }
                    ]
                },
                request=request,
            )
        return original_post(url, *args, **kwargs)

    def fake_stream(method, url, *args, **kwargs):
        url_text = str(url)
        if url_text.startswith(("http://localhost", "http://127.0.0.1")):
            return original_stream(method, url, *args, **kwargs)
        payload = kwargs.get("json", {})
        if "/chat/completions" in url_text and payload.get("stream") is True:
            return FakeStreamContext(
                FakeStreamResponse(
                    url_text=url_text,
                    lines=[
                        'data: {"choices":[{"delta":{"content":"stubbed openai response"},"finish_reason":"stop"}]}',
                        "data: [DONE]",
                    ],
                )
            )
        if url_text.rstrip("/").endswith("/messages") and payload.get("stream") is True:
            return FakeStreamContext(
                FakeStreamResponse(
                    url_text=url_text,
                    lines=[
                        'data: {"type":"message_start","message":{"id":"msg_stub"}}',
                        'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"stubbed anthropic response"}}',
                        'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}',
                        'data: {"type":"message_stop"}',
                        "data: [DONE]",
                    ],
                )
            )
        if ":streamGenerateContent" in url_text:
            return FakeStreamContext(
                FakeStreamResponse(
                    url_text=url_text,
                    lines=[
                        'data: {"candidates":[{"content":{"parts":[{"text":"stubbed gemini response"}]},"finishReason":"STOP"}]}',
                        "data: [DONE]",
                    ],
                )
            )
        return original_stream(method, url, *args, **kwargs)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "stream", fake_stream)
