# GitHub, Google Drive, Slack and Shopify connections

The platform owner registers each provider app **once** and saves its client ID/secret in the Render API Web Service. Users then click Connect and authorize their own accounts; they do not generate or paste access tokens.

OAuth grants are separate from signing in to Evolvyn. All tools in this release are read-only. Account identity is checked before the grant is saved, MCP tools are discovered in the existing registry, and credentials are encrypted by the existing vault. Only owners/admins can connect or disconnect organization accounts. This release supports one active account/workspace/store per provider per Evolvyn organization; reconnect replaces that provider's grant.

## Render and Vercel

Keep these existing Render settings:

```text
PUBLIC_ORIGIN=https://evolvyn.vercel.app
COOKIE_SECURE=1
```

Keep the existing vault seed unchanged. In **Render → Evolvyn API Web Service → Environment**, add each provider's client ID/secret under the exact names below. Save and redeploy the API. Deploy the matching frontend commit to Vercel. Keep all secrets out of Vercel frontend variables, source control, screenshots and chat.

The Vercel `/api` proxy must continue forwarding to `https://evolvyn.onrender.com/api`. Register the **Vercel** callback addresses below, because authorization begins in the Vercel browser session.

## GitHub

Existing GitHub OAuth and the public-repository MCP profile are retained.

1. Open <https://github.com/settings/developers> → OAuth Apps → your Evolvyn app.
2. Homepage: `https://evolvyn.vercel.app`.
3. Authorization callback URL: `https://evolvyn.vercel.app/api/auth/oauth/github/callback`.
4. In Render, set `OAUTH_GITHUB_CLIENT_ID` and `OAUTH_GITHUB_CLIENT_SECRET` (already used for GitHub sign-in).
5. In Evolvyn → Integrations → Account connections, click **Connect GitHub**. Use **Test connection** afterward.

Tools: `github_repositories`, `github_repository`, `github_issues`. Public repositories only; no private-repository or write grants are requested.

## Google Drive

1. Open <https://console.cloud.google.com/> and select your Google project.
2. Enable **Google Drive API** in APIs & Services → Library.
3. In Google Auth Platform, configure Branding, Audience and Data Access. Add `https://www.googleapis.com/auth/drive.readonly`. Add your team under Test users while the app is in testing.
4. Create a **Web application** OAuth client. Authorized JavaScript origin, if requested: `https://evolvyn.vercel.app`.
5. Authorized redirect URI: `https://evolvyn.vercel.app/api/integrations/google_drive/callback`.
6. In Render, add `OAUTH_GOOGLE_DRIVE_CLIENT_ID` and `OAUTH_GOOGLE_DRIVE_CLIENT_SECRET`. A dedicated client is recommended; Google sign-in alone does not grant Drive access.
7. Redeploy, then click **Connect Google Drive** in Evolvyn and approve the read-only access.

Tools: `drive_files` lists up to 20 file metadata records; `drive_text` reads Google Docs/plain text/CSV up to 24 KB. Other formats and binary downloads are rejected. Refresh tokens are encrypted and renewed through Google's fixed endpoint when needed. Testing-mode refresh grants can expire after seven days. Drive read-only is a restricted scope; public use may require Google's verification and applicable security assessment. Test with your own team's accounts first.

## Slack

1. Open <https://api.slack.com/apps> → Create New App → From scratch. Name it Evolvyn and choose your test workspace.
2. Open OAuth & Permissions → Redirect URLs. Add `https://evolvyn.vercel.app/api/integrations/slack/callback` and save.
3. Under **Bot Token Scopes**, add `channels:read` and `channels:history`. Do not add DM/private-channel/write scopes for this release.
4. Keep token rotation **off** for this connector version. Expiring Slack grants require reconnecting; Slack refresh-token rotation is not implemented.
5. Open Basic Information → App Credentials. Add `OAUTH_SLACK_CLIENT_ID` and `OAUTH_SLACK_CLIENT_SECRET` in Render.
6. Redeploy and click **Connect Slack** in Evolvyn. Approve the workspace installation. A workspace admin may need to approve the app.
7. Invite the app/bot to each public channel you want to analyze using Slack's channel integration controls or `/invite @Evolvyn`.

