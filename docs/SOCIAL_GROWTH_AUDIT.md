# Social growth implementation audit

The supplied Growth Insights specification is the target, not a completed-feature claim.

- Working: business/project/tenant records, commerce CSV/SQL metrics, growth snapshots, vault, typed tool registry, guarded MCP transports, leased graph jobs/checkpoints, recurring scheduler, approvals/internal task receipts, model routes and specialist roles.
- Partial: Growth dashboard and monitoring review uploaded evidence; social metrics currently only exist as unstructured optional MCP excerpts. No normalized account/post snapshots, social charts or eligible forecasting pipeline exists yet.
- Missing: native Instagram/YouTube adapters, social-source binding/config validation, persistent normalized engagement history, source-backed monitoring, chart drill-down and social-specific coordinated evidence interpretation.
- Blocked for live acceptance: authorized provider tokens/accounts/app permissions and real cloud access. Sign-in OAuth grants do not authorize social analytics. Instagram professional/Meta permissions and YouTube Data API/read-only OAuth are separate. LinkedIn approved organization APIs require provider approval; configurable MCP is the extension point.
- Delivery scope: two read-only native MCP adapters plus an approved-MCP contract, normalized immutable snapshots, existing scheduler/graph-based monitoring, persisted dashboard, gated forecasting and existing three-role handoffs. No social publishing, spend, private messages, arbitrary source hosts or automated self-approval.

## Delivered vertical slice (local acceptance)

The gaps above describe the pre-change audit. Native read-only Instagram (two Meta login token flows), YouTube, social-v1 MCP ingestion, source/account/config binding, immutable normalized observations, nullable metrics, post/comment drill-down, saved chart values, gated forecasts, shared scheduler monitoring, default-model three-role reviews with same-workspace internal data, JSON evidence export and navigation persistence are now implemented. Growth Insights keeps the existing UI and adds one contextual Social intelligence section; no new global agent/module was added.

The full backend suite passed 287 tests. The social browser journey passed using a synthetic upstream MCP boundary, actual API/DB/vault/stdio discovery and explicit evidence mode. After final authorization changes, all 24 social tests passed, including late-response cancellation, disconnect and credential rotation. The production frontend build and final desktop/mobile browser journey also passed. Native official API adapters and Gemini calls were tested using controlled boundaries, not live credentials. Live Meta access/public deploy acceptance remains blocked until the operator configures and successfully tests their authorized account. See [connection, semantics and limitations](SOCIAL_GROWTH.md).
