# Vercel + Render deployment

Current operator-provided origins are **https://evolvyn.vercel.app** (frontend) and **https://evolvyn.onrender.com** (API). The checked-in API rewrite targets that Render origin. Public health, cookies and OAuth must still be verified through the actual deployments; workspace outbound connectivity could not reach either site. Reconfigure the rewrite before deploying a separate copy.

The repository includes a Vercel SPA configuration and `render.yaml` Blueprint for an always-on API, managed PostgreSQL and a private source compiler. These are deployment inputs, not proof that cloud resources exist. This session has no Vercel/Render deployment tokens. The operator must import the repository through the already connected dashboards and supply the public service URLs.

## Actual layout and limits

| Component | Destination |
| --- | --- |
| Existing React/Vite app | Vercel, project Root Directory `frontend` |
| Existing FastAPI, durable queue and scheduler | One paid always-on Render Docker web service |
| Existing data | Render managed PostgreSQL; external access disabled in Blueprint |
| Existing isolated source compiler | Render private Docker service, shared authentication token |
| Browser API requests | Vercel `/api/*` rewrite to the fixed public Render API origin |

No new agent engine, scheduler, CORS wildcard, public compiler port or browser API key is introduced. The compiler parses/bundles source; it does not execute generated apps. The API's existing background worker/scheduler remains in the one API process; do not independently scale replicas until capacity/fairness/deployment tests are complete.

Review current Render plans/prices and the selected region before clicking Create/Deploy. The Blueprint declares paid services because sleeping/free services do not provide reliable scheduled execution, and the compiler requires private-service hosting. Keep API, compiler and database in the same company-approved region. The checked-in plan names may need adjustment if the provider changes its catalog; Render must validate the Blueprint in the dashboard. No provider plan availability or public deployment is claimed by local tests.

## 1. Create the Vercel project first

1. Open https://vercel.com/new and import `25955A0512/Evolvyn`, branch `main`.
2. Set **Root Directory: `frontend`** and framework **Vite**. `frontend/vercel.json` sets the locked install command, build command and `dist` output.
3. Deploy and copy the stable **production project URL**, e.g. `https://your-project.vercel.app`.

For a separate deployment, connect the frontend to your own Render API using step 3 before entering credentials or sharing it as a working platform. `/api/*` is excluded from the SPA fallback; when no proxy rule is configured it fails rather than returning the SPA as an API result. Do not add AI/OAuth/database/vault credentials to Vercel frontend environment variables. No frontend environment variables are needed for API routing.

## 2. Deploy the Render Blueprint

1. Open https://dashboard.render.com → **New → Blueprint**.
2. Select `25955A0512/Evolvyn`, branch `main`, with Blueprint path `render.yaml`.
3. Review the region, paid plans and resources before creating them.
4. Set the requested **`PUBLIC_ORIGIN`** to the exact Vercel production origin from step 1: HTTPS, no path/query or trailing slash. Do not use the Render API origin here.
5. Deploy. Wait for `evolvyn-db`, `evolvyn-compiler` and `evolvyn-api` to be ready.
6. Copy the API's public `https://…onrender.com` URL. Check `/api/health` returns `{"status":"ok"}`.

The Blueprint links DATABASE_URL to managed Postgres, requires TLS via PGSSLMODE, shares the generated compiler token with the API and passes the compiler's private `hostport`. The API bootstrap honors Render's PORT, adds only its exact Render hostname and configured frontend hostname to the allowed hosts, and rejects insecure public-origin settings. No browser CORS exception is needed.

### Persistent vault encryption

`EVOLVYN_VAULT_SEED` is generated as a private Render environment secret and deterministically derives a Fernet master key. The same seed is required across restarts and redeployments. **Never regenerate/delete/change the seed after saving credentials without a deliberate re-encryption/migration.** A database backup alone cannot decrypt saved credentials. Securely back up this seed separately with limited operator access; it is not an AWS KMS integration.

For an existing database migrated from local Docker, set `EVOLVYN_VAULT_MASTER_KEY` to the **original** vault key using Render's private environment settings before serving that data. An explicit master key takes precedence over a seed. Never paste either into chat or GitHub. A fresh cloud installation has no local users, uploads or Gemini credentials; create a cloud account and enter its key through the cloud vault.

## 3. Connect Vercel to the real Render API

Use the exact public API URL assigned in step 2. The script rejects non-HTTPS URLs, credentials/query/path components, non-Render destinations and unexpected ports. It writes only a public routing URL—no tokens or secret values:

