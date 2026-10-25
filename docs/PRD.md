# Evolvyn — Product Requirements Document (PRD)

**Document status:** Product direction and requirements  
**Version:** 1.0  
**Last reviewed:** 2026-10-25  
**Repository:** [25955A0512/Evolvyn](https://github.com/25955A0512/Evolvyn)  
**Audience:** Product, engineering, design, QA, security and future contributors

> This PRD describes the intended product and its acceptance criteria. It is not a claim that every capability is implemented, connected to a live provider, independently security-reviewed, or production-deployed. Use the linked implementation audits and tests to determine actual status.

## 1. Executive summary

Evolvyn is an **AI-powered Continuous Business Evolution Platform**. It helps a business understand what is happening, discover why it may be happening, identify opportunities, decide what to do, safely carry out approved actions, and measure what happened afterward.

Evolvyn brings business data, external research, specialist agents, workflows, governed tools, human approvals and outcome history into one workspace. Its value is not simply generating advice: it is maintaining a traceable path from evidence to decision, execution receipt and later measurement.

**Core loop**

Understand the business → Observe changes → Investigate with evidence → Prioritize opportunities → Propose a strategy → Approve and execute safely → Verify the result → Learn from outcomes.

The first business vertical is **e-commerce**, using uploaded sales/catalog data, explicit metric definitions, source-linked research, recommendations, approval-gated internal task creation and dated follow-up comparisons. Native store/CRM/ad/social publishing must only be described as available when the corresponding provider integration is configured and successfully tested.

## 2. Problem statement

Business owners and small teams often work across disconnected spreadsheets, customer feedback, analytics, research, project tools and social channels. They must manually assemble context, interpret conflicting signals, research competitors, choose actions and determine whether those actions helped.

Generic chat assistants can produce plausible recommendations but may lack current authorized business data, source provenance, persistent decisions, safe action execution and outcome verification. Traditional dashboards show metrics but usually do not turn them into an accountable, governed workflow.

Evolvyn aims to close that gap with a persistent, evidence-first, human-governed system.

## 3. Vision, positioning and product principles

### Vision
Become a trusted operating workspace where a business can continuously improve through evidence-backed AI analysis and safely governed execution.

### Product promise
**Turn business evidence into better decisions and measurable action—without losing control or trust.**

### Principles
1. **Evidence before confidence:** Every material finding links to its source, timestamp and calculation or retrieval method.
2. **Truthful system status:** Distinguish configured, connected, healthy, recently synced, stale, failed and unavailable. Never imply an integration or action succeeded without verification.
3. **Deterministic numbers:** SQL/Python calculate financial and operational metrics. LLMs interpret evidence and propose hypotheses; they do not invent figures.
4. **Human control:** AI may recommend an action, but server-side policy and explicit approvals determine whether it can execute.
5. **Traceability:** Persist source records, agent runs, decisions, approvals, tool invocations, receipts, artifacts and outcome measurements.
6. **Bounded autonomy:** Limit permissions, steps, tool calls, tokens, time, concurrency and cost. Route only relevant specialists to a task.
7. **Tenant isolation:** Every resource, query, background job, connector, artifact and approval must be scoped to an authorized organization/workspace and, where applicable, project.
8. **Extensibility without parallel systems:** Reuse the existing React/TypeScript, FastAPI, PostgreSQL, LangGraph, execution harness, registry and policy gateway.
9. **Privacy by design:** Least-privilege scopes, explicit external-processing rules, secret custody, data minimization, retention controls and auditability.
10. **Measurable learning, not causal overclaiming:** Outcomes inform future decisions, but correlation alone does not prove an action caused a change.

## 4. Target users and permissions

### Primary personas
- **Business owner / founder:** Wants a clear view of business health, prioritized growth opportunities and confidence that actions are safe.
- **Growth / marketing operator:** Investigates performance, customer feedback, market signals and campaign experiments.
- **Analyst / product operator:** Validates source data, compares periods, maintains evidence and converts decisions into tasks.
- **Team member:** Reviews shared findings, collaborates in discussions and contributes within assigned permissions.
- **Workspace administrator:** Manages members, provider connections, secrets, policies, schedules and access.
- **Builder / developer:** Uses Product Studio to turn requirements into a reviewed, tested, previewable application.

### Access model
The product must support organization/workspace boundaries and project-level restrictions. Capabilities must be enforced by the backend, not just hidden in the UI:
- **Read:** View permitted evidence, reports, conversations and artifacts.
- **Edit/manage:** Create or update permitted business/project data, configurations and drafts.
- **Discuss with agents:** Submit prompts and run allowed analysis in the selected scope.
- **Approve:** Separately granted capability for consequential actions.
- **Administer:** Manage members, credentials, policies and organization settings.

Do not assume that “editor” means “approver” or “admin”. Membership revocation must affect future API access and background work.

## 5. Product experience and navigation

Evolvyn is a modular, responsive conversational workspace. Navigation should expose distinct, shareable URLs for meaningful modules, while retaining a cohesive application shell. Direct navigation, browser back/forward and refresh must preserve the correct module and authorized resource.

Suggested route families (final paths must be reconciled with the current router before implementation):
- `/dashboard` — business overview and next actions
- `/grow` or `/growth-insights` — Growth Insights
- `/discussionroom` — Discussion Room
- `/product-studio` — Product Building Studio
- `/keyvault` — credential and model configuration
- `/connections` / `/mcp-registry` — provider connections, MCP servers and tools
- `/team-settings` — workspace, membership and policy settings
- `/activity` — executions, approvals, receipts and audit history

These are product route requirements, not confirmation that each exact route already exists. Route guards and backend authorization must be tested together.

### Common interaction requirements
- Show useful loading, empty, offline, permission-denied, stale-data, partial-success and failure states.
- Clearly identify sample/synthetic data and deterministic evidence mode versus model-generated output.
- Preserve drafts and recover from transient UI failures where safe.
- Provide search/filtering, timestamps, source links, visible progress and actionable error messages.
- Stream progress when supported, but keep a persisted run record as the source of truth.
- Support desktop and mobile layouts, keyboard navigation, readable contrast, accessible labels and focus management.
- Confirm destructive or externally visible actions; do not make buttons that imply success without a real operation.

## 6. Core module: Growth Insights (highest product priority)

Growth Insights is the heart of Evolvyn. It should help a business move from fragmented information to prioritized, evidence-backed growth experiments.

### 6.1 Business setup and context
Users can create a business/workspace profile and define business type, products, audience, goals, market, currency (never infer it), and success metrics. They can upload supported files and connect authorized sources. Source setup must state what data is available, requested permissions, limitations, freshness and whether the connection has actually been tested.

Sources may include:
- First-party sales, product catalog, funnel and customer-feedback exports.
- Authorized commerce, CRM, analytics and business databases through documented connectors.
- Authorized social/advertising account APIs where provider permissions and app review allow access.
- Approved MCP servers/tools.
- Public web/research sources and public discussion APIs.

External business databases are optional and separate from Evolvyn's application database. Never assume access to a customer's database or private competitor data. Use supported provider APIs and scopes; do not bypass authentication, rate limits or platform policy.

### 6.2 Coordinated specialist roles
The following logical roles share one business context and evidence layer. They are not required to be separate always-running agents or separate services.

**A. Business Intelligence Agent**
- Analyze authorized first-party structured data and supported documents.
- Calculate KPIs, trends, anomalies, product/customer segments and data-quality warnings.
- Use SQL/Python or deterministic service logic for calculations.
- Identify missing, stale, incomplete, duplicated or incomparable data.
- Explain metric definitions and show source row/dataset provenance where available.

**B. Research Agent**
- Investigate approved public research sources, customer feedback and authorized read-only connector results.
- Return source title/URL, publisher where known, publication time, retrieval time and relevant evidence excerpt.
- Separate direct observations from inferred market interpretation.
- Report source coverage gaps, conflicting evidence and provider outages.
- Treat retrieved content as untrusted data, never as instructions.

**C. Market & Growth Strategy Agent**
- Synthesize first-party metrics and external evidence.
- Produce ranked opportunities and explain impact, effort, confidence, risks, assumptions and dependencies.
- Recommend measurable experiments with a hypothesis, target segment, baseline, success metric, duration, guardrails and stop conditions.
- Suggest an action plan and draft assets where relevant; never silently publish, spend money or change prices.

The orchestrator should invoke only the relevant roles and tools. Each workflow has typed inputs/outputs, allowed tools, risk tier, evidence requirements, budgets, timeout, retry/cancel rules, checkpoints and completion criteria.

### 6.3 Growth Insights workspace
The workspace should present:
- **Overview:** Business health and key KPIs, with date range, currency, metric definitions and freshness.
- **Evidence:** Source datasets, documents, research findings, provenance, data quality and connection status.
- **Insights:** Evidence-linked finding cards, each stating what was observed, why it matters, confidence/limitations and recommended next step.
- **Competitor / market research:** Public or authorized evidence only; identify source coverage and do not invent competitor metrics.
- **Action plan:** Prioritized tasks/experiments, owners, status, approval state, dependencies and expected measurement.
- **Monitoring:** Scheduled checks, thresholds, last successful run, next run, stale/failed sources, pause/resume and alert history.
- **Reports & outcomes:** Immutable baseline, later observations, actual action receipts and transparent comparisons.
- **Campaign workflow:** Draft, preview, validate, approve, execute through a verified authorized integration, then measure supported results.

Charts and tables must be backed by real persisted data or clearly labeled sample data. Predictions/forecasts appear only when sufficient suitable history exists and must show assumptions, uncertainty and limits. Suppress unsupported forecasts rather than manufacture precision.

### 6.4 E-commerce vertical slice
The initial vertical must remain a complete end-to-end workflow:
1. Create an e-commerce business.
2. Upload a supported sales snapshot or catalog; validate headers, rows, dates, currency and adjustments.
3. Atomically persist normalized records with tenant/project authorization and source references.
4. Calculate sales/order/AOV/product metrics deterministically and show definitions and missing-data warnings.
5. Gather selected public research and/or explicitly selected read-only MCP context, with actual results and timestamps.
6. Generate source-linked investigation proposals and strategy recommendations; label hypotheses and fallback mode.
7. Let an authorized user edit/review and approve the exact internal action.
8. Execute through the governed tool gateway, verify persisted writes and create a receipt.
9. Upload a later dated snapshot and compare against the immutable baseline, validating period overlap and currency.
10. Show observed outcomes without claiming causation.

Important metric boundaries: catalog price is not realized revenue; do not infer currency, profit, taxes, shipping, customer lifetime value, acquisition cost or conversion without suitable data. Distinguish gross and net measures. Never sum overlapping snapshots. A task created is not the same as an external campaign launched.

### 6.5 Campaign and external action lifecycle
Every externally visible or consequential action follows:
Draft → Preview → Validate policy and permissions → Present exact target/content/arguments → Obtain required approval → Execute once with idempotency/reconciliation → Verify provider response/state → Persist receipt → Measure outcomes.

Publishing, campaign launch, pricing changes, spend, repository writes, deployment and destructive operations require explicit risk-appropriate approval. Critical financial/legal actions remain human-led by default. If a provider call times out after a possible write, reconcile state before retrying. Do not represent a draft or queued task as a published campaign.

## 7. Discussion Room and collaborative decisions

Discussion Room coordinates specialist analysis over selected business evidence and registered context tools. It should:
- Support persistent, searchable conversations scoped to workspace/project.
- Allow permitted documents and feedback uploads with safe extraction, source attribution and bounded size/type.
- Run relevant specialists through the existing LangGraph orchestration and bounded harness.
- Show agent roles, evidence, handoffs, progress, review findings, model/fallback mode and errors.
- Support editing a proposed decision, approval/rejection and preserving the source conversation.
- Save cross-session memory only from reviewed/accepted information with provenance, scope and retention.
- Keep rejected, draft, expired or unreviewed proposals out of trusted memory.
- Allow a reviewed decision to be explicitly applied as a new Product Studio requirements revision; never silently mutate an existing build or plan.

Retrieved text, files, public pages, tool output and model responses remain untrusted. A prompt or document cannot grant permissions or override policy.

## 8. Product Building Studio

Product Studio helps users move from an idea to a reviewed application artifact in a single workspace.

### Required workflow
1. **Requirements interview:** Ask clarifying questions about users, problem, features, stack, theme, entities/fields, authentication, privacy, integrations, acceptance criteria and deployment constraints.
2. **PRD generation:** Create an editable, versioned PRD and a real downloadable DOCX. Preserve assumptions, open questions and acceptance criteria.
3. **Architecture design:** Generate stack rationale, components, data model, APIs, trust boundaries, risks, deployment design and test strategy.
4. **Workflow design:** Generate editable user/business flows and technical diagrams with explicit triggers, decisions, errors and approvals.
5. **UI/UX design:** Propose screens and components consistent with Evolvyn's existing design system; preserve editable design decisions.
6. **Code generation:** Create versioned source files using supported, verified adapters; explain major decisions and show diffs.
7. **Testing and review:** Run relevant checks and display actual commands/results, failures and evidence. Never invent passing tests.
8. **Preview:** Build and run in an isolated sandbox and show a live preview inside the same dashboard.
9. **Iteration:** Support file browsing/editing, diffs, logs, checkpoints, selective regeneration, rollback, cancellation, resume, export and artifact history.

### Execution safety boundary
Current trusted starter adapters and scoped prototypes are not equivalent to unrestricted arbitrary-code execution. Arbitrary generated code must never run in the FastAPI process or a privileged shared container. A full sandbox requires an isolated ephemeral worker/broker with CPU, memory, disk, process, time and network limits; no production secrets, host mounts or Docker socket by default; restricted egress; separate artifact identity; isolated preview origins/cookies; artifact scanning/signing; and approval bound to the exact artifact digest and deployment target. If sandboxing is not available, label the prototype limitation clearly rather than simulating a live build.

## 9. Connections, MCP registry and Key Vault

### 9.1 Connection lifecycle
A guided connection flow should support:
Configure → Authenticate/authorize → Test → Discover supported capabilities and schemas → Review scopes/risk → Select allowed workspace/agents → Enable.

Users should see real status, last successful check, scopes, data/action capabilities, errors and remediation. Support reconnect, refresh, disable, disconnect, credential rotation/revocation and provider-specific limitations. A configured record is not proof of a healthy live connection.

### 9.2 MCP and tool registry
- Reuse the persistent typed/versioned registry and existing gateway.
- Support approved stdio/HTTPS transports as appropriate, server identity/config version, workspace scope, secret reference, discovered tool schemas, permissions, risk tier and health.
- Validate tool inputs against schemas before execution and cap output sizes.
- Enforce identity/workspace authorization, data-processing policy, allowlists, risk ceilings, budgets, timeouts and audit records on every call.
- Guard against SSRF, DNS rebinding, private-network access, malicious metadata/results, prompt injection, unsafe local commands and oversized outputs.
- GitHub is the first external integration target: read-only by default. Repository/issue/PR writes, merges and deployments require separate capability and approval.
- Adding a server must use the documented adapter/manifest path, not introduce a second registry or execution engine.

### 9.3 Key Vault and model routes
- Store provider credentials encrypted; never return raw secret values through read APIs.
- Permit authorized owners/admins to create, replace, rotate and revoke credentials and set organization defaults or per-agent overrides.
- Resolve secrets only server-side at invocation time. Never place them in prompts, tool arguments, client state, source control or logs.
- Keep local-only, evidence-only and remote-provider routes explicit. Do not silently switch to another provider when a request fails or violates data policy.
- Show the actual resolved route, supported model and sanitized error/usage information.
- Vault key custody, backup and restoration must be documented and tested; restoring a database without its matching vault key cannot recover encrypted credentials.

### 9.4 Provider OAuth
Google/GitHub sign-in is distinct from authorizing a business data connector. OAuth must use fixed provider endpoints, validated browser-bound state, PKCE where supported, safe redirect allowlists, single-use callback state and explicit account linking. Business analytics/publishing access is only available where provider APIs, scopes, account type and app review permit it. Provider tokens must not be handed to agents as plain text. Live provider acceptance requires real registered applications and credentials.

## 10. Continuous monitoring and the learning loop

Monitoring must run while the user is offline using durable schedules, worker leases, webhooks/events where available and bounded polling only where needed. It must not depend on an open browser tab or endless client polling.

Required capabilities:
- Schedule/threshold configuration, timezone-aware execution, quiet hours and notification preferences.
- Durable job state, leases, bounded retries with backoff/jitter, deduplication, cancellation, pause/resume and recovery after worker restart.
- Per-source health, last-success timestamp, freshness, next run and actionable failure details.
- Persisted findings, source snapshots, decisions, action receipts and outcome observations.
- Feedback loop: observe → detect → investigate → propose → approve/execute → verify → evaluate → improve.
- Version and evaluate changes to prompts, models, policies and workflows; retain a rollback path.
- Never call monitoring “active” unless a healthy source and recent successful run support that claim.

## 11. Governance, safety and reliability

Policy is deterministic and server-side. An LLM can propose a tool call but cannot grant itself a capability, elevate a risk level, bypass approval or change policy.

### Mandatory controls
- Least-privilege identity, organization/project authorization and data egress policy.
- Read/internal-write/external-write/critical risk classification with configured risk ceilings.
- Explicit approvals bound to exact action, arguments, actor, workspace, tool/server configuration and expiry; prevent replay and stale-configuration use.
- Bounded graph steps/visits, tool calls, model calls, output tokens, wall-clock time, retries, concurrency and spend.
- Cancellation, checkpoints, resume, idempotency where appropriate, safe retry policy and reconciliation for uncertain writes.
- Input/output schema validation, output limits, error redaction, payload-free audit records and observability.
- Safe uploads and rendering; never render untrusted HTML as trusted UI.
- Prompt-injection defenses that treat source content as data; do not promise complete elimination.
- Security threat model covering OAuth/session abuse, cross-tenant IDOR, privilege escalation, injection, XSS/CSRF, SSRF, path traversal, malicious uploads, secret leakage, unsafe code, sandbox escape and vulnerable dependencies.
- Data export/deletion/retention procedures, encryption, backup/restore tests, incident response and dependency/security monitoring.
- Independent security review before production use. Do not claim certification, penetration testing or production hardening without evidence.

## 12. Data model and provenance

Reuse the existing PostgreSQL application persistence and current schemas/migrations. Evolve the model only where necessary; avoid duplicate registries or competing workflow engines.

Core conceptual entities:
- Organization/workspace, membership, role/capabilities and restricted project ACL.
- Business profile, goals and metric definitions.
- Connector/server, credential reference, discovered tool/capability and health state.
- Dataset/document, normalized records, source references and ingestion run.
- Conversation/message, agent run, execution graph/checkpoint/event and usage record.
- Evidence item, insight/recommendation, hypothesis, experiment/action plan and decision.
- Approval request/decision, tool invocation, idempotency record and verified receipt.
- Schedule/job/lease, notification and monitoring observation.
- Product Studio project, requirements revision, architecture/workflow artifact, source build, test run and preview.
- Outcome snapshot, baseline, follow-up measurement and evaluation result.
- Audit event and retention/deletion request.

Each important result should carry business/workspace scope, creation time, source/provenance, run/config version, status and appropriate actor. Keep immutable snapshots or versions where historical comparisons and audits depend on them. Minimize PII and do not retain source payloads in logs by default.

## 13. Architecture and operational requirements

### Existing baseline to preserve
- Frontend: React + TypeScript.
- API: FastAPI/Python.
- Persistence: PostgreSQL.
- Orchestration: LangGraph and existing bounded execution harness.
- Integrations: typed persistent tool registry, MCP adapters, existing policy gateway.
- Local development: Docker Compose; local model path plus explicitly labeled deterministic evidence mode.
- Current product surfaces include the conversational workspace, e-commerce workflow, Growth Insights, Discussion Room, Product Studio, Key Vault and Agent control/registry operations.

### Target deployment boundary
Separate public frontend/API, durable orchestration workers, database/object storage, secret custody and untrusted code sandbox. Use managed PostgreSQL, encrypted object storage, managed secret/key service, HTTPS, private networking, controlled egress, centralized redacted logs, metrics/alerts, quotas and backup/restore. AWS is a target option; Vercel + Render has also been prepared in repository docs. Neither should be described as deployed until real resources are provisioned and smoke-tested.

Required operations: health/readiness checks, migrations with rollback strategy, graceful shutdown, worker lease recovery, rate limits, per-tenant concurrency and cost controls, backup/restore drills, incident procedures, and a staging environment with provider credentials isolated from production.

## 14. Non-functional requirements

- **Correctness:** Deterministic calculations; validated inputs; reproducible source-linked outputs.
- **Security:** Server-side authorization on every request and background action; no secret leakage; tested isolation and approval boundaries.
- **Reliability:** Durable jobs/checkpoints; safe recovery; idempotent or reconciled writes; useful partial-failure behavior.
- **Performance:** Bounded concurrency, pagination and indexed queries; no unnecessary polling; measure latency before optimizing.
- **Scalability:** Stateless API where practical, worker separation, tenant quotas, durable queues/leases and object storage for large artifacts.
- **Cost control:** Per-run/provider usage tracking, configurable budgets, bounded retries and quotas.
- **Usability:** Clear progress, source links, editable artifacts, actionable errors, responsive layout and accessible interactions.
- **Maintainability:** Typed API contracts, migrations, focused adapters, tests, documented configuration and no duplicated core abstractions.
- **Portability:** Reproducible local Compose and environment-driven deployment without committing credentials.
- **Transparency:** Clearly label fallback mode, unsupported data, incomplete integrations, stale sources, uncertain forecasts and unverified outcomes.

Do not invent numerical SLAs, concurrency targets or accuracy targets until workload baselines are measured and product owners set explicit targets. Establish those targets before broad production launch.

## 15. Product success metrics

Measure product outcomes rather than agent activity alone:
- Time from business setup to first source-backed insight.
- Percentage of insights with valid provenance and complete metric definitions.
- Percentage of recommendations accepted, edited or rejected, with reasons where users choose to provide them.
- Percentage of approved actions with a verified execution receipt.
- Percentage of scheduled runs completed on time; stale-source and failure rate.
- Outcome measurement coverage and time from action to first follow-up.
- User-reported usefulness and repeat usage of Growth Insights.
- Product Studio workflow completion rate: idea → PRD → architecture/workflow → source → tests → preview.
- Authorization/policy violation test pass rate, cross-tenant test coverage, secret-redaction checks and restore-drill success.
- Model/provider latency, error rate, token/cost usage and fallback rate.

Metrics must be defined precisely, derived from persisted events, and reported with denominators and time windows. Do not use an increase in engagement or a revenue delta as proof of causality without a suitable experiment design.

## 16. Prioritization and phased delivery

### P0 — Trustworthy foundation
- Audit each module as working, partial, missing or blocked against code and tests.
- Fix and test tenant/project isolation, OAuth/session edge cases, role capabilities and background-job authorization.
- Verify Key Vault lifecycle, secret redaction, policy enforcement, approval binding, replay protection and uncertain-write reconciliation.
- Establish data retention/export/deletion and backup/vault-key restore procedures.
- Ensure URL routing, direct links, refresh and route-level authorization work for all existing modules.
- Add security and failure-path tests before adding more autonomy.

### P1 — Complete the core Growth Insights journey
- Deliver the e-commerce end-to-end path with deterministic metrics, evidence links, real source timestamps, research limits, approvals, verified receipts and outcome comparison.
- Complete source connection health/freshness UX and authorized read-only connector setup.
- Finish one durable monitor with schedules, worker recovery, deduplication, backoff, pause/resume and visible last-success status.
- Build dashboards and charts only from persisted, defined metrics.
- Validate forecasts and suppress them when history is insufficient.

### P2 — Extensible integrations and team collaboration
- Complete real Google/GitHub sign-in acceptance with registered applications, account linking, callback security and revocation.
- Complete GitHub MCP read-only connect/discover/test/invoke and its audit/approval boundaries for writes.
- Complete workspace invitations and read/edit/discuss/approve/admin capability tests.
- Add integrations incrementally through the shared registry, starting with the highest-value authorized business sources.
- Keep provider review and scope limitations visible in the UI.

### P3 — Idea-to-preview Product Studio
- Deliver editable PRD and downloadable DOCX.
- Deliver architecture and editable workflow diagrams.
- Generate versioned source using supported adapters, with file diffs and real test output.
- Add isolated sandbox broker, live preview, cancel/resume, checkpoints and rollback.
- Gate external deployment on review and approval bound to the artifact digest.

### P4 — Production release and measurable evolution
- Provision the selected cloud target; configure TLS, domains, OAuth callbacks, managed database/secrets and object storage.
- Complete tenant/load/cost tests, security review, backup and vault-key restore drills, monitoring and incident procedures.
- Validate live providers with authorized test accounts and document supported scopes.
- Run real business experiments with baselines, measurement plans and transparent interpretation.
- Expand agent roles only when evaluation shows a measurable benefit.

## 17. Acceptance criteria and definition of done

A feature is complete only when the full path works:
**UI → authenticated API → server authorization → persisted state/job → service/tool → validated result → visible UI feedback**, including negative paths.

For each feature:
1. Map requirements to current code and mark working/partial/missing/blocked.
2. Define typed inputs/outputs and observable success/failure states.
3. Add or update schema migrations, API contracts and focused tests.
4. Test successful use, malformed input, missing permissions, cross-tenant access, timeout, cancellation, partial failure and retry behavior where applicable.
5. Verify that approval binds the exact action and cannot be replayed.
6. Verify source provenance and ensure unsupported claims are suppressed or clearly labeled.
7. Run relevant backend tests, frontend type/build checks and browser journeys; record exact commands and results.
8. Inspect the diff for security regressions, generated files and secrets.
9. Update implementation/status documentation only to match verified behavior.
10. Document known limitations, operational setup and manual provider steps.

### Release blockers
- Any cross-tenant data exposure or privilege escalation.
- Secrets in client responses, prompts, logs or source control.
- Unapproved consequential writes or replayable approvals.
- Arbitrary generated code running in the API or a privileged shared environment.
- Fake provider connections, fabricated citations/metrics or unverified success claims.
- No tested backup/restore path for production data and vault key.
- Public deployment without correct TLS, origin/host/cookie settings and operational review.

## 18. Current-state notes from the repository audit

The following reflects repository documentation available on 2026-10-25; it is not a fresh execution of the test suite.

**Documented as implemented or exercised in the local application:** React/TypeScript + FastAPI + PostgreSQL; accounts and workspace roles; persistent conversations and runs; bounded LangGraph/harness execution; typed MCP/tool registry; encrypted credential vault; local Qwen inference and explicit evidence-only fallback; structured e-commerce imports and SQL-calculated metrics; source-linked recommendation/approval/task receipt/outcome workflow; Growth Insights workspace; Discussion Room; Product Studio trusted starter adapters and scoped prototype; saved workflows and recurring schedules; local Docker Compose readiness and selected desktop/mobile browser journeys.

**Documented as partial, awaiting real provider setup, or requiring further acceptance:** live Google/GitHub OAuth with registered production apps; live optional remote model/provider validation; live third-party business/social connector acceptance and provider app review; social publishing and native account synchronization; broad semantic/vector retrieval; forecasts where source history is insufficient; unrestricted isolated generated-code execution; public cloud provisioning and TLS launch; identity recovery/email verification/MFA; general retention/deletion and production key lifecycle; distributed rate limits; independent penetration/security review; production load/cost tests; fresh-cloud-task restoration and real business experiment outcome validation.

**Important evidence sources in this repository**
- [README and setup/current behavior](../README.md)
- [Implementation checklist](PROGRESS.md)
- [E-commerce execution audit](ECOMMERCE_AUDIT.md)
- [Expanded product requirements/checklist](PRODUCT_REQUIREMENTS.md)
- [Governance boundaries](GOVERNANCE.md)
- [Security controls and limits](SECURITY.md)
- [Modern stack and current module notes](MODERN_STACK.md)
- [Cloud deployment recommendation and launch gates](CLOUD_DEPLOYMENT.md)
- [Growth Insights acceptance scope](GROWTH_INSIGHTS_SPEC.md)
- [Social growth acceptance and limits](SOCIAL_GROWTH.md)
- [OAuth setup and provider requirements](PUBLIC_OAUTH_SETUP.md)

## 19. Open product decisions

These decisions should be made using real user needs and workload evidence, not silently assumed:
- Which cloud target is the first production target: Vercel + Render or AWS?
- Which first-party connector should follow the e-commerce CSV workflow, based on user demand and provider feasibility?
- Which notifications are required at launch (in-app, email, Slack, etc.) and what are the quiet-hour defaults?
- What retention and deletion windows apply to uploaded data, evidence, run logs and generated artifacts?
- What initial target workload, latency, availability and cost budget should be used for release acceptance?
- Which supported generated-code stacks and languages are in the first public Studio release?
- Which actions, if any, can be auto-executed under narrow user-configured limits without per-action approval?
- Which measurable growth experiments and attribution methods will be used with the first pilot businesses?

Until decided, preserve safe defaults: read-only external access, explicit approvals for consequential writes, no silent provider switching, bounded execution, no fabricated data, and no claim of production readiness.
