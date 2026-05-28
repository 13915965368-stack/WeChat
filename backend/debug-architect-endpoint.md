[OPEN] Architect Endpoint Debug Session

## Session
- session_id: architect-endpoint
- scope: architect agent normal chat vs web_search failure mismatch
- status: investigating

## Goal
- Compare architect behavior between direct backend reproduction and frontend single/group chat usage
- Verify whether architect fails only after tool invocation or also in plain chat
- Verify whether conversation-level model config or runtime metadata differs from direct reproduction
- Determine whether endpoint fallback, auth, or request shape causes the architect-specific failure

## Initial Hypotheses
- H1: direct reproduction uses different conversation-level config or metadata than frontend sessions
- H2: architect can send plain messages, but fails specifically on second request after `web_search`
- H3: endpoint fallback behavior differs between real frontend sessions and isolated backend reproduction
- H4: the current reproduction path omits frontend-carried context required by architect's provider flow

## Target Comparison
- frontend single chat with architect
- frontend group chat including architect
- direct backend reproduction with architect

## Evidence
- `architect` model config uses `provider=moonshot`, `model=kimi-k2.6`, `api_format=openai_chat`, `base_url=https://api.moonshot.ai/v1`
- real frontend-like direct conversation `direct-architect-default` has `conversation.model_config_id = null`, so runtime falls back to the agent-level model config
- in the same real direct conversation context:
  - plain message `你好` succeeds without any tool calls
  - search message triggers `web_search`, receives tool result, then fails on the second model request
- replaying all captured payloads to Moonshot endpoints shows:
  - payload without tool replay: `moonshot.cn -> 200`, `moonshot.ai -> 401 Invalid Authentication`
  - payload with `assistant.tool_calls + role=tool`: `moonshot.cn -> 400 invalid_request_error`, `moonshot.ai -> 401 Invalid Authentication`

## Confirmed 400 Error
- domestic endpoint raw error:
  - `thinking is enabled but reasoning_content is missing in assistant tool call message at index 14`

## Confirmed Root Cause
- the failing request is specifically the second-round tool replay payload
- this payload contains an assistant message with `tool_calls`, followed by a `role=tool` message
- for Kimi domestic endpoint, when thinking is enabled, the assistant tool-call replay message must include `reasoning_content`
- current generic OpenAI-compatible replay path does not preserve or resend `reasoning_content`, so Kimi rejects the request with `400 invalid_request_error`

## Secondary Finding
- `moonshot.ai` consistently returns `401 Invalid Authentication`, which matches the documented domestic-vs-overseas key mismatch behavior and is not the primary blocker for the domestic-first flow
