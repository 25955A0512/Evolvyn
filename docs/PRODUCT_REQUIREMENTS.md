# Evolvyn Product Requirements and Acceptance Checklist

These are target requirements, not a claim that the feature already exists. Audit the code first and mark each item working, partial, missing, or blocked. Reuse existing components. A feature is done only when its full path works and relevant tests pass.

## 1. Identity and team access
- Google and GitHub OAuth sign-up/sign-in, safe account linking, validated state/callback/redirects, logout and session revocation.
- Organizations/workspaces, invitations, member removal, role assignment and audit history.
- Server-side capabilities for read, edit/manage, and discuss with agents. Every API, DB query, conversation, file, job, connector, and approval must enforce organization/project scope. Never rely on frontend-only controls.
- Secure cookies/sessions, CSRF protection where relevant, rate limits, expiry, safe errors and tests for cross-tenant access/privilege escalation.

## 2. Product Building Studio
- Requirements agent asks clarifying questions; creates an editable PRD and real downloadable DOCX.
- Architecture agent produces stack, components, data model, APIs, risks and deployment plan.
- Workflow agent produces editable user/business flows and technical diagrams.
- UI/UX agent creates screens/components consistent with the existing design system.
- Code agent generates versioned source files and explains important decisions.
- Test/review agent runs checks, presents evidence/failures and suggests fixes.
- Isolated sandbox builds/runs the app and shows a live preview in the same dashboard.
- Project UI supports file browse/edit, diffs, logs, test status, downloads, checkpoints, selective regeneration, rollback, cancel and resume.
- Never execute generated code in the API process, privileged containers, or a host-Docker-socket-connected agent. Use isolated ephemeral workers with CPU/memory/disk/process/time/network limits; no secrets/host mounts by default; restrict preview origins and iframe permissions. If full sandboxing is unavailable, label preview limitations honestly.

## 3. Agents and orchestration
- Reuse LangGraph and the existing bounded harness. Add another orchestration framework only for a demonstrated gap.
- Specialist roles may include planner, business/customer intelligence, research, product strategy, product building, marketing, alert triage, log analysis, change analysis, runbook retrieval, verification/evaluation and governed execution. Route only relevant agents/tools; do not run every agent on every task.
- Every workflow declares typed inputs/outputs, evidence sources, allowed tools, risk tier, budgets, timeout, retry/cancel rules, checkpoints and completion criteria.
- Keep agent data access least-privilege and workspace-scoped.

## 4. Extensible MCP and tool registry
- Guided flow: configure server/transport, authenticate, test connection, discover capabilities/tools/schemas, review scopes/risks, test a selected tool, enable for chosen workspace/agents.
- Support health/status, reconnect, schema refresh, config versioning, enable/disable, disconnect, credential rotation/revocation and useful diagnostics.
- Use typed/versioned registry records for server identity, workspace, transport, endpoint/command, secret reference, tool schemas, scopes, risk and status.
- Keep credentials in a secret manager/encrypted custody—not plaintext DB fields, frontend state, logs, prompts or source control.
- Validate arguments with JSON Schema and local policy. Treat MCP metadata/results as untrusted. Defend against SSRF, DNS rebinding, private-network access, prompt injection, malicious tool outputs, oversized responses and unsafe local commands. Restrict egress and sandbox local MCP processes.
- Every call passes identity/workspace authorization, allowlists, deterministic risk policy, limits and audit logging. Approval binds exact tool/arguments/server config/actor/workspace/expiry; prevent replay/stale approvals. Verify side effects and do not blindly retry uncertain writes.
- Adding servers/tools should use documented adapters/manifests, not rewrite orchestration. GitHub is the first integration: read-only by default; gate issue/PR/repository writes, merge and deployment separately behind approval.
- Use customer-authorized APIs/connectors; never assume access to arbitrary customer PostgreSQL. Keep Evolvyn's application DB separate from external business data.

## 5. Continuous monitoring and feedback loop
- Monitoring continues while users are offline using durable scheduled jobs, worker leases and webhooks/events where available—not endless polling.
- Add backoff/jitter, rate limits, deduplication, pause/resume, configurable thresholds/quiet hours, stale connection status and last-success timestamp.
- Show source-linked findings, timestamps, freshness, confidence/limitations and actual connection health. Never claim monitoring is active without a healthy configured source and recent successful run.
- Implement a measurable loop: observe → detect → investigate → propose → approve/execute → verify → evaluate → improve. Persist outcomes; distinguish correlation from causation. Version/evaluate/revert changes to prompts, models, policies and workflows.

## 6. Governance and security
- Deterministic server-side policy decides access, tenant boundaries, tool allowlists, risk ceilings, approvals, rate limits and execution budgets. The LLM may propose actions but cannot grant itself permissions or override policy.
- Gate external writes, public posts, campaigns, pricing changes, repository changes, deployment and destructive actions with approval. Critical actions remain human-controlled by default.
- Bound steps, tool calls, tokens, wall time and cost; support cancellation, checkpoint/resume, safe retries, idempotency, concurrency controls, output limits and recovery from partial failures.
- Threat-model OAuth/session abuse, cross-tenant IDOR, SQL injection, XSS/CSRF, SSRF, path traversal, malicious uploads, secret leakage, unsafe generated code, sandbox egress and vulnerable dependencies.
- Encrypt in transit/at rest, rotate secrets, redact logs, audit events, retention/deletion/export controls, backups/restore drills, security headers, dependency scans and alerts.
- Test unauthorized roles, cross-tenant access, forged/expired/replayed approvals, changed arguments after approval, malicious MCP outputs, budget exhaustion, uncertain write timeouts, secret redaction, OAuth callback abuse and sandbox boundaries. Never claim penetration testing/compliance without evidence.

## 7. Interactive dashboard
- Reflect real persisted state: progress, running/waiting/failed/completed, approvals, evidence, tool history, logs, artifacts, usage/cost and next actions.
- Support streaming where available, responsive/accessibility basics, loading/empty/offline/error states, retry/cancel/resume and confirmations for risky actions.
- Team discussions, files and artifacts must honor read/edit/discuss capabilities. Connector setup, team management, schedules and Product Studio must work end-to-end; clearly label sample/demo data.

## 8. Cloud operations
- Production architecture should separate API, durable workers and untrusted code sandbox. Consider managed PostgreSQL, object storage, secret management/KMS, HTTPS, controlled ingress, logs/metrics/alerts, health/readiness, graceful shutdown, migrations/rollback, backups/restore and spend controls.
- Provide an environment template with placeholders only. Do not claim cloud resources or public hosting exist until provisioned and smoke-tested.

## 9. Definition of done and priorities
For each feature verify UI → authenticated API → server authorization → persisted state/job → service/tool → validated result → UI feedback, including negative paths. Add migrations/contracts/tests; run relevant tests, type checks, build and E2E where possible; report exact results and limitations honestly. Never weaken tests, stub security, fake integrations or mark incomplete work complete.

Priority order:
1. Audit current modules into working/partial/missing/blocked with file paths/tests.
2. Fix tenant isolation, OAuth/team permissions, secret custody, governance and sandbox boundaries.
3. Complete Google/GitHub OAuth and workspace capabilities.
4. Complete GitHub MCP read-only connect/discover/test/invoke.
5. Complete one durable background monitor.
6. Complete idea → PRD DOCX → generated app → isolated tests → live preview.
7. Add approval-gated writes, measurable feedback loop, then cloud deployment and recovery.
