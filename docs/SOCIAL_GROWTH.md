# Authorized social evidence in Growth Insights

This adds a working read-only vertical slice to the existing Evolvyn architecture. It does not complete every capability in the master Growth Insights document or certify production readiness.

## Connect Instagram

The preferred flow is now **Connect with Instagram**: the platform owner configures the Meta app once, then each business authorizes its own account. Long-lived exchange and bounded renewal use the existing vault/scheduler. See [Instagram OAuth setup and acceptance](INSTAGRAM_OAUTH.md). The numbered steps below remain the advanced manual-token alternative.

1. Deploy this revision of both API and frontend. Open **Grow your business → Social intelligence** and select an evidence conversation/business. Use a project whose data policy allows selected external providers; local-only projects reject social collection.
2. Obtain a token for a professional Instagram account through your approved Meta application. Use the account's Instagram business/user ID, **not its @username or Facebook Page ID**. Confirm access to that account using Meta's tools privately.
3. In **Key vault**, save the authorized access token as provider **MCP**, with a useful label. The Gemini key is the model credential, not a Meta access token. Do not put tokens in chat, screenshots, URLs, source, tool arguments or this document.
4. Return to Social intelligence → **Connect social account**. Select the matching token flow: **Instagram · Facebook Login token** calls `graph.facebook.com`; **Instagram · Instagram Login token** calls `graph.instagram.com`. Select the saved credential and account ID; register the source.
5. **Sync account**. Registration/discovery alone is explicitly unverified. Only a successful real provider read and durable snapshot produces a verified observation. Review failures in the saved workflow; check token expiry, selected ID, app access/review, API version and scopes.
6. Upload sales/customer evidence in the same conversation, then **Run business + research + strategy review**. The existing business analyst, marketing analyst and product manager roles use the workspace default/per-agent model routes. Select **Evidence rules · no LLM** explicitly for deterministic excerpts. No generated recommendation constitutes approval or proof of uplift.
7. Enable daily monitoring, inspect the persisted schedule/next due, and use **Refresh observations** for newly collected evidence. Pause/disconnect stops future collection; an already-running job remains visible and can be stopped. A free sleeping Render service cannot continuously collect evidence.

For Facebook Login, account/media read generally needs `instagram_basic` and the appropriate Page permissions (`pages_show_list`, `pages_read_engagement`) for the linked professional account. Reading comments additionally needs `instagram_manage_comments`; analytics endpoints beyond this adapter can require `instagram_manage_insights`. Instagram Login uses `instagram_business_basic` and approved `instagram_business_manage_comments` for comment access. Confirm current scope names, account eligibility, token type, app mode/review and version in Meta's documentation: https://developers.facebook.com/docs/instagram-platform/ . This adapter defaults to Graph `v23.0`; operators can set `EVOLVYN_META_API_VERSION` to a supported `vNN.0`. No permission is granted merely by entering a token.

A rejected nested comment request (HTTP 400/403) retries once for supported post counters without comment fields, with explicit coverage disclosure. Other errors do not produce successful snapshots. For manual-token sources, replace expired tokens privately, disconnect the old source, and register a new source using the updated credential. Native Instagram OAuth sources use the authorization/renewal flow described above. Token/config changes invalidate old bindings.

## Other connections and extension contract

YouTube uses an existing authorized `youtube.readonly` OAuth token saved as MCP, enabled YouTube Data API access, and the matching channel ID. It reads uploaded-video counters, not comment text or revenue. Evolvyn does not yet issue/refresh this OAuth token itself.

An approved external MCP may provide Instagram, YouTube or LinkedIn organization observations. Register its HTTPS host under governance, connect/probe the MCP server, then register a **read-only** tool accepting `account_id` and `conversation_id`. Select **Approved MCP · social-v1 contract** in Growth Insights. The same tool registry remains available in Product Studio and the research/business workflows. There is no native LinkedIn authorization or publishing claim.

