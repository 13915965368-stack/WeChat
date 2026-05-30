from app.llm.endpoint_fallback import EndpointFallbackError
from app.llm.validator import LLMStreamInterruptedError, LLMValidationError
from app.services.stream_errors import (
    build_stream_error_payload,
    resolve_message_error_status,
    should_handle_message_exception,
)


def test_build_stream_error_payload_has_message_and_code():
    payload = build_stream_error_payload(LLMValidationError("bad"))

    assert "message" in payload
    assert "code" in payload


def test_should_handle_message_exception_recognizes_supported_route_errors():
    assert should_handle_message_exception(LLMValidationError("bad")) is True
    assert should_handle_message_exception(LLMStreamInterruptedError("interrupted")) is True
    assert should_handle_message_exception(EndpointFallbackError("failed")) is True
    assert should_handle_message_exception(ValueError("bad request")) is True
    assert should_handle_message_exception(RuntimeError("unexpected")) is False


def test_resolve_message_error_status_uses_validation_status_code():
    exc = LLMValidationError("bad", status_code=409)

    assert resolve_message_error_status(exc, "model_empty_reply") == 409


def test_resolve_message_error_status_uses_code_mapping_for_non_validation_errors():
    assert (
        resolve_message_error_status(
            LLMStreamInterruptedError("interrupted"),
            "model_stream_interrupted",
        )
        == 422
    )
    assert resolve_message_error_status(RuntimeError("boom"), "stream_generation_failed") == 500
