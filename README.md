# Evolvyn — Continuous Business Evolution Platform

A conversational workspace that connects business evidence, research, recommendations, human approval, internal execution, and outcome measurement. Built with React/TypeScript, FastAPI, PostgreSQL and a real local MCP strategy tool.

**No OpenAI key is required.** Local AI uses Qwen 2.5 1.5B through a checksum-verified llama.cpp runtime. If the local model is unavailable, the application clearly labels its deterministic evidence analysis and heuristic recommendations. It never presents that fallback as an LLM response.

## Run on your computer with Docker

Install Git, Python 3 and Docker Desktop (including Docker Compose). Start Docker Desktop, then run:

```bash
git clone https://github.com/25955A0512/Evolvyn.git
cd Evolvyn
python scripts/prepare_deployment.py
docker compose --env-file .local/deploy.env up --build -d --wait
```

On macOS/Linux, use `python3` if `python` is unavailable. Open **http://localhost:3000** on that same computer, create an account or select **Try a sample business**, and open **Agent control center** for the registries, execution graphs and governance. To stop the app, run `docker compose --env-file .local/deploy.env down`; the database volume is retained.

This source checkout excludes private data, credentials, model weights and compiled runtime binaries. A fresh Docker start uses the explicitly labeled deterministic evidence mode until the optional local model is installed. The Linux x86-64 setup below installs that model; no OpenAI key is required. Docker builds download their locked dependencies, so Internet access is required for the initial build.

## Development setup on Linux
Requires Python 3.12, uv, Node 24/npm, Docker and Docker Compose on Linux x86-64.

```bash
bash scripts/install.sh
bash scripts/start.sh
```

Create an account, or select **Try a sample business** for an isolated synthetic workspace. Private development-token access is retained as an optional advanced path; its generated token is in ignored, mode-0600 `.local/runtime.env`. Never paste it in chat or commit it.

Installation prepares verified dependencies and downloads the local model when it is not already installed. Model catalogue and binary-CDN access are now working. The pinned model is installed and actual local inference has been verified. To refresh or start the model separately:

```bash
.venv/bin/python scripts/install_local_model.py
bash scripts/start_local_model.sh
```

The model is pinned to an official immutable repository revision and LFS SHA-256 in `config/local-model.json`. Installation and startup reject a modified model. A 1.1 GB download and approximately 2–4 GB inference memory are needed. The runtime itself is installed, checksum-verified, and executable both on the host and in the application container. **Verified:** actual local completion, model-generated schema-validated recommendations, streamed interpretation, approval and internal task creation, with no external API key. A representative full run took about 50 seconds on four CPU cores.

## Container stack

```bash
bash scripts/deploy_local.sh
```

This builds static frontend assets and a non-root API image, starts Nginx and an authenticated PostgreSQL database, and checks readiness. The web port is 3000, bound only to loopback. The API and database are not published. Private deployment secrets are generated in ignored `.local/deploy.env` without displaying them. The offline image build uses hash-verified wheels and the environment's existing public trust bundle; TLS checks remain enabled. Existing proxy configuration is passed at runtime with internal services excluded.

Public Internet hosting has not been performed. To expose a deployment, provide a real TLS reverse proxy and hostname, set PUBLIC_ORIGIN, ALLOWED_HOSTS and COOKIE_SECURE=1, and review operational security. The development trust-auth database is separate from the authenticated Compose database.

## Working features