The exact schema is `Observation` in `backend/social_contract.py`: `schema_version=social-v1`, provider, account ID/name, timezone-aware capture date, optional follower count, at most 25 uniquely identified posts with public provider URLs, optional nonnegative integer counters, at most 20 permitted comments, and a coverage description. Missing metrics remain null, not zero. Wrong accounts, malformed/oversized responses, unexpected provider URLs and stale/future snapshots are rejected. Generic adapters must honor their own provider authorization, redaction and credential-reflection rules; native adapters enforce fixed destinations, bounded HTTPS responses and no token reflection.

## What the dashboard measures

- Latest saved provider counters, capture date, account ID, coverage, post links and bounded comment samples.
- Observed-post counts, available likes/comments/views/followers, and interaction totals. These are **cumulative counters on sampled posts**, not daily engagement, unique customers, sales, sentiment, market share or causal lift.
- Persisted snapshot history, execution/error receipts, monitoring status, three-role review outputs and downloadable JSON evidence report. Reviews identify their input snapshot; newer evidence is labeled.
- A conservative forecast only after at least 29 comparable daily snapshots: same account, same sampled post IDs, same connector/credential definitions, near-24-hour intervals, fresh latest snapshot and nondecreasing known per-post counters. A rolling seven-day mean must perform at least as well as a last-day baseline over seven backtest points. Bounds use maximum recent backtest error, **not** a calibrated confidence interval. Hourly/weekly/changing post cohorts will be suppressed. This is an estimate for interactions on the same observed posts, not business revenue/demand predictions.

## Security and persistence

Collection uses the existing encrypted vault, MCP registry, tool ontology, bounded LangGraph jobs, worker leases, authenticated tenant/project policy and PostgreSQL records. Automatic monitors collect evidence only; model reviews are explicit user actions. No external publisher/ad/spend/write tool is introduced. Existing consequential-action approval gates remain unchanged.

Snapshots have deterministic execution/source IDs for replay safety. The source, execution, parent conversation and relevant authorization/configuration rows are checked before commit. Reopening an execution does not recollect. Membership/token/config/local-only revocation, cancellation and conversation trash must prevent unauthorized new snapshots. Snapshot queries use a tenant/source index; the dashboard sends bounded summaries plus the latest full sample.

Email addresses, handles and phone-like text are redacted from captions/comments; author profiles and private messages are not collected. This is a bounded minimization measure, not comprehensive PII detection. Disconnect disables future collection and dedicated tool/server, preserves audit history, and **does not revoke the provider token**. Revoke/delete that credential in Key vault and the provider account when needed. Comprehensive social retention/erasure controls, including copies in agent checkpoints, remain unfinished; do not ingest sensitive customer material before organization review. Existing conversation trash lifecycle applies to linked source records.

## Validation and remaining scope

`tests/test_social_growth.py`: contract/metric/forecast tests, real PostgreSQL/authentication/stdio discovery/worker persistence, scheduled collection, pause/disconnect, tenant/project/viewer boundaries, token revocation and provider/schema/account failures. Three-role default Gemini routing and combined sales/social evidence are checked with a controlled model completion boundary. Native HTTP adapters are checked using `httpx.MockTransport`, including fixed hosts/bearer headers, fallback, rate limits, malformed/oversized data and reflection rejection.

`python tests/e2e_social_growth.py`: isolated real API/vault/queue/database/browser, with an explicitly synthetic upstream MCP response and evidence-only review; verifies export, persistence, schedules, mobile layout and disconnect. No live token/model or public deployment success is inferred from these tests.

Still requiring separate work: live operator-authorized Meta acceptance, native YouTube OAuth/token refresh, complete social retention/erasure policy, representative sentiment analysis, competitor access, post/ads publishing, attribution/causal outcomes, broader forecasting, social PDF/DOCX exports, always-on infrastructure and independent production security/load/restore acceptance. Source evidence and predictions must remain labeled accordingly.
