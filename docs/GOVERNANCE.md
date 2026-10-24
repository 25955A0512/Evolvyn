# Governance boundaries

Credential administration is restricted to organization owners/admins. Vault values are encrypted in PostgreSQL, never returned by a read API, and resolved only inside server-side provider/MCP calls. Model outputs cannot authorize tools or change policy.

Organization and restricted-project scope apply to resources, memory, prototypes, conversations, executions, schedules and source artifacts. Specialist capability sets restrict graph tool nodes; supervisor authority remains bounded by organization policy. Background actors and external-processing policy are revalidated before model calls. New periodic work preserves its creator and is stopped if membership is revoked.

Consequential registered tools require approval bound to exact arguments and current tool/server configuration. Credentials, source text and model output cannot create approval flags. The legacy experiment-brief endpoint cannot approve graph or discussion executions. Discussion approval records a reviewed decision; explicit user changes are needed to apply it to product requirements. Requirement versions and source artifacts remain separately reviewable.

Source generation is a trusted adapter operation. The prototype does not run arbitrary generated code. Deployments, campaigns, third-party mutations and arbitrary code execution are not automatically authorized or implemented. See MODERN_STACK.md and CLOUD_DEPLOYMENT.md for current controls and required production gates.