- Email/password accounts with scrypt hashes, HttpOnly sessions, organization isolation and owner/admin/editor/viewer roles.
- Business profiles, goals and projects. Local-only project policies prevent remote model requests.
- Persistent, searchable conversations with grouped history, Markdown, streamed execution updates and cancellation.
- Validated TXT/CSV/PDF/DOCX ingestion. Binary documents are parsed in a bounded child process.
- Numerical funnel calculations, keyword signals, lexical passage retrieval and source citations. Related conversations can reuse evidence only within the same business/project scope.
- Structured recommendations with evidence, assumptions, risks, effort, measurement plans and rollback guidance. Model proposals are schema-checked and unsupported citations are rejected; the fallback is labeled.
- Persistent MCP server registry with two bundled stdio profiles, HTTPS transport, organization-scoped credential references, health checks and schema discovery.
- Persistent built-in/MCP tool adapters, capability and business-entity discovery, schema validation and single-use approvals bound to exact arguments and configuration.
- Declarative agent graphs with conditional branches, joins, bounded loops, durable checkpoints, transient retries and call/time/output-token budgets.
- Central organization policy for tool access, risk and external processing, plus restricted project membership enforced on linked resources.
- An Agent control center for MCP connections, tool registration/invocation, graph planning/execution and governance.
- Editable approval creating a real internal brief and tasks atomically, with replay prevention.
- Task status/notes and follow-up CSV comparisons against the stored baseline. Comparisons do not claim causality or invented business improvements.
- Persisted recurring analysis, manually triggered runs, bounded PostgreSQL worker leases, and recovery from completed evidence/strategy checkpoints.
- A draggable workflow canvas and saved templates whose research, provider, source and recommendation settings affect actual execution. Approval cannot be disabled.
- Five uploaded-log agent interfaces: alert triage, log analysis, change analysis, runbook retrieval and verification prerequisites. This is not a connected production monitor.
- Public discussion research with URLs and retrieval/publication timestamps; these are discovery leads rather than verified market claims.
- Local/OpenAI/Groq/Gemini provider adapters, bounded context, provider-reported usage when returned, and payload-free audit records. Remote providers are optional and require their own credentials/network access.

## Demonstrate

1. Create an account and business, or open the synthetic sample.
2. Upload `sample-data/funnel.csv` and `sample-data/customer-feedback.txt`.
3. Choose Local AI (the default) and ask what to investigate. Evidence only is available for a fast deterministic comparison.
4. Inspect calculated conversion (8% then 5%), cited text and recommendation cards.
5. Select a recommendation, edit the plan, approve, and inspect the created tasks.
6. Upload `sample-data/followup.csv`; compare observations in Reports & outcomes. The synthetic follow-up is 6%, a one-percentage-point pre/post difference, not proof of improvement caused by an action.
7. Open workflow tools, drag/save a layout, change the recommendation limit, and run the saved workflow.
8. Refresh and reopen history; use Account & team to inspect membership and audits.
9. Open Agent control center to register/check MCP servers, bind a discovered tool, generate/save/run an execution graph, and approve its exact write arguments. Governance controls organization policy and project membership.
10. Optionally upload `sample-data/service-logs.txt` and select Uploaded logs to run the operational checks.

## Verify and preserve

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend run build
EVOLVYN_TEST_URL=http://localhost:3000 python3 tests/e2e_account.py
python3 tests/e2e_control_center.py
bash scripts/backup.sh
```

65 automated tests pass against an isolated temporary PostgreSQL schema. Chromium validated account creation, private uploads, analysis/approval, refresh persistence, team access, canvas editing and a saved workflow running with its configured recommendation count. Docker images build and all three services pass readiness. Public research also succeeds through the container's configured proxy. Actual local inference and model-generated recommendations passed earlier acceptance runs. The most recent strict local-AI acceptance run rejected structured proposals and used the labeled heuristic fallback; that strict check failed. A subsequent deterministic upload/analysis/approval/task run passed. Public Internet hosting has not been performed.

Backups keep the development database and Compose data separately in ignored mode-0600 files. An empty Compose database is restored by the deploy script; existing records are not overwritten. Protect backups as business data. Cloud publication and restoration in a new task remain separate, unverified platform steps.

Known remaining work: embedding-based semantic retrieval, identity recovery/email verification, additional business service connectors, production incident actions, robust model evaluation and public deployment. See `docs/PROGRESS.md` for current scope.

Remote MCP credentials are optional. Add the hostname in Governance, register its HTTPS endpoint, and use the organization-specific environment-variable prefix displayed in the form. Supply the actual value through private runtime configuration; Compose optionally reads ignored `.local/mcp-secrets.env`. Redeploy after changing credentials. Never paste a key into tool arguments or an endpoint URL. Bundled stdio profiles need no credentials. Remote transport and policy boundaries have automated coverage; no third-party authenticated MCP deployment was available for live acceptance.
