[OPEN] Agent Search Chain Debug Session

## Session
- session_id: agent-search-chain
- scope: deepseek and writer web_search end-to-end verification
- status: investigating

## Goal
- Verify whether `deepseek` and `writer` can decrypt model config API keys with the configured encryption key
- Verify whether each agent triggers `web_search` for the query about recent Wang Hedi events
- Verify whether `tool_result` is returned into the LLM context
- Verify whether final model output content and format are acceptable

## Initial Hypotheses
- H1: `MODEL_CONFIG_ENCRYPTION_KEY` is now effective, so model config API keys can be decrypted successfully
- H2: one or both agents may choose not to call `web_search` even when search is available
- H3: `web_search` may be called successfully, but tool results may fail to reach the model context
- H4: the search chain may work correctly, but final output quality or format may still be suboptimal due to model behavior

## Test Query
- 帮我搜索一下最近的王鹤棣事件。

## Findings
- `MODEL_CONFIG_ENCRYPTION_KEY` 生效后，`deepseek` 与 `writer` 都能成功进入真实模型调用阶段
- 终端直接用 PowerShell here-string 输入中文会被编码成 `?`，需改用 Unicode 转义或端侧 JSON 请求进行测试
- 直接调用 `generate_agent_reply()` 时，如果未先执行 `register_all_tools()`，工具注册表为空，模型不会收到 `web_search`
- 在执行真实工具链后，`writer` 在自然问法下会主动触发 `web_search`，并成功基于搜索结果输出摘要
- `deepseek` 也会主动触发 `web_search`，但在拿到 `tool_result` 后的第二次模型请求阶段返回 `400 Bad Request`

## Confirmed Root Cause
- `tool_loop.py` 会把 `assistant.tool_calls` 与 `tool.tool_call_id` 正确写入下一轮 `ChatRequest.messages`
- 但 `validate_chat_request()` 在归一化消息时，仅保留 `ChatMessage(role=message.role, content=message.content)`，导致 `tool_calls` 与 `tool_call_id` 元数据丢失
- 丢失后的第二轮 payload 退化为仅包含普通 `tool` 文本消息，且 `tool_call_id` 为空、缺少前置 `assistant tool_calls`
- `writer` 绑定的模型对这种退化格式较宽容，因此仍能输出基于搜索结果的总结
- `deepseek` 对 tool 协议更严格，因此第二轮请求返回 `400 Bad Request`

## Status
- search engine: working
- writer agent with web_search: working but relies on degraded tool protocol
- deepseek agent with web_search: failing due to tool metadata loss before second request
