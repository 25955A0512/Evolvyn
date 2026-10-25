# Evolvyn Harness Test Plan and Operational Readiness

**Status:** Validation plan  
**Reviewed:** 2026-10-25  
**Companion:** [Harness Engineering and Skills Registry](HARNESS_ENGINEERING_AND_SKILLS.md)

> This is a test and operations plan. It does not claim these tests have been run or that production readiness has been established.

## 1. Change checklist

For each harness, skill, model-routing, tool or MCP change:

1. Read AGENTS.md, docs/PROGRESS.md, docs/GOVERNANCE.md, docs/SECURITY.md and the affected implementation.
2. Record the goal, affected trust boundary, data scope, risk class and rollback plan.
3. Add deterministic tests for authorization, schema, approval and budget invariants.
4. Add success-path, provider-failure, timeout, cancellation and partial-failure tests.
5. Run focused backend tests, then the relevant full backend suite.
6. Run frontend typecheck/build and targeted browser flows if UI is affected.
7. Test provider behavior in a non-production environment with least-privilege credentials.
8. Inspect logs/errors for secret leakage and verify audit events.
9. Record exact commit SHA, commands, environment and pass/fail/skip counts.
10. Roll out with restricted allowlists or feature flags where possible and keep a rollback path.

Never infer test success from a code review or from documentation.

## 2. Minimum test matrix

| Area | Scenario | Expected behavior |
|---|---|---|
| Graph validation | Duplicate node IDs, unknown edge endpoints, invalid entry, unknown fields | Rejected before execution |
| Resource bounds | Step, node-visit, tool-call, output-token or wall-clock budget exhausted | Run stops with explicit reason |
| Authorization | Missing capability, viewer attempts mutation, editor attempts admin action | Denied server-side |
| Tenant isolation | Actor guesses another organization's resource ID | No disclosure or mutation |
| Tool schema | Missing, extra or invalid arguments | Rejected before adapter invocation |
| Tool lifecycle | Disabled/unregistered tool is requested | Denied |
| Approval | Consequential write without approval | Paused/denied; no side effect |
| Approval binding | Arguments or server config change after approval | Approval invalidated |
| Replay prevention | Same approval consumed twice | Second use denied |
| Credential custody | Token appears in API output, prompt, artifact or logs | Test fails |
| MCP SSRF | Loopback/private/link-local address or unsafe DNS resolution | Registration/invocation rejected |
| Provider timeout | Read call times out | Bounded retry only when classified retryable |
| Ambiguous mutation | Remote write times out after request may have been sent | Mark uncertain; reconcile before retry |
| Persistence | Worker restarts after checkpoint | Safe resume or explicit recovery failure |
| Revocation | Membership/credential revoked while run waits | Resume/invocation blocked |
| Cancellation | User cancels while graph is running | Future work stops; in-flight writes reconciled |
| Evidence | Model cites source not in evidence set | Rejected or explicitly marked unverified |
| Data policy | External processing disabled | No external model/provider request containing protected data |
| Skill publication | Draft/disabled skill is invoked in production | Invocation rejected |
| Skill isolation | Skill references tool outside its allowlist | Invocation denied |
| Skill versioning | Published version edited in place | Mutation rejected; new version required |
| Evaluation | Required skill safety test fails | Publishing blocked |

## 3. Evidence and outcome quality

Classify each material statement as one of:
- **Observed fact:** deterministic query or directly captured source data.
- **Sourced finding:** evidence with source ID/URL and retrieval timestamp.
- **Hypothesis:** possible explanation that remains unproven.
- **Recommendation:** proposed action and rationale.
- **Approved action:** authorized by the correct person/policy.
- **Execution receipt:** provider or internal system evidence of an operation.
- **Verified outcome:** measurement from a defined source and period.

For business experiments, capture baseline window, intervention date, segment, experiment/campaign ID, primary metric, guardrail metrics, attribution method, duration, sample limitations and stop criteria. Compare like-for-like windows. Without valid attribution or a control, report observed change without claiming that the action caused it.

## 4. Operational metrics

Monitor:
- Runs by terminal/intermediate status and skill/workflow version.
- Queue wait and p50/p95 duration.
- Provider errors, rate limits and timeout rates.
- Tool calls by adapter and risk class.
- Approval wait, rejection and invalidation rates.
- Budget exhaustion, retries and cancellation rates.
- MCP authentication/connection failures and stale credentials.
- Schema/evidence validation failures and unsupported claims.
- Token usage and estimated cost.
- Uncertain remote writes and time to reconciliation.
- Checkpoint resume/recovery success.
- Policy denials and suspected cross-tenant access.

Keep customer data and secrets out of metric labels. Alert on repeated provider failures, unusual tool/risk growth, spend spikes, credential expiry, recovery failure, unreconciled writes and possible secret disclosure.

## 5. Incident response runbook

1. **Contain:** disable the affected tool/server/skill or lower its policy ceiling.
2. **Preserve:** retain run IDs, sanitized events, timestamps and config/version fingerprints.
3. **Scope:** identify affected organizations, projects, runs, data and external systems.
4. **Reconcile:** determine whether external side effects happened despite a timeout.
5. **Recover:** rotate/revoke credentials if necessary and restore safe configuration.
6. **Replay carefully:** replay only when idempotency and remote state are understood.
7. **Communicate:** distinguish verified facts, likely causes and unknowns.
8. **Prevent recurrence:** add regression tests, update the runbook and review similar adapters.

Incident record fields: incident ID/severity/owner; affected commit/config; first observed time; affected org/project/run IDs; expected versus actual behavior; sanitized timeline; possible external side effects; containment; reconciliation result; impact and uncertainty; root cause; regression test; follow-up owner/date.

## 6. Release gates

Do not describe the platform as production-ready until the team has:
- Reproducible current-commit test evidence.
- Tenant, role, approval, schema, budget and secret-handling tests.
- Worker restart, checkpoint, cancellation and duplicate-delivery tests.
- Provider OAuth refresh/revocation/reconnect validation.
- Distributed rate limits, concurrency caps, provider quotas and cost accounting.
- Backup/restore drills, key rotation and incident ownership.
- TLS, secure cookies, origin/host controls and public-deployment review.
- Retention/deletion/export decisions and identity recovery procedures.
- Independent threat modelling and penetration testing.
- Non-production acceptance tests for every claimed external integration.
- A separately isolated ephemeral sandbox before executing generated code.
- Documented rollback and feature-disable procedures.

## 7. Honest release statement template

> On commit <SHA>, we ran <commands> in <environment>. <N> tests passed, <M> failed, and <K> were skipped. Coverage included <areas>. The following remain unverified: <live integrations, production deployment, security review>. This evidence applies only to the stated scope and is not a blanket guarantee of safety or production readiness.
