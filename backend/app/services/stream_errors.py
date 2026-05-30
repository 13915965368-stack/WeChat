from __future__ import annotations

from app.llm.endpoint_fallback import EndpointFallbackError
from app.llm.validator import LLMStreamInterruptedError, LLMValidationError

MESSAGE_ERROR_STATUS_BY_CODE = {
    "model_stream_interrupted": 422,
    "model_endpoint_failed": 422,
    "model_request_failed": 422,
}


def build_stream_error_payload(exc: Exception) -> dict[str, str]:
    if isinstance(exc, LLMValidationError):
        return {"code": exc.code, "message": str(exc)}
    if isinstance(exc, LLMStreamInterruptedError):
        return {"code": "model_stream_interrupted", "message": str(exc)}
    if isinstance(exc, EndpointFallbackError):
        return {"code": "model_endpoint_failed", "message": str(exc)}
    if isinstance(exc, ValueError):
        return {"code": "model_request_failed", "message": str(exc)}
    return {"code": "stream_generation_failed", "message": str(exc) or "群聊运行失败"}


def build_contextual_error_payload(prefix: str, exc: Exception) -> dict[str, str]:
    payload = build_stream_error_payload(exc)
    message = payload.get("message", "").strip() or "群聊运行失败"
    payload["message"] = f"{prefix}：{message}"
    return payload


def should_handle_message_exception(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            LLMValidationError,
            LLMStreamInterruptedError,
            EndpointFallbackError,
            ValueError,
        ),
    )


def resolve_message_error_status(exc: Exception, code: str) -> int:
    if isinstance(exc, LLMValidationError):
        return exc.status_code
    return MESSAGE_ERROR_STATUS_BY_CODE.get(code, 500)
