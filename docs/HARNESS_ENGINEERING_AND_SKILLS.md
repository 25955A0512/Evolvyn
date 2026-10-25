# Evolvyn Platform Architecture: Harness, Registries, Governance and Gateways

## 1. How the harness is built around Evolvyn

Evolvyn's harness is the controlled execution layer around the platform's agents and workflows. It connects user goals, business context, model reasoning, registered tools, permissions, approvals, persistent execution and result tracking.

**Runtime flow**

User request → workspace and business context → agent/workflow graph → model gateway → proposed tool call → tool registry → governance/policy checks → approval if required → built-in or MCP adapter → result validation → persisted receipt, evidence and run state.

The model proposes what to do. The backend decides whether it is allowed, validates the request, executes it within limits and records what happened.

### Main implementation pieces

- **Graph harness — `backend/graph_harness.py`:** Validates declarative graphs and node/edge references; executes nodes with bounded steps, node visits, tool calls, output tokens and time; persists checkpoints; pauses and resumes at approval gates.
- **Tool execution — `backend/tool_plugins.py` and `backend/registry.py`:** Provides typed tool definitions and adapters, validates arguments against JSON Schema, checks tool availability and connects tool execution to policy and approval handling.
- **Policy engine — `backend/policy.py`:** Makes deterministic decisions about actor, organization/project scope, permissions, data access and action risk.
- **Agent/model layer — `backend/agent_gateway.py` and `backend/model_strategy.py`:** Routes model requests and bounded specialist-agent work; validates structured outputs and restricts evidence citations to authorized/supplied evidence.
- **Persistence:** Saves run/checkpoint state, approvals, events, artifacts, connector results and receipts so the UI can show progress and results rather than relying only on a transient model response.

The harness is shared infrastructure: chat, workflows, Growth Insights and tool-using features should go through the same policy-checked execution path rather than implement their own unrestricted tool calls.

## 2. How the MCP Registry fits in

The MCP Registry is the control-plane inventory for remote/local MCP connections and the tools they expose. Evolvyn's documented implementation includes persistent multi-server registration, health management, credential references, discovered capabilities, and built-in/MCP adapters.

**Registration lifecycle**
1. An owner/admin registers a server name, transport and endpoint or server profile.
2. Governance checks the hostname/endpoint; unsafe/private destinations are rejected.
3. Credentials are referenced through the Key Vault, not embedded in the server URL or model prompt.
4. Evolvyn tests the connection and discovers the server's tool definitions.
5. Tool metadata is made available to the Tool Registry and permitted agents/workflows.
6. At invocation time, Evolvyn re-checks server/tool status, caller permissions, risk, arguments and approval requirements.

Registering a server does not automatically make every tool available to every agent. A successful registration also does not prove that every provider operation or OAuth lifecycle is production-ready.

## 3. How the Tool Registry fits in

The Tool Registry describes **what Evolvyn can call** and how each operation must be invoked. It separates tool discovery from tool execution.

A tool definition includes its stable ID/name, adapter type (built-in or MCP), input schema, required capability/permission, risk class and execution metadata. The registry supports tool discovery and invocation from the platform's agent/workflow paths.

**Invocation path**

Agent/workflow requests a tool ID → registry resolves the registered tool → input schema is validated → governance/policy checks the actor and action → approval gate is checked → credentials are resolved server-side → adapter invokes the tool → result/receipt is validated and persisted.

This central path enables consistent enforcement and auditability across first-party tools and external MCP tools. Tool descriptions and results from external servers are treated as untrusted input.

## 4. How Governance and policy are built in

Governance is enforced at runtime in backend code; it is not just a settings page or a prompt instruction.

The current policy design includes:
- Organization and restricted-project access checks.
- Role and capability enforcement.
- Tool allowlists and action-risk limits.
- Data-processing/provider restrictions.
- Public hostname approval and unsafe endpoint checks for MCP registration.
- Owner/admin restrictions on credential management.
- Approval-bound writes, with approval tied to the intended arguments/configuration and protected against replay.
- Credential references backed by an encrypted vault; secret values are not returned by normal read APIs.

Risk levels in the policy model are `read`, `internal_write`, `external_write` and `critical`. The policy engine evaluates the action before execution. Consequential writes can pause for human approval; changed arguments or configuration must not reuse an earlier approval.

## 5. The gateways: model access versus tool execution

Evolvyn has two different boundaries that should not be confused:

### Model gateway
The agent/model layer routes requests to configured model providers and applies model-access, structured-output and evidence-handling controls. It controls how agents use models; it is not the authority that grants business permissions.

### Tool/MCP execution gateway
The shared backend tool-execution path is the enforcement point between an agent and a tool. It validates the requested tool and arguments, checks policy and approval, resolves credentials, invokes the built-in/MCP adapter, and records the result.

**Important architecture distinction:** The current documentation describes a shared application-level MCP/tool execution gateway and registry. Do not describe Evolvyn as having a separate standalone network reverse-proxy MCP gateway unless such a deployed proxy exists and is verified.

## 6. How the components work together

Example: an agent recommends a change based on e-commerce data.

1. The agent obtains authorized sales/catalog evidence.
2. Deterministic application queries calculate the metrics; the model interprets them and proposes a recommendation.
3. If a tool is needed, the agent requests a registered tool by ID.
4. The Tool Registry resolves the tool and validates its arguments.
5. Governance checks workspace/project access, permissions, risk and policy.
6. If the action requires approval, the harness persists the pending action and pauses.
7. After authorized approval, the tool adapter executes the exact approved action.
8. Evolvyn records the result/receipt and verifies the effect where possible.
9. The run state and evidence are persisted for the UI and later outcome comparison.

## 7. Current implementation versus next work

**Documented in the repository:** bounded graph execution and checkpoints; typed tool registration and invocation; JSON Schema argument validation; central risk/data/role policy; argument-bound approval handling; persistent multi-server MCP registry; server health and credential references; built-in/MCP adapters; model routing; evidence-oriented outputs; and persisted execution records.

**Must be verified before claiming complete:** live third-party MCP/OAuth acceptance for each provider; full production deployment and operational recovery; current-commit test results; and whether a dedicated, separately deployed network MCP proxy exists.

**Skills registry note:** Skills are reusable procedures that bind an agent/workflow to a defined task and permitted tools. The skills lifecycle (versioning, validation, review, publishing and evaluations) is a separate layer to implement or verify; it should use the existing harness, Tool Registry and Governance rather than bypass them.

## 8. Repository map

| Area | Main file / reference |
|---|---|
| Bounded workflow execution | `backend/graph_harness.py` |
| Typed tool registration and execution | `backend/tool_plugins.py`, `backend/registry.py` |
| Runtime authorization and risk | `backend/policy.py` |
| Agent/model orchestration | `backend/agent_gateway.py`, `backend/model_strategy.py` |
| Governance rules | `docs/GOVERNANCE.md` |
| Implementation status and test notes | `docs/PROGRESS.md` |
| MCP setup | `docs/CUSTOM_MCP_SERVER.md`, `docs/ACCOUNT_CONNECTOR_OAUTH.md` |

This document explains the platform's architecture and execution boundaries. Test status and live provider readiness should be reported only from recorded results for the exact commit and environment.
