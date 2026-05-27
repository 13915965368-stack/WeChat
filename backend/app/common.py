from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi.responses import JSONResponse

from app.schemas import ErrorResponse


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def error_payload(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error_payload(code, message))


def error_example(code: str, message: str) -> dict[str, Any]:
    return {
        "summary": code,
        "value": error_payload(code, message),
    }


def error_responses(
    description: str,
    *examples: tuple[str, str, str],
) -> dict[str, Any]:
    return {
        "description": description,
        "model": ErrorResponse,
        "content": {
            "application/json": {
                "examples": {
                    name: error_example(code, message)
                    for name, code, message in examples
                }
            }
        },
    }
