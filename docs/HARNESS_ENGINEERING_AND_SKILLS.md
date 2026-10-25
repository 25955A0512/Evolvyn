# Evolvyn Harness Engineering, Skills Registry and Operations

**Status:** Architecture specification and implementation roadmap  
**Reviewed:** 2026-10-25  
**Repository:** 25955A0512/Evolvyn

> This document separates existing repository mechanisms from proposed capabilities and production gates. Documentation is not proof of implementation, test success, or production readiness.

## 1. Executive summary

Evolvyn is an evidence-driven continuous business evolution platform. Its operational loop is: understand the business → detect changes → investigate with evidence → choose a strategy → execute safely → verify results → improve future decisions.

Harness engineering is the control system around an LLM. The model may interpret evidence and propose a plan, but deterministic application code must own identity, permissions, tool validation, budgets, approval, persistence, retries, audit events and verification. The model is not the security boundary.

Evolvyn already has important building blocks in its repository: LangGraph workflows, a bounded declarative graph harness, typed built-in/MCP tool registration and invocation, deterministic policy checks, argument/configuration-bound approval logic, model routing, persistence/checkpointing and evidence-oriented output handling. See the repository code map below. A first-class versioned skills registry, comprehensive automated evaluation lifecycle and production operations readiness must be verified independently; this document defines the target contract rather than claiming those are all implemented.

## 2. Harness architecture

### Components and responsibilities

1. **Goal/request layer:** receives the user goal, identifies the organization/project and validates the requested operation.
2. **Context and evidence layer:** retrieves authorized business records, documents and public research. SQL/application code calculates numerical KPIs; model-generated interpretations remain distinguishable from facts.
3. **Agent/workflow layer:** selects only relevant specialists and executes a validated workflow. Reuse LangGraph and the existing harness instead of adding a parallel orchestration engine without a demonstrated need.
4. **Model access/routing:** chooses a configured provider/model under server-side policy. Model output cannot alter permissions, policy, approval state or global budgets.
5. **Skill registry (target contract):** selects a versioned procedure and defines its intended inputs, context, tool references and output requirements.
6. **Tool registry:** maps stable tool IDs to typed built-in or MCP adapters, schemas, risk, permissions, capabilities, timeouts and enabled state.
7. **Policy gateway:** enforces actor/organization/project scope, role, allowlist, risk ceiling, external-processing rules and approval requirements.
8. **Credential vault:** resolves credentials inside trusted server-side adapters. Secrets never enter prompts, browser responses or normal logs.
9. **Execution/persistence layer:** records run state, checkpoints, approvals, events, artifacts and receipts; supports bounded execution and recovery.
10. **Evaluation/observability:** checks policy invariants, evidence quality, tool outcomes, latency, resource usage and measured business results.

### Runtime sequence

1. Authenticate actor and resolve organization/project scope.
2. Load only authorized context; check external-processing permissions before sending data to a provider.
3. Select the appropriate workflow/skill version and expose only its explicitly allowed tools.
4. Validate graph structure, input schemas, references and limits.
5. Execute under step, visit, tool-call, token, output-size, timeout and wall-clock budgets.
6. Before every tool call, re-check actor membership, capability, organization/project scope, tool/server status, schema, risk and policy.
7. Pause before consequential actions and persist the exact pending action.
8. Verify approval still matches the action and current configuration; consume it once.
9. Resolve credentials server-side, invoke adapter, validate result and record a sanitized receipt.
10. Verify external effect where possible. A successful HTTP response is not necessarily proof of a business outcome.
11. Persist final state and evidence. If interrupted, resume from a safe checkpoint or mark outcome unknown and reconcile.

### Non-negotiable invariants

- Authorization is enforced in backend code, never only in UI or prompts.
- Every resource, query, artifact, background task, memory record and approval is scoped to the correct organization/project.
- Unknown tools, invalid schemas, missing permissions and invalid approvals fail closed.
- Every tool call passes through the governed gateway; no bypass through arbitrary URLs, shell commands or generated code.
- Approval is bound to the exact tool/action, normalized arguments, actor/scope and relevant tool/server configuration. Changes invalidate it.
- Use idempotency keys where supported. Never blindly retry a remote mutation after a timeout that may have occurred after the provider accepted it; reconcile first.
- Bound graph steps, node visits, tool calls, model output, time, retries, concurrency and cost.
- Treat retrieved documents, web pages, MCP descriptions and tool output as untrusted data. Prompt injection cannot grant authority.
- Distinguish observed facts, sourced findings, hypotheses, recommendations, approved actions, execution receipts and verified outcomes.
- Never fabricate citations, metrics, provider connectivity or action success.

