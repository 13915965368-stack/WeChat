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

    monkeypatch.setattr(httpx, "post", fake_post)
