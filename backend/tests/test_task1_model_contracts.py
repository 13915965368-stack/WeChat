from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.db import ensure_sqlite_schema
from app.main import create_app
from app.models import Base


def test_task1_seed_exposes_blank_agent_and_new_agent_fields(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "task1_seed.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock-model")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv(
        "MODEL_CONFIG_ENCRYPTION_KEY",
        "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    )

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/agents")

    assert response.status_code == 200
    body = response.json()
    by_id = {agent["id"]: agent for agent in body}

    assert "blank-agent" in by_id
    assert by_id["blank-agent"]["isTemplate"] is True
    assert by_id["blank-agent"]["systemPrompt"] == ""
    assert by_id["architect"]["modelConfigId"] is None
    assert by_id["architect"]["modelUnavailable"] is False


def test_task1_conversation_and_message_contract_include_new_fields(client):
    conversations_response = client.get("/api/v1/conversations")
    messages_response = client.get(
        "/api/v1/messages",
        params={"conversationId": "direct-architect-default"},
    )

    assert conversations_response.status_code == 200
    assert messages_response.status_code == 200
    assert conversations_response.json()[0]["modelConfigId"] is None
    assert messages_response.json()["items"][0]["attachments"] == []


def test_task1_sqlite_init_adds_new_columns_and_model_config_table(tmp_path: Path):
    db_path = tmp_path / "task1_legacy.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE agents (
                    id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(128) NOT NULL,
                    role_summary TEXT NOT NULL,
                    style_summary TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    avatar VARCHAR(32) NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE conversations (
                    id VARCHAR(32) PRIMARY KEY,
                    type VARCHAR(16) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    agent_id VARCHAR(64),
                    pinned BOOLEAN NOT NULL DEFAULT 0,
                    created_at VARCHAR(40) NOT NULL,
                    updated_at VARCHAR(40) NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE messages (
                    id VARCHAR(32) PRIMARY KEY,
                    conversation_id VARCHAR(32) NOT NULL,
                    sender_type VARCHAR(16) NOT NULL,
                    sender_id VARCHAR(64) NOT NULL,
                    content TEXT NOT NULL,
                    created_at VARCHAR(40) NOT NULL
                )
                """
            )
        )

    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema(engine)

    inspector = inspect(engine)
    agent_columns = {column["name"] for column in inspector.get_columns("agents")}
    conversation_columns = {column["name"] for column in inspector.get_columns("conversations")}
    message_columns = {column["name"] for column in inspector.get_columns("messages")}

    assert "model_configs" in inspector.get_table_names()
    assert {"model_config_id", "model_unavailable", "is_template"}.issubset(agent_columns)
    assert "model_config_id" in conversation_columns
    assert "attachments" in message_columns
