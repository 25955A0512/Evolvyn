# Evolvyn

An AI workspace for business analysis, research and product development, built with React, TypeScript, FastAPI, PostgreSQL and LangGraph.

## Core modules

- **Growth insights:** analyze uploaded business evidence and authorized social data, review recommendations, schedule analysis and compare outcomes.
- **Build a product:** refine requirements in chat, review specialist designs and approve file-by-file source generation.
- **Discussion room:** collaborate with business, marketing and product agents using shared evidence.
- **Integrations:** connect supported accounts through OAuth or register your own MCP server and tools.

## Quick start

Install Git, Python 3 and Docker Desktop with Docker Compose. Start Docker, then run:

```bash
git clone https://github.com/25955A0512/Evolvyn.git
cd Evolvyn
python scripts/prepare_deployment.py
docker compose --env-file .local/deploy.env up --build -d --wait
```

Use `python3` on systems where `python` is unavailable. Open **http://localhost:3000** and create an account.

1. Open **Key vault → Add key** and save a Gemini or Groq API key. A successful model check makes it the shared default for all agents.
2. Open **Growth insights** and upload your business data, or try the synthetic files in [sample-data](sample-data/).
3. Configure account connections in **Integrations**, or custom servers and tools in **Agent control center**.

Stop the stack without deleting database volumes:

```bash
docker compose --env-file .local/deploy.env down
```

## Configuration and limits

- Gemini and Groq are the current user-facing AI providers; availability and quota depend on your provider account.
- OAuth requires administrator client credentials. Users authorize their own accounts; sign-in does not grant access to other services.
- Keep secrets out of source control and chat. Preserve the generated `.local/deploy.env` and back up `.local/vault.key` securely, separately from database backups.
- Generated source requires review and approval. Frontend compilation and the data prototype do not establish that a generated backend runs correctly or is deployed.
- Social metrics require authorized API access. Recommendations and forecasts are proposals, not guaranteed business outcomes.

## Deployment and guides

- [Vercel + Render deployment](docs/VERCEL_RENDER_DEPLOYMENT.md) — includes configuration for deploying your own copy; update the frontend API rewrite to your Render URL.
- [Gemini and Groq setup](docs/CLOUD_MODEL_DEFAULTS.md)
- [Google and GitHub sign-in](docs/PUBLIC_OAUTH_SETUP.md)
- [GitHub, Google Drive, Slack and Shopify connections](docs/ACCOUNT_CONNECTOR_OAUTH.md)
- [Create and register a custom MCP server](docs/CUSTOM_MCP_SERVER.md)
- [Social analytics](docs/SOCIAL_GROWTH.md)
- [Implementation progress and limitations](docs/PROGRESS.md)

## Development checks

With development dependencies and PostgreSQL configured:

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend run build
```

Provider-mocked tests do not prove live OAuth or model connectivity. Validate your deployment with your own authorized accounts.
