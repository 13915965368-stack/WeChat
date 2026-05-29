from __future__ import annotations

from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_engine_from_settings(settings) -> Engine:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    )

    if settings.database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def ensure_sqlite_schema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "agents" not in table_names:
        return

    table_missing_columns: dict[str, dict[str, str]] = {
        "agents": {
            "avatar_image": "ALTER TABLE agents ADD COLUMN avatar_image TEXT",
            "theme_color": "ALTER TABLE agents ADD COLUMN theme_color VARCHAR(32)",
            "theme_light": "ALTER TABLE agents ADD COLUMN theme_light VARCHAR(32)",
            "theme_soft": "ALTER TABLE agents ADD COLUMN theme_soft VARCHAR(32)",
            "model_config_id": "ALTER TABLE agents ADD COLUMN model_config_id VARCHAR(64)",
            "model_unavailable": "ALTER TABLE agents ADD COLUMN model_unavailable BOOLEAN NOT NULL DEFAULT 0",
            "is_template": "ALTER TABLE agents ADD COLUMN is_template BOOLEAN NOT NULL DEFAULT 0",
            "pinned": "ALTER TABLE agents ADD COLUMN pinned BOOLEAN NOT NULL DEFAULT 0",
            "pinned_at": "ALTER TABLE agents ADD COLUMN pinned_at VARCHAR(40)",
        },
        "conversations": {
            "source_conversation_id": "ALTER TABLE conversations ADD COLUMN source_conversation_id VARCHAR(32)",
            "model_config_id": "ALTER TABLE conversations ADD COLUMN model_config_id VARCHAR(64)",
            "runtime_metadata": "ALTER TABLE conversations ADD COLUMN runtime_metadata TEXT NOT NULL DEFAULT '{}'",
            "is_disabled": "ALTER TABLE conversations ADD COLUMN is_disabled BOOLEAN NOT NULL DEFAULT 0",
            "pinned_at": "ALTER TABLE conversations ADD COLUMN pinned_at VARCHAR(40)",
        },
        "messages": {
            "render_format": "ALTER TABLE messages ADD COLUMN render_format VARCHAR(32) NOT NULL DEFAULT 'plain_text'",
            "thinking_payload": "ALTER TABLE messages ADD COLUMN thinking_payload TEXT NOT NULL DEFAULT '{}'",
            "usage_payload": "ALTER TABLE messages ADD COLUMN usage_payload TEXT NOT NULL DEFAULT '{}'",
            "message_meta": "ALTER TABLE messages ADD COLUMN message_meta TEXT NOT NULL DEFAULT '{}'",
            "attachments": "ALTER TABLE messages ADD COLUMN attachments TEXT NOT NULL DEFAULT '[]'",
        },
    }

    with engine.begin() as connection:
        for table_name, missing_columns in table_missing_columns.items():
            if table_name not in table_names:
                continue
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column_name, ddl in missing_columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(ddl))

    # Migrate llm_settings: add updated_at column if missing
    if "llm_settings" in table_names:
        llm_columns = {column["name"] for column in inspector.get_columns("llm_settings")}
        if "updated_at" not in llm_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE llm_settings ADD COLUMN updated_at VARCHAR(40) NOT NULL DEFAULT ''"))

    inspector = inspect(engine)
    if "agents" in inspector.get_table_names():
        agent_indexes = {index["name"] for index in inspector.get_indexes("agents")}
        conversation_indexes = {index["name"] for index in inspector.get_indexes("conversations")} if "conversations" in inspector.get_table_names() else set()
        with engine.begin() as connection:
            if "ix_agents_model_config_id" not in agent_indexes:
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_agents_model_config_id ON agents (model_config_id)"))
            if "ix_conversations_model_config_id" not in conversation_indexes:
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_conversations_model_config_id ON conversations (model_config_id)"))
            if "ix_conversations_source_conversation_id" not in conversation_indexes:
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_conversations_source_conversation_id "
                        "ON conversations (source_conversation_id)"
                    )
                )


def get_db(request: Request) -> Generator[Session, None, None]:
    session_factory = request.app.state.session_factory
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
