# Evolvyn: Harness Testing and Operations

## 1. Purpose

Use this checklist when changing the harness, agents, skills, tools, model routing, or MCP integrations. Record test results from the actual commit; do not infer that tests passed from code review.

## 2. Minimum test checklist

| Area | Test | Expected result |
|---|---|---|
| Workflow validation | Invalid nodes, edges, or inputs | Rejected before execution |
| Execution limits | Step, tool-call, output, or time budget exceeded | Run stops with a clear reason |
| Permissions | Missing role/capability or cross-organization access | Denied |
| Tool schema | Invalid arguments or disabled tool | Rejected before invocation |
| Approval | Write attempted without approval | No side effect |
| Approval binding | Arguments or server configuration changed | Approval invalidated |
| Replay | Approval used twice | Second use denied |
| Credentials | Secret appears in model context, API response, or logs | Test fails |
| MCP security | Unsafe/private endpoint | Registration or invocation rejected |
| Remote timeout | Write may have reached provider | Reconcile before retry |
| Recovery | Worker restarts during a run | Safe resume or explicit recovery failure |
| Evidence | Unsupported citation or claim | Rejected or marked unverified |
| Cancellation | Run cancelled while active | Future steps stop; in-flight writes reconciled |
| Skills | Draft/disabled skill or unapproved tool reference | Execution denied |

## 3. Evidence and business outcomes

Keep these categories separate:
- **Fact:** Directly supported by data or a deterministic calculation.
- **Finding:** Supported by a cited source.
- **Hypothesis:** A possible explanation that is not yet proven.
- **Recommendation:** A proposed action.
- **Execution receipt:** Evidence that an operation was accepted or performed.
- **Verified outcome:** A measured result from a defined source and time period.

For experiments, record the baseline, intervention date, target group, campaign/experiment ID, primary metric, guardrail metrics, duration, and attribution method. Without reliable attribution, report observed changes without claiming causation.

## 4. Monitoring

Track:
- Run status, duration, and queue wait.
- Model/provider errors and timeouts.
- Tool calls by type and risk level.
- Approval waits, denials, and failures.
- Budget exhaustion, retries, and cancellation.
- MCP connection and authentication failures.
- Credential expiry and uncertain remote writes.
- Token usage, estimated cost, and checkpoint recovery.

Do not put credentials or sensitive customer data in logs or metric labels.

## 5. Release checklist

Before calling a change ready:
1. Run focused tests and the relevant full test suite.
2. Run frontend typecheck/build and affected UI tests when applicable.
3. Test external providers in a non-production environment.
4. Verify tenant isolation, approvals, secret handling, and failure recovery.
5. Record commit SHA, commands, environment, and pass/fail/skip counts.
6. Document untested integrations and remaining risks.
7. Keep a rollback or feature-disable path.

Production deployment additionally requires appropriate identity and credential lifecycle controls, rate limits, backups and restore testing, monitoring, and security review.

## 6. Test report template

> Commit: <SHA>  
> Environment: <environment>  
> Commands: <commands run>  
> Results: <passed / failed / skipped>  
> Coverage: <areas tested>  
> Not verified: <integrations or controls not tested>

A successful registration or unit test does not, by itself, prove that an integration or the overall platform is production-ready.
