# Create and register your own MCP server

The repository includes a deployable, authenticated read-only starter at `backend/custom_mcp.py`. It reuses the existing MCP SDK and numerical evidence functions; it has no database, model key or customer-account connection.

| Tool | Inputs | Result |
| --- | --- | --- |
| `calculate_conversion` | Positive visits; paid between zero and visits | Conversion percentage from the supplied counts |
| `compare_conversion_rates` | Before/after percentages between 0 and 100 | Percentage-point change; no causal claim |

These tools perform real calculations on caller-supplied inputs. They do not claim to fetch store sales or independently monitor a business.

## 1. Deploy matching Evolvyn changes

Deploy the current API/frontend commits on Render and Vercel so the registry includes **Approve this hostname for my workspace**, and MCP tokens display a credential reference in Key vault. The separate Governance screen is not reintroduced.

## 2. Create the MCP Web Service in Render

Use **New → Web Service**, select the existing Evolvyn GitHub repository and configure:

| Setting | Value |
| --- | --- |
| Branch | `main` |
| Runtime / language | Docker |
| Root directory | Leave blank: repository root |
| Dockerfile path | `mcp-service/Dockerfile` |
| Docker build context, if requested | `.` |
| Health check path | `/health` |
| Name | Your choice, for example `evolvyn-mcp-tools` |

Choose an available plan yourself. A free service can sleep: open `/health` and wait for readiness before testing a cold endpoint. Continuous availability requires an appropriate always-on plan; no paid resource is created by this repository change.

Generate a private random token on your own computer:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

In the **new MCP Web Service** environment, set `MCP_SERVER_TOKEN` to that value. Do not put `Bearer ` before it. Keep it private; do not commit or paste it into chat. No Gemini/Groq key, vault seed or database URL is needed for this standalone server.

Render supplies `PORT` and `RENDER_EXTERNAL_HOSTNAME`; the service uses them automatically. For a custom domain or another host, set `MCP_PUBLIC_HOST` to the hostname only and configure TLS at the hosting edge. Missing/weak tokens and malformed hostname configuration stop startup.

Create/deploy the Web Service. Copy its actual Render address; the example service name is not a claim that the URL has been provisioned.

- Readiness: `https://YOUR-ACTUAL-HOST/health`
- MCP endpoint: `https://YOUR-ACTUAL-HOST/mcp`

`/health` is public readiness metadata. `/mcp` requires the exact Bearer token, supports MCP Streamable HTTP and enforces Host/Origin checks and a 64 KiB request limit. HTTPS is supplied by Render; the application listens on its assigned internal port. Access logging is disabled to avoid logging request arguments or credentials.

## 3. Store its token in Evolvyn

1. Sign in as a workspace owner/admin.
2. Open **Key vault → Connection tokens → Add connection token**.
3. Name it **My MCP server** and save the same private token used in `MCP_SERVER_TOKEN`.
4. Copy the displayed **Credential reference**. This ID references the encrypted token; it is not the token itself.

Use a separate token/deployment for each independently owned business/customer. This starter has one service token and does not implement multi-tenant account authorization or generic OAuth issuance.

## 4. Register the endpoint

In **Agent control center → MCP servers → Register a server**:

- Display name: **My business metrics**.
- Transport: **Remote HTTPS MCP**.
- HTTPS endpoint: the actual `https://YOUR-ACTUAL-HOST/mcp` URL.
- Check **Approve this hostname for my workspace**. This explicitly adds that public hostname to the current workspace's allowlist after role, external-data-policy and DNS checks. Existing policy fields are preserved.
- Vault credential ID: the credential reference from step 3.
- Credential variable reference: leave blank when using a vault credential.
- Maximum tool risk: **Read only** for this calculation server.

Click **Register connection**, then **Check health** on the saved server. Only successful MCP initialization and tool discovery produce a healthy status. Host approval by itself does not verify a server or register any tools. Public HTTPS on port 443 is required; private, loopback, link-local destinations, URL credentials, query strings and fragments remain blocked. If a hosted URL is cold, warm `/health` and retry after it becomes ready.

## 5. Register and invoke a tool

In **Tool registry**, fill the registration form:

- Name: `my_conversion`.
- Description: **Calculate conversion from supplied funnel counts**.
- Adapter: **Discovered MCP tool**.
- Healthy server: **My business metrics**.
- Remote tool: `calculate_conversion`.
- Capabilities: `analytics.conversion`.
- Entities: `funnel`.

Register it, then use **Invoke tool** with:

```json
{"visits": 200, "paid": 30}
```

Expected calculation: `conversion_percent` is `15`. This is an explicit input example, not actual customer performance. Select the registered tool through **Connections & tools** in a supported conversation/workflow. External-processing restrictions and normal registry permissions still apply.

## Development and acceptance

Run locally with the repository's existing Python environment and a private `MCP_SERVER_TOKEN`:

```bash
.venv/bin/python -m backend.custom_mcp
```

The default local port is 8071. Local HTTP is for protocol testing; Evolvyn's production remote registry intentionally does not accept localhost/private addresses.

`tests/test_custom_mcp.py` starts a real MCP HTTP process and checks Bearer rejection, Host/Origin rejection, request limits, actual protocol initialization/discovery, valid calculations and invalid counts. Separate real DB/API tests cover explicit hostname approval, policy preservation, tenant/role/data-policy checks and unsafe DNS/URL rejection. These checks do not establish a deployed public server or registration in the operator's live workspace.

The Docker image runs as a non-root user and uses a minimal hashed dependency lock derived from the existing root lock. No unrelated runtime services or credentials are copied into it. Adding a new `@server.tool()` function requires reviewing its schema, data access, resource use and real risk classification before redeploying and refreshing discovery.

Validation for this revision: 53 focused backend tests passed, including a real authenticated MCP HTTP subprocess; the browser registered a scoped server with explicit hostname approval and an encrypted credential reference using controlled public DNS (no deployed remote endpoint was claimed). TypeScript/Vite production build passed. Docker builds were attempted but could not download locked dependencies because the local build environment could not resolve the package index, including a host-network retry. The public Render image build, HTTPS protocol check and registration in the operator's live workspace remain to be completed.