```cmd
git pull origin main
python scripts/configure_vercel.py --api-origin https://YOUR-ACTUAL-API.onrender.com
python scripts/configure_vercel.py --check
git add frontend/vercel.json
git commit -m "Connect Vercel frontend to Render API"
git push origin main
```

If an assistant has repository write access, share **only the two public URLs** so the routing change can be committed for you. Neither URL is an API key. Wait for Vercel's production redeployment. Its API rule must precede the SPA fallback. Response security headers are retained; API responses are marked private/no-store.

Host-only Secure/HttpOnly cookies are issued through the Vercel origin. OAuth redirects return through that origin. Do not change cookie Domain, set SameSite=None or enable wildcard CORS to work around an incorrect proxy. Changing either public URL requires an explicit configuration update; use stable production aliases rather than per-commit preview URLs.

## 4. Configure real OAuth and models

In Render **evolvyn-api → Environment**, privately add:

```
OAUTH_GOOGLE_CLIENT_ID
OAUTH_GOOGLE_CLIENT_SECRET
OAUTH_GITHUB_CLIENT_ID
OAUTH_GITHUB_CLIENT_SECRET
```

Register provider callbacks on the **Vercel frontend origin**:

```
https://YOUR-VERCEL-PRODUCTION-ORIGIN/api/auth/oauth/google/callback
https://YOUR-VERCEL-PRODUCTION-ORIGIN/api/auth/oauth/github/callback
```

Use Google Web application credentials; configure the consent screen/test users or complete Google's publishing requirements. GitHub OAuth application's homepage is the Vercel origin. The same GitHub callback supports separately initiated read-only connector authorization. A signup does not automatically connect repository tools.

Redeploy the API after changing environment variables. Complete real sign-in/sign-out/linking tests; configured credential metadata is not proof of successful provider authorization. The local `configure_oauth.py` helper writes local Compose settings and **does not configure Render's environment**.

Save the Gemini credential in the new cloud workspace's Key vault and run a small actual model test. Keep all AI/support keys on Render or in the encrypted cloud vault; never expose them in `VITE_*` or Vercel browser configuration.

## 5. Public acceptance before sharing

1. Open the Vercel production URL in a private browser. Verify `/api/health` through Vercel, not only on Render.
2. Register a synthetic evaluation account, refresh a deep route such as `/growth`, log out/in, and confirm persisted workspace identity. Check cookie metadata: Secure, HttpOnly, host-only and root path for the `__Host-` session cookie.
3. Test Google/GitHub sign-in, provider cancellation and explicit linking once real credentials are registered. Confirm callbacks use the Vercel origin.
4. Upload the synthetic sales CSV, verify SQL metrics, approve an internal brief and inspect its actual tasks/receipt. Navigate away/back during a run and check it restores. Verify an actual authenticated compiler receipt, not an empty green status.
5. Create a recurring review and confirm the worker runs it while your laptop is offline. Check its actual state; scheduled does not mean provider data has synced.
6. Confirm accounts in different organizations cannot access each other's data. Confirm private compiler and database have no public access. Keep synthetic evaluation data until security/recovery requirements are met.

Vercel/Render proxy timeouts may interrupt streams; the existing UI reconnects to persisted execution state. Verify reconnects on the chosen plans. Public OAuth/token exchange, provider plan limits, database TLS, DNS, headers/cookies through the actual edge and independent security/load/recovery reviews remain **live acceptance**, not results established by local tests. Enable appropriate database backups, service alerts and billing limits before customer use.

## Local verification available

- `tests/test_managed_hosting.py`: restart-stable vault custody, explicit migration key, port/origin/host checks, Blueprint boundaries, frontend proxy destinations/order and private compiler receipts.
- `.venv/bin/python tests/live_managed_hosting.py`: starts actual API and compiler processes with managed-hosting-style variables; verifies SQL health, assigned ports, exact hosts, HTTPS callback metadata, encrypted vault custody through an actual API restart, compiler authentication/compilation, clean shutdown and nonzero invalid-configuration exit. Does not deploy to Render/Vercel.
- `npm --prefix frontend run build`: current frontend type/production build.
- Existing identity, OAuth, tenant, approval and execution suites remain required.

## Instagram business connector OAuth

Configure the Instagram App ID/secret once on the Render API; end users authorize their own professional accounts using Connect with Instagram. The exact deployed redirect is `https://evolvyn.vercel.app/api/integrations/instagram/callback`. See [Instagram OAuth setup](INSTAGRAM_OAUTH.md) for environment names, Meta access/review requirements, long-lived renewal, credential custody and live acceptance boundaries.
