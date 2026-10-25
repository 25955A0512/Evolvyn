# Gemini and Groq workspace keys

The user-facing platform uses **Gemini or Groq** for new AI work. Save a key in Key vault once; every agent uses the shared workspace default. There is no per-agent assignment, “Use for all agents” action or model picker. Connection tokens remain a separate advanced feature for authorized integrations.

## Save or replace a key

1. Open Key vault → Add key and choose Gemini or Groq.
2. Enter the key privately and save.
3. The API checks the provider catalog and runs a small JSON chat request against a platform-supported model. The check consumes a small amount of provider quota.
4. Only a successful check saves/replaces the key and makes it the default. Failed authentication, quota, format or availability checks leave the previous default unchanged.
5. Agent routes is a read-only view of the shared route. Test connection rechecks an existing key and updates its verified model without assigning different agents.

The supported text/JSON candidates for this release are Gemini `gemini-2.5-flash-lite` / `gemini-2.5-flash`, and Groq `llama-3.3-70b-versatile` / `llama-3.1-8b-instant`. Candidates must appear in the authenticated provider catalog; the selected candidate must pass the completion check. Image/audio/embedding, inactive and untested preview models are excluded. This list is a platform compatibility boundary, not a claim of permanent provider availability or unlimited quota. Selection stays within the provider chosen by the user.

## Existing workspaces

A saved Gemini/Groq key supersedes stale local defaults and legacy per-agent overrides in the effective shared route. An existing unverified key is labeled Saved; use Test connection to verify catalog access and generation. A verified shared default remains authoritative. Revoking it stops default model work rather than silently switching to another key/provider or local execution. Save/replace a supported key to establish a new default.

The Groq path uses bounded non-streaming OpenAI-compatible requests with `max_completion_tokens`, validated text/JSON, safe failure messages and token usage. Product agents, source generation, discussions, strategy reviews and main conversations use the same workspace route. General chat no longer bypasses it in favor of separate support-service keys.

Local, evidence-only, OpenAI and OpenRouter choices are removed from current chat/workflow/provider settings. Historical explicit offline records and internal deterministic evidence calculations are retained for compatibility; SQL metrics do not become LLM estimates. Organization/project external-processing restrictions remain enforced. Legacy private APIs and historical records are not destructively deleted.

Deploy matching backend and frontend revisions on Render and Vercel. No local workspace contains the operator's actual Gemini/Groq credentials, so live credential/quota acceptance must be performed privately after deployment. A successful test is a point-in-time check, not a guarantee against subsequent provider retirement or rate limits.

## Verification

- Focused tests exercise catalog filtering, verified shared defaults, stale local-route recovery, Groq structured output and the real product chat graph with controlled provider HTTP, failed-save preservation, role revalidation, concurrent revocation and no-key admission errors.
- The existing product/model/registry regression suite is retained with shared-default expectations updated to the new product requirements.
- Browser acceptance saves both providers through the real vault UI without model/override controls, verifies all agent routes, reads actual discussion outputs through a controlled Groq adapter, and preserves Product Studio Enter/draft/history behavior.

Provider HTTP is controlled in these tests. Database, encryption, queues, graph orchestration and browser interactions are real; the tests do not establish live Gemini/Groq acceptance.
