# Instagram account authorization

Users can now click **Growth Insights → Social intelligence → Connect with Instagram**. They authorize their own professional account in Instagram; Evolvyn verifies its ID, exchanges the short-lived token for a long-lived token, encrypts it in the existing vault and registers a scoped social MCP source. They do not create a Meta developer application or copy tokens. This is a connector grant, not a new Evolvyn sign-in method.

## One-time platform-owner configuration

1. In https://developers.facebook.com/apps/ configure **Instagram API with Instagram Login** for the Evolvyn Meta app. Use the **Instagram App ID and Instagram App Secret** shown in that product's settings, not Google/GitHub credentials or an AI key.
2. Register this exact valid OAuth redirect URI for the current deployment:

   `https://evolvyn.vercel.app/api/integrations/instagram/callback`

3. In **Render → Evolvyn API Web Service → Environment**, privately add:

   | Variable | Value |
   | --- | --- |
   | `OAUTH_INSTAGRAM_CLIENT_ID` | Instagram App ID |
   | `OAUTH_INSTAGRAM_CLIENT_SECRET` | Instagram App Secret |
   | `PUBLIC_ORIGIN` | `https://evolvyn.vercel.app` |
   | `COOKIE_SECURE` | `1` |

   Keep the existing persistent vault seed/master key. Do not put any app secret in Vercel frontend variables, source control or chat. Redeploy the API after saving configuration. Deploy the matching frontend revision too.
4. Configure eligible professional test accounts/app roles in Meta and accept any required invitation. Complete Meta's applicable verification, App Review and Advanced Access requirements before onboarding businesses outside those app roles. Configuration and a successful test-account grant do not prove general public access approval.
5. Open Growth Insights, select the evidence workspace and click **Connect with Instagram**. The returned account is automatically selected by the provider grant; no arbitrary user-supplied account ID is trusted. Click **Sync account** to verify actual account/media access and save the first dashboard observation. OAuth/discovery alone does not mark engagement metrics verified.

Basic access requests `instagram_business_basic`. Comment text is optional and additionally requests `instagram_business_manage_comments`. Meta names this a management permission; Evolvyn exposes only bounded read tools and no comment publication/deletion, messages, ads or spend. Permission scopes requested are recorded separately from successful data access; the app does not infer that every requested permission was granted.

An administrator must connect shared business accounts under the existing tenant model. Viewer/editor roles do not gain vault/registry administration through OAuth. Supporting per-member private connector custody would require a separate permission model.

## Lifecycle

The documented endpoints are fixed: Instagram's authorization endpoint, `api.instagram.com/oauth/access_token`, and `graph.instagram.com/access_token`, `/refresh_access_token`, and versioned `/me`. Token exchange/profile payloads are bounded; redirects are disabled. The long-lived exchange must succeed; no one-hour fallback is silently saved.

The provider-reported expiration is stored. The existing running scheduler claims at most one due grant per tick and attempts renewal within seven days of expiration, after the grant is at least 24 hours old. It verifies the refreshed account identity, uses version-checked encrypted credential rotation, updates source binding/expiry and records a cooldown/error. Failures retry after a six-hour cooldown, not a tight loop. Expired, revoked, policy-blocked or changed grants require reconnecting. A sleeping/offline Render service cannot guarantee timely renewal. No external account is claimed connected until a successful provider check, and no metrics appear without a separate successful observation.

Reauthorizing the same OAuth account in the same evidence conversation updates its existing source and credential, preserving saved history and paused monitors. Connecting another account creates a separate source. Disconnect stops monitoring/tools and erases that OAuth credential locally; the provider app grant must be revoked in Instagram settings when required. Manual-token sources preserve the existing explicit vault-revocation behavior.

Authorization uses a single-use hashed state, expiring HttpOnly/SameSite=Lax browser cookie, initiating session/membership binding, exact configured redirect and configuration fingerprint. Session, project and external-data permissions are rechecked around provider calls. Codes/tokens are not stored in tool arguments, graph state, API responses or frontend storage. This confidential-client Instagram flow does not claim PKCE support; existing Google/GitHub PKCE flows remain unchanged. Meta's documented long-lived exchange/refresh endpoints require token parameters in outbound HTTPS GET requests; their query strings are stripped from HTTPX request logs, and upstream errors are replaced with static messages. Do not enable unredacted HTTP transport/body tracing in production.

## Verification boundaries

`tests/test_instagram_oauth.py` checks actual auth/DB/vault/stdio discovery against a controlled Meta HTTP transport: single-use state, browser/session/membership/policy/config changes, denial, account mismatch, token exchange, encrypted storage, reconnect, expiry, renewal, cooldown, local credential erasure and query-log redaction. `tests/e2e_instagram_oauth.py` checks browser authorize/callback/return, native source creation, social sync, review, JSON export, monitor/pause, persistence, mobile and disconnect with explicitly synthetic provider/MCP boundaries.

Live acceptance still requires the operator's Meta application configuration, provider approval and a real authorized professional account. These controlled tests do not prove Meta has approved the app or that public Vercel/Render deployments are healthy. Follow current Meta documentation at https://developers.facebook.com/docs/instagram-platform/ .

Validated locally: full regression run **305 passed**; final focused OAuth/social run **43 passed** (includes the additional renewal/revocation cases and actual asynchronous cancellation); production TypeScript/Vite build and desktop/mobile OAuth browser journey passed. Provider/model responses were controlled test boundaries; no live Meta or public deployment acceptance is claimed.

## Callback diagnostics

The initial code exchange accepts both a flat token object and a single-account `data` array envelope. Ambiguous multi-account or conflicting envelopes are rejected; no account is guessed. Callback failures identify the initial exchange, long-lived exchange, or profile verification stage and may include only allowlisted numeric HTTP/Meta error codes. Provider error messages, trace IDs, URLs, codes and tokens are not reflected. Render receives a matching payload-free diagnostic and request ID. Always retry through Connect with Instagram; OAuth codes/state are single-use. A screenshot of a generic old failure cannot establish which provider request failed.

Callback-format patch verification: **67 focused OAuth/identity tests passed**, plus the desktop/mobile OAuth browser journey using a single-account `data` token envelope and explicitly controlled provider responses. Live callback failure diagnosis still requires a new operator-authorized attempt after deployment.
