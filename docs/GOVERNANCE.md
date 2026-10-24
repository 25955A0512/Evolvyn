# Governance boundaries

Credential administration is restricted to organization owners/admins. Vault values are encrypted in PostgreSQL, never returned by a read API, and resolved only inside server-side provider/MCP calls. Model outputs cannot authorize tools or change policy.

Organization and restricted-project scope apply to resources, memory, prototypes, conversations, executions, schedules and source artifacts. Specialist capability sets restrict graph tool nodes; supervisor authority remains bounded by organization policy. Background actors and external-processing policy are revalidated before model calls. New periodic work preserves its creator and is stopped if membership is revoked.

Consequential registered tools require approval bound to exact arguments and current tool/server configuration. Credentials, source text and model output cannot create approval flags. The legacy experiment-brief endpoint cannot approve graph or discussion executions. Discussion approval records a reviewed decision; explicit user changes are needed to apply it to product requirements. Requirement versions and source artifacts remain separately reviewable.

Source generation is a trusted adapter operation. The prototype does not run arbitrary generated code. Deployments, campaigns, third-party mutations and arbitrary code execution are not automatically authorized or implemented. See MODERN_STACK.md and CLOUD_DEPLOYMENT.md for current controls and required production gates.

## Growth, canvas and exported runtimes

Growth fetches require explicit source selection and external-processing permission. MCP context must be read-only and passes the existing gateway policy. Public discussion counts are not revenue/demand/customer facts. Recommendations remain hypotheses; saving a decision memory requires review, and changing a product requires explicit field changes and a new revision.

Canvas geometry, strokes and graph sizes are bounded. Labels render as text, never HTML/code. Saved graph references retain linked-resource checks. Product application checks both revisions and project scope under row locks. Existing builds are immutable. New products receive allowlisted runtime source, fresh identity/database/vault, separate private networks and browser-cookie namespaces, and no tenant configuration or secrets. Product data access requires a deliberate upload/connector, not a shared production database credential.

OAuth state is short-lived, browser-bound and consumed once; token exchange uses PKCE and fixed TLS provider endpoints. Provider email must be verified. Existing local accounts require explicit authenticated linking rather than matching email. Provider access tokens are transient; they are not persisted or passed to agents. Sessions are hashed/revocable, password change revokes all sessions, and the account panel can revoke all devices. These controls do not replace MFA, recovery, email verification, TLS, egress controls or independent production review.
