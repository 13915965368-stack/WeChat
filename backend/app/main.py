from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.common import error_response
from app.config import get_settings
from app.db import create_engine_from_settings, create_session_factory, ensure_sqlite_schema
from app.llm.validator import LLMValidationError
from app.models import Base
from app.routes.agents import router as agents_router
from app.routes.attachments import router as attachments_router
from app.routes.conversations import router as conversations_router
from app.routes.messages import router as messages_router
from app.routes.model_configs import router as model_configs_router
from app.routes.settings import router as settings_router
from app.security import validate_encryption_key
from app.seed import seed_default_data
from app.services.attachment_store import InMemoryAttachmentStore
from app.services.secret_migration_service import migrate_plaintext_api_keys
from app.llm.tools import register_all_tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_encryption_key(app.state.settings)
    Base.metadata.create_all(bind=app.state.engine)
    ensure_sqlite_schema(app.state.engine)
    with app.state.session_factory() as db:
        migrate_plaintext_api_keys(db, app.state.settings)
        seed_default_data(db)
    register_all_tools()
    try:
        yield
    finally:
        app.state.engine.dispose()


def create_app(session_factory=None) -> FastAPI:
    settings = get_settings()
    engine = create_engine_from_settings(settings)
    resolved_session_factory = session_factory or create_session_factory(engine)

    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = resolved_session_factory
    app.state.attachment_store = InMemoryAttachmentStore()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request, _exc):
        return error_response(422, "validation_error", "Invalid request")

    @app.exception_handler(LLMValidationError)
    async def handle_llm_validation_error(_request, exc: LLMValidationError):
        return error_response(exc.status_code, exc.code, str(exc))

    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        return {"ok": True}

    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(attachments_router, prefix="/api/v1")
    app.include_router(conversations_router, prefix="/api/v1")
    app.include_router(messages_router, prefix="/api/v1")
    app.include_router(model_configs_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    return app