## 3. Budgets, retries and recovery

The current graph harness schema defines explicit maxima, including up to 32 nodes, 64 edges, 100 steps, 64 tool calls, 8,192 output tokens and 600 seconds overall; per-node visit, timeout and retry bounds also exist. These are hard ceilings, not suggested defaults for every workflow. Policy may set lower limits. Verify effective configuration before relying on any number.

Retry only bounded, retryable transient failures. Do not retry schema, authorization, approval or policy failures. For a remote write with an ambiguous timeout, mark the outcome uncertain and reconcile provider state before retry. Cancellation should stop future steps, while in-flight remote mutations may still require reconciliation. On worker restart, resume from durable checkpoint only if state and permissions remain valid; re-check membership and policy before resuming.

Failure behavior:
- Invalid workflow/tool input: reject before side effects.
- Permission/tenant mismatch: deny and record a safe audit event.
- Approval pending: persist and pause.
- Changed arguments/configuration: invalidate approval.
- Budget exhausted: stop with explicit reason.
- Provider error: redact secrets and preserve safe diagnostic context.
- Citation not present in supplied evidence: reject, repair or label unverified.
- Credential revoked or membership removed: block subsequent work.
- Uncertain external write: reconcile, do not blindly replay.

## 4. Skills registry: definition and contract

A **skill** is a reusable, versioned procedure describing how to complete a class of work. It is not a credential, an unrestricted tool, an agent with universal permissions, or a script that may execute arbitrary code.

Distinguish:
- **Skill:** procedure, intended use, input/output contract, context requirements and explicit tool references.
- **Tool:** callable operation with input/output schema, permission, risk and adapter.
- **MCP server:** service exposing tools over MCP.
- **Connector:** provider authorization/data-access setup, such as OAuth.
- **Agent:** bounded reasoning role with a limited capability set.
- **Workflow/harness:** deterministic runtime that sequences work and enforces controls.

### Proposed SkillManifest fields

| Field | Purpose |
|---|---|
| id | Stable identifier, e.g. ecommerce.performance_diagnosis |
| name / summary | Human-readable purpose |
| version | Immutable version |
| when_to_use / exclusions | Trigger and non-trigger conditions |
| input_schema | Strict JSON Schema for required inputs |
| context_requirements | Required data scope, evidence type and freshness |
| tool_refs | Explicit stable tool IDs; never arbitrary URLs/commands |
| workflow_ref | Optional validated workflow/version |
| instructions | Bounded guidance treated as untrusted content, not policy |
| output_schema | Expected structured result and evidence fields |
| permissions | Required actor capabilities and data scopes |
| risk_profile | Maximum action risk and approval policy |
| limits | Skill-level budgets that cannot exceed global ceilings |
| status | draft, review, published, deprecated or disabled |
| owner / scope | Owning organization/team and visibility |
| provenance | Built-in, organization-authored or third-party source/checksum |
| evaluation_suite | Versioned test cases and acceptance criteria |
| timestamps | Creation, update and publication audit metadata |

Reject unknown fields, invalid references, unpublished/disabled versions, excessive limits and missing permissions. Published versions should be immutable; edits create a new version.

### Skill lifecycle

1. Create/import as draft; never auto-execute imported instructions.
2. Validate schema, IDs, size, tool references, scopes and budgets.
3. Review for prompt injection, exfiltration, privilege escalation, destructive actions and approval bypass.
4. Run offline evaluations against fixtures/mocked tools.
5. Require authorized review before publishing shared/production skills.
6. Bind a pinned skill version to a specific agent/workflow and tool allowlist.
7. Execute only through the existing bounded harness.
8. Record skill/version, workflow/model versions, tool IDs, policy decisions, approvals, artifact references, duration and outcome.
9. Improve through reviewed feedback and regression cases; never silently mutate a published version.
10. Deprecate/revoke versions and re-check revocation when resuming background runs.

### Separate registries and responsibilities

