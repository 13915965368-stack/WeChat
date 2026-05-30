from app.services import chat_service


def test_facade_exposes_required_symbols():
    for name in [
        "create_client",
        "generate_agent_reply",
        "_ensure_group_moderator_note",
        "build_chat_request",
        "sanitize_group_reply_content",
        "_build_group_public_event",
        "_build_group_trigger_event",
        "_build_group_dispatch_state",
        "MessageSendResult",
        "MAX_HISTORY_MESSAGES",
        "Conversation",
        "Agent",
        "Message",
        "AdapterConfig",
    ]:
        assert hasattr(chat_service, name), f"facade missing: {name}"


def test_facade_does_not_leak_protocol_text():
    assert not hasattr(chat_service, "GROUP_RUNTIME_PROTOCOL_TEXT")
    assert not hasattr(chat_service, "GROUP_MODERATOR_NOTE_SYSTEM_TEXT")