Tools: `slack_channels`, `slack_history`. History requires channel membership and is a bounded recent sample. Slack's rate limits and app-distribution restrictions apply; this is not a full workspace archive or an automatic monitoring schedule.

## Shopify

1. Open <https://dev.shopify.com/dashboard>, create an app and choose the appropriate development-store/distribution setup.
2. Configure the app URL as `https://evolvyn.vercel.app`.
3. Enable **legacy authorization-code installation** for this flow (in Shopify app configuration this is `use_legacy_install_flow = true`; use Shopify CLI configuration if the dashboard does not expose it).
4. Configure the allowed redirect URL: `https://evolvyn.vercel.app/api/integrations/shopify/callback`.
5. Configure scopes `read_products,read_orders`, then release the app configuration. The app is an external, non-embedded OAuth connection; it does not implement Shopify embedded session-token exchange.
6. From the app's credentials/settings, add `OAUTH_SHOPIFY_CLIENT_ID` and `OAUTH_SHOPIFY_CLIENT_SECRET` to Render.
7. Redeploy, click **Connect Shopify**, enter the permanent store hostname such as `yourstore.myshopify.com`, and approve installation as an authorized merchant.

Tools: `shopify_products`, `shopify_orders`. Shopify callback HMAC, timestamp and the initiating shop hostname are verified. Queries use a pinned Admin GraphQL version (`2026-07`; override with a valid `EVOLVYN_SHOPIFY_API_VERSION` only after testing). The orders tool returns a bounded sample of recent order totals with currencies, without customer identities. It is **not** full-store revenue, a normalized sales import, or a forecast. Standard order access is limited by Shopify's permitted order window; no `read_all_orders` permission is requested. App distribution, merchant installation eligibility, scope review and applicable protected customer data requirements remain provider-controlled. Test on an authorized development store first. Expired/revoked Shopify grants require reconnecting in this release.

## Registry and use

Healthy enabled MCP servers appear first in Integrations and the control-center registry. Servers needing setup/attention are collapsed below account connections. The discover catalog keeps the two working local MCP profiles and Custom MCP; duplicate third-party endpoint recipes have been removed in favor of direct OAuth cards.

After connecting, use **Test connection** and inspect the actual registered tools under **Tools**. Select the required tool explicitly in the business/research/discussion context picker. Scheduling and growth analysis still use the existing evidence and approval boundaries. Connecting an account alone does not import an entire workspace/store, create a growth dashboard snapshot, start continuous monitoring, or authorize publishing.

**Disconnect** erases the local encrypted grant and disables its tools. It does not revoke the provider-side app installation; uninstall/revoke there if needed. The provider-specific setup dialog repeats the exact URLs, variables and scopes. Failed callbacks never mark an account connected; return to Integrations and start a fresh authorization instead of reloading a one-time callback URL.

## Acceptance scope

Focused backend tests use controlled provider HTTP, real PostgreSQL and actual MCP stdio discovery. Browser tests follow the actual redirects/callbacks with synthetic consent responses. They cover replay/browser/config/session checks, scope and identity failure, encrypted storage, Drive renewal, tool schemas, disconnect, registry policy and mobile navigation. Real Google/Slack/Shopify consent and authorized data reads must still be tested after the owner configures provider apps in Render. Passing synthetic tests does not establish provider approval or public production acceptance.

Checks run for this change:

```bash
npm --prefix frontend run build
.venv/bin/python -m pytest -q tests/test_business_connectors.py
.venv/bin/python -m pytest -q tests/test_business_connectors.py tests/test_connected_identity.py tests/test_instagram_oauth.py tests/test_social_growth.py tests/test_visual_assets.py
python tests/e2e_connector_oauth.py
python tests/e2e_dashboard_refresh.py
```

Results: production build passed; the regression suite passed 95 tests; the final focused connector suite passed 17 tests after adding grant-renewal role coverage. Both browser journeys passed. Provider HTTP/consent responses were controlled; MCP discovery and DB/vault operations were real. The existing Vite chunk-size and Starlette deprecation notices remain nonblocking.