- **Skill registry:** versioned procedure metadata, lifecycle, tool references, tests, provenance and owner.
- **Tool registry:** adapter, tool ID, schemas, capability, entity/data domain, permission, risk, timeout, idempotency, enabled state and config/version fingerprint.
- **MCP server registry:** display name, transport, endpoint/server profile, approved host, credential reference, health and discovered tool snapshots.
- **Credential vault:** encrypted secret/OAuth data and lifecycle metadata; never return secret values through normal APIs.
- **Policy/governance:** host allowlists, role/capability checks, data-processing policy, tool allowlists/denylists, risk ceiling, approval rules and budgets. The model cannot edit these.
- **Execution records:** runs, checkpoints, tool events, approval transitions, receipts, artifacts and outcome measurements.

Do not create duplicate registries/tables before auditing existing persistence. Extend existing typed records and migrations where they can represent the contract safely.

## 5. Tool and MCP execution contract

Execution path:

**Skill/agent → stable tool ID → schema validation → actor/scope checks → capability and risk checks → approval gate → credential resolution → built-in/MCP adapter → timeout and output validation → receipt/audit event → evidence/result verification.**

For remote MCP:
- Approve the hostname through governance before registering the server.
- Use HTTPS and reject loopback/private/link-local destinations and unsafe DNS resolutions.
- Keep credentials as vault references; never inline tokens in URLs or prompts.
- Discover tools and schemas, but treat remote descriptions and results as untrusted.
- Re-check server/tool enabled state, identity, policy and risk at every invocation.
- Bound time, output size and concurrency; redact provider errors.
- Test authentication and a real read/write operation separately from successful registration.
- A registry “connected” status is not proof every tool works, OAuth scopes are sufficient, or writes are safe.

For Google Docs specifically, the remote endpoint is OAuth-based. A generic bearer-token environment variable is not automatically equivalent to a valid OAuth access/refresh-token lifecycle. Confirm Evolvyn's supported OAuth flow, scopes, callback, token refresh and vault integration before marking it production-ready.

## 6. Risk and approval policy

Repository policy defines risk levels: read, internal_write, external_write and critical. Policy checks include role, organization settings, tool allowlist and maximum risk. Consequential registered tools should require explicit approval bound to exact arguments and configuration.

Recommended defaults:
- **Read:** authorized data access only; still enforce scope and data minimization.
- **Internal write:** create internal draft/task/brief. Apply approval where consequences warrant it.
- **External write:** send/publish, change customer-facing settings, modify live campaigns or spend budget. Explicit approval by default.
- **Critical:** destructive, high-impact financial/legal/security or irreversible action. Human-led or disabled unless separately reviewed.

A dropdown setting alone is not proof that enforcement is correct; verify policy and adapter behavior with tests.

## 7. Starter skill catalogue (proposed, not claimed as implemented)

1. **ecommerce.performance_diagnosis** — Calculate sales/conversion/catalog metrics using deterministic queries; cite source rows and metric definitions; flag anomalies and data-quality issues.
2. **research.competitor_snapshot** — Gather public dated evidence with URLs, retrieval timestamps, source summaries and uncertainty; never represent public chatter as internal revenue/customer facts.
3. **growth.experiment_proposal** — Propose a hypothesis, segment, baseline, treatment/control where feasible, primary and guardrail metrics, duration, budget, stop criteria and attribution plan. Launch remains approval-gated.
4. **documents.review_and_summarize** — Summarize authorized docs with section/page references and action items; ignore embedded instructions that conflict with policy.
5. **operations.alert_triage** — Classify alert, collect read-only diagnostics, find runbook and recommend escalation. No production mutation without separate approval.
6. **product.requirements_to_prd** — Convert interview and approved notes into versioned PRD with assumptions, acceptance criteria, risks and unresolved decisions.

Start with one complete vertical slice rather than many half-built skills. The recommended first slice is e-commerce performance diagnosis through evidence-backed recommendation and a safely approved internal follow-up.

## 8. Evaluation and testing strategy

Test deterministic harness safety separately from model quality.

### Mandatory policy tests
- Unknown/disabled tool denied.
- Missing role/capability and cross-organization/project access denied.
- Invalid tool arguments rejected before invocation.
- Write without approval does not execute.
- Changed arguments or server config invalidate approval.
- Approval cannot be replayed.
- Step/tool/token/time budgets terminate the run.
- Membership revocation blocks a paused/resumed run.
- Secrets do not appear in API output, model context or logs.
- Unsafe MCP target/private IP/DNS rebinding attempt rejected.
- Ambiguous remote write timeout is not blindly retried.
- External processing disabled means no external model/provider call.

### Workflow/evidence tests
- KPI calculations and source row attribution are correct.
- Citations refer only to supplied evidence.
- Empty, stale and contradictory data are disclosed.
- Fallback behavior is labelled.
- Approval pause/resume, cancellation, checkpoint restart and partial failures work.
- Experiment comparison uses defined windows and does not infer causality from correlation alone.

