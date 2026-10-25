# Evolvyn: Harness Engineering and Skills Registry

## 1. Purpose

Harness engineering is the system around an AI model that makes agent execution controlled, reliable, and observable. In Evolvyn, the model reasons and proposes actions; application code enforces permissions, validates tools, manages approvals, limits execution, stores state, and records results.

## 2. Harness architecture

The main execution flow is:

**User goal → Context and evidence → Agent/workflow → Tool validation → Policy checks → Approval if required → Tool execution → Result verification → Audit and persistence**

Key components:
- **LangGraph and execution harness:** Orchestrate workflows and manage execution state.
- **Model gateway/routing:** Selects configured models without granting them extra permissions.
- **Tool registry:** Defines available built-in and MCP tools, schemas, and risk levels.
- **Policy engine:** Enforces organization scope, roles, permissions, tool allowlists, and approval rules.
- **Credential vault:** Keeps provider credentials out of prompts, logs, and normal API responses.
- **Persistence and checkpoints:** Store run state, events, approvals, and artifacts.
- **Evidence layer:** Connects recommendations to source data and records.

## 3. Core safety rules

- Every tool call must pass server-side authorization and schema validation.
- Agents can access only the tools and data explicitly allowed for their role and organization.
- The model cannot change permissions, approve its own actions, or increase execution limits.
- External writes—such as publishing, sending messages, or changing live business settings—require approval by default.
- Approval applies to the specific action and arguments; changed actions need new approval.
- Bound steps, tool calls, output size, retries, and execution time.
- Do not blindly retry a remote write after a timeout; check whether it succeeded first.
- Treat documents, websites, and MCP responses as untrusted input.
- Distinguish facts, hypotheses, recommendations, executed actions, and verified outcomes.

## 4. Skills registry

A **skill** is a reusable, versioned procedure that tells an agent how to complete a task. It is different from a tool: a skill describes the process; a tool performs an operation.

A skill definition should include:
- ID, name, version, and purpose.
- When to use it and required inputs.
- Context/data requirements.
- Explicit tool IDs it may use.
- Expected output format.
- Required permissions and maximum risk.
- Execution limits, owner, status, and evaluation cases.

### Skill lifecycle

1. Create a draft.
2. Validate its schema, inputs, tool references, permissions, and limits.
3. Review its instructions for unsafe actions or attempts to bypass policy.
4. Test it with representative cases.
5. Publish an approved, versioned release.
6. Bind it to an agent or workflow with explicit tool permissions.
7. Monitor results and improve through a new version.
8. Disable or retire unsafe or outdated versions.

Published versions should not change silently. Imported skill instructions must never grant new permissions or bypass the tool gateway.

## 5. Registry responsibilities

| Component | Responsibility |
|---|---|
| Skills registry | Versioned task procedures, inputs/outputs, lifecycle, and evaluations |
| Tool registry | Callable tools, schemas, permissions, risk, and adapters |
| MCP registry | Server endpoint, transport, credential reference, and discovered tools |
| Key Vault | Secure storage and resolution of credentials |
| Governance | Approved hosts, role rules, tool access, risk limits, and approvals |
| Execution records | Run state, decisions, approvals, tool results, and artifacts |

For MCP servers, approve the hostname, use HTTPS, keep credentials in the vault, validate tool inputs, and re-check permissions on every call. Successful registration alone does not prove authentication and tool execution work correctly.

## 6. Initial skills for Evolvyn

These are recommended starting skills, not a claim that all are already implemented.

- **E-commerce performance diagnosis:** Calculate KPIs, detect changes, and link findings to source data.
- **Competitor research:** Collect dated public evidence with source links and limitations.
- **Growth experiment proposal:** Define a hypothesis, target, metrics, duration, and attribution plan.
- **Document summary:** Summarize authorized documents with source references.
- **Alert triage:** Gather diagnostics and recommend next steps.
- **Requirements to PRD:** Convert approved requirements into a structured product document.

Start with one complete workflow—e-commerce performance diagnosis through evidence-backed recommendations—before expanding the catalogue.

## 7. Repository implementation map

- `backend/graph_harness.py` — bounded workflow execution, validation, checkpoints, and approval pauses.
- `backend/tool_plugins.py` — tool registration/invocation, schema validation, and approval integration.
- `backend/policy.py` — role, organization, risk, and policy checks.
- `backend/agent_gateway.py`, `backend/model_strategy.py` — model access and routing.
- `backend/registry.py` — built-in tool definitions.
- `docs/GOVERNANCE.md`, `docs/SECURITY.md`, and `docs/PROGRESS.md` — governance, security, and implementation status.

## 8. Implementation status

The existing harness, tool registration, policy checks, and workflow controls provide the foundation. A complete first-class skills lifecycle—versioning, review, publishing, and evaluations—must be confirmed in code before being described as fully implemented. Run the relevant tests on the current commit before making claims about test status or production readiness.
