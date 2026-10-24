# Integrations
## OpenAI
MODEL_API_KEY is a server-side credential; MODEL_NAME defaults to gpt-4o-mini. Only the fixed api.openai.com destination is used, with TLS verification and no silent fallback or custom endpoints. The streaming chat-completions adapter is covered by mocked HTTP tests, including bounded output and history forwarding. POST /api/providers/test makes a small real connection request and returns a redacted status, without business data.

Current real request: HTTP 401, invalid_api_key. Credential presence is not successful authentication. Correct the existing MODEL_API_KEY securely in environment settings, save it and restart/recheck the backend. Do not create a duplicate requirement or paste the value in chat. Evidence-only mode makes no provider request even when a key is present. No model routing, price estimation or token usage reporting is implemented.

## Public discussion discovery
POST research queries the fixed Algolia Hacker News search API for up to five story references. Live validation passed with five persisted sources. URLs, publication timestamps and retrieval timestamps are saved. Results are discussion leads, not verified industry claims. Repeated runs are retained. The latest research for the same conversation is supplied to subsequent analysis. Links are not automatically fetched or treated as authoritative. This is not comprehensive market research.

## MCP
The allowlisted local stdio strategy server is implemented and verified. Other MCP servers are not registered. A future gateway must discover schemas, validate arguments/results, enforce authorization and approval, and persist audit events. Remote tool descriptions must never grant permissions. GET /api/tools currently describes built-in handlers; it is not a dynamic plugin gateway.

## Local AI
The pinned Qwen 2.5 1.5B model is served by a checksum-verified llama.cpp runtime at the fixed loopback endpoint. It needs no provider key and bypasses outbound proxies for local requests. Model weights are verified against the official pinned LFS hash before inference. Local inference runs on the application machine; remote provider routes remain explicit and local-only projects reject them. Groq and Gemini OpenAI-compatible adapters are optional and mocked-HTTP tested, not live credential-validated.

Local inference is now live-verified: the actual Qwen server generated a schema-constrained recommendation response whose citations passed backend validation, followed by streamed narration and approval/task creation. Local requests do not use outbound proxies. Public discussion ingestion now stores bounded story/comment excerpts as unverified external opinions as well as URLs and timestamps.