### Model-quality evaluation
Maintain versioned representative cases and measure tool choice, argument validity, evidence coverage, unsupported claims, policy adherence, task completion, latency and cost. Use deterministic assertions for security; model-as-judge is supplementary only. Run regression cases before publishing a skill or changing routing/prompts.

## 9. Observability and incident response

A run should answer: who initiated it, for which scope, which workflow/skill/model version ran, what sources were read, which tools were called, what policy/approval decisions occurred, what artifacts/receipts were created, resource consumption, terminal status and whether outcome was verified.

Suggested event fields: run ID, organization/project, actor/role, workflow and skill versions, node/tool IDs, timestamp, event type, policy reason code, approval ID, argument digest (not raw secrets), config fingerprint, receipt reference, retry count, elapsed time, token/cost estimate and terminal status.

Never log access/refresh tokens, client secrets, full sensitive documents or raw arguments by default.

Incident response: contain by disabling affected tool/skill or lowering policy ceiling; preserve sanitized event timeline and fingerprints; identify affected organizations/runs; reconcile possible external writes; revoke/rotate credentials if needed; restore safe config; add regression tests and document verified facts versus unknowns.

## 10. Production readiness gates

Before describing the system as production-ready:
- Run backend/frontend/integration/browser suites on the exact commit and record command, environment, pass/fail counts.
- Verify worker crash/restart, durable checkpoints, cancellation and duplicate delivery.
- Verify rate limits, provider quotas, concurrency caps and cost accounting.
- Test OAuth scopes, refresh, revocation, reconnect UX and provider approval requirements.
- Complete identity recovery/MFA decisions, retention/deletion/export controls and incident ownership.
- Conduct independent threat modelling and penetration testing, including SSRF/DNS rebinding, prompt injection, OAuth state and tenant isolation.
- Test every external integration in a non-production environment.
- Verify TLS, secure cookie/origin/host configuration, backups and restore drills, key rotation and alerts.
- Keep arbitrary generated-code execution out of the API; use an isolated ephemeral sandbox with strict resource/network limits before executable previews.
- Measure real business outcomes with attribution and avoid causal overclaiming.

## 11. Repository code map

- **backend/graph_harness.py:** bounded declarative graph/node/edge validation, execution budgets, checkpointing and approval pauses.
- **backend/tool_plugins.py:** typed built-in/MCP tool registration and invocation, JSON Schema argument validation, risk integration and argument/configuration fingerprints.
- **backend/policy.py:** deterministic principal/organization/role and tool-risk/policy enforcement.
- **backend/registry.py:** built-in tool definitions and execution context; inspect schemas before adding new tools.
- **backend/agent_gateway.py and backend/model_strategy.py:** model access/routing and evidence-oriented output behavior.
- **backend/execution_queue.py and persistence modules:** background work and durable state; verify deployment and crash-recovery behavior in the target environment.
- **docs/GOVERNANCE.md:** authorization and approval boundaries.
- **docs/SECURITY.md:** implemented controls and limitations.
- **docs/PROGRESS.md:** current implementation notes and outstanding items.
- **docs/PRD.md and docs/PRODUCT_REQUIREMENTS.md:** product intent and acceptance criteria.
- **tests/**: current automated assertions. A test's existence is not evidence it passed on the current commit.

## 12. Known gaps and honest status

This specification does not claim that every proposed skill lifecycle, evaluation dashboard, production alert, external connector, OAuth lifecycle or isolated code sandbox is implemented. The current repo's tool registry and bounded harness are the foundation. Verify implementation and tests before describing a feature as complete.

Historically documented work still requiring explicit current verification includes live-provider acceptance, full current-commit test runs, production identity/recovery and retention operations, independent security review, public deployment/TLS and real business-outcome validation. AWS topology documents are guidance, not proof infrastructure is provisioned.

## 13. Definition of done

A harness/skill feature is done only when its UI, API, persistence, authorization, tool path, approval semantics, failure handling, audit events, tests and documentation agree. A visible control, a successful server registration, or one passing unit test is not enough.

For release evidence, use this template:

> On commit <SHA>, we ran <commands> in <environment>. <N> tests passed; <M> failed or were skipped. Coverage included <areas>. The following remain unverified: <live integrations, deployment, security review>. This evidence supports only the listed scope and is not a blanket guarantee of safety or production readiness.
