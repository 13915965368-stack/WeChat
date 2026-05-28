[OPEN] Web Search Failure Debug Session

## Session
- session_id: web-search-failure
- scope: backend web search tool
- status: investigating

## Symptom
- Actual: real `web_search` call returns `搜索失败: provider unavailable`
- Expected: tool returns usable search results, or at least a failure reason that accurately reflects the root cause

## Initial Evidence
- Related tests pass, including tool registration, tool loop, provider fallback, and adapter tool protocol
- Runtime config currently resolves `searxng_base_url` to `http://localhost:8080`
- Real call attempts `searxng`, `duckduckgo`, and `tavily`
- Observed attempt errors include `502 Bad Gateway`, `202 Ratelimit`, and `provider unavailable`
- `.env` confirms `SEARXNG_BASE_URL=http://localhost:8080` and empty `TAVILY_API_KEY`
- Direct HTTP request to `http://localhost:8080/search?...` returns status `502` with empty body
- `Test-NetConnection localhost:8080` reports `TcpTestSucceeded: False`
- Direct `DuckDuckGoSearchProvider().search(...)` call returns `202 Ratelimit`

## Hypotheses
- H1: local `searxng` service is unhealthy or misconfigured, so the primary provider fails first
- H2: `duckduckgo` fallback is reachable but temporarily rate-limited, so fallback cannot rescue the request
- H3: `tavily` fallback is effectively disabled because the API key is missing
- H4: the final surfaced error is misleading because search error aggregation prefers the last failure instead of the most actionable failure

## Next Checks
- Verify whether `http://localhost:8080/search` is consistently returning `502`
- Inspect whether the current environment config comes from `.env` or process environment
- Confirm how provider attempt errors are aggregated into the final tool-visible error

## Current Assessment
- H1 confirmed: the primary `searxng` endpoint configured in `.env` is not healthy for search requests
- H2 confirmed: DuckDuckGo fallback is blocked by upstream rate limiting in the current environment
- H3 confirmed: Tavily fallback is unavailable because no API key is configured
- H4 confirmed: final error selection uses the last non-empty attempt error, which surfaces `provider unavailable` instead of the earlier actionable failures

## Additional Runtime Evidence
- `httpx.get(..., trust_env=True)` to `http://localhost:8080/search` now fails with `ConnectError [WinError 10061]`
- `httpx.get(..., trust_env=False)` fails with the same `ConnectError [WinError 10061]`
- `netstat -ano | findstr :8080` returns no listener
- `netsh interface portproxy show all` returns no port proxy rules
- `docker ps -a` cannot connect to Docker daemon, which suggests local containerized SearXNG is not running here

## Refined Assessment
- The stable root cause is not an application-level `/search` bug inside SearXNG
- The configured endpoint `http://localhost:8080` currently has no reachable local service behind it
- The earlier observed `502` appears transient or external to the backend search code; current stronger evidence indicates connection refusal
