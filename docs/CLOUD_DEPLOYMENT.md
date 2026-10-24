# Cloud deployment recommendation

For the private business-data version, prefer **AWS** if the company has no existing cloud standard. Use the company's approved region; do not infer data residency from a user's location. An Azure-first company should use its existing tenant and equivalent managed services instead.

## Recommended boundary

- CloudFront/S3 for frontend assets, or the existing web container behind an HTTPS Application Load Balancer.
- ECS/Fargate for API and separate orchestration workers, in private subnets. Apply CPU/memory/time limits, controlled outbound destinations and per-organization quotas.
- RDS PostgreSQL with encryption, TLS, private networking, automated backups and point-in-time recovery. Current JSON execution checkpoints and reviewed memory fit PostgreSQL; pgvector is a future semantic-index adapter, not the current retrieval implementation.
- S3 for private uploaded documents and immutable build artifacts, with organization-specific prefixes, IAM checks, encryption and short-lived signed downloads. Current development storage remains PostgreSQL.
- Secrets Manager/KMS for the vault master-key lifecycle and provider credential custody. The current local adapter encrypts credentials with Fernet and provisions a separate mode-0600 key through a one-shot, network-disabled initialization container. It is not an AWS KMS integration. Inject a managed key through EVOLVYN_VAULT_MASTER_KEY or a protected EVOLVYN_VAULT_KEY_FILE in production; avoid printing configuration or environment values.
- An enterprise identity provider with MFA/SSO and tested recovery. Local password accounts and project ACLs are implemented; enterprise SSO/recovery are not.
- Central logs with body/header/credential redaction, alarms, WAF limits, usage/cost accounting and incident procedures. LangGraph external tracing is explicitly disabled for private runs.

## Generated code is a separate trust domain

The current studio generates trusted React/FastAPI or React/Express starters, validates source, and offers a prototype backed by scoped Evolvyn data. It does **not** execute arbitrary model-authored code inside the API.

To offer unrestricted, Manus-style execution, add a sandbox broker using dedicated short-lived Fargate tasks, microVMs or a managed code-sandbox service. Give every build a fresh filesystem, narrowly scoped artifact credentials, explicit egress policy, no production DB/vault access, no Docker socket, and CPU/memory/process/time limits. Use distinct preview hostnames with isolated cookies. Deployment must require approval bound to the exact artifact digest, target and permission scope. Do not implement this by mounting the host Docker socket into the API.

## Launch gates still required

Independent security testing; SSO/recovery; backup and vault-key restore exercises; tenant/load/cost tests; isolated arbitrary-code execution; artifact signing/scanning; migration/versioning procedures; live authenticated CRM/social MCP integration acceptance; and business-specific product acceptance tests.

The local app, graph orchestration, credential custody and generated starters are implemented and tested. The AWS topology above is a deployment recommendation, not a claim that cloud infrastructure has been provisioned or production security certified.
