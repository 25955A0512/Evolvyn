# Enable real Google and GitHub sign-in

The platform owner registers Evolvyn once with each provider. End users then authorize their own Google/GitHub accounts directly. Provider-issued OAuth application credentials belong in the **Render API service environment**, not Vercel's browser variables, the business-agent key vault, chat, or source control. A model API key or randomly generated vault/access token cannot substitute for these registrations.

Current frontend: `https://evolvyn.vercel.app`.

## Google

1. Open https://console.cloud.google.com/ and select/create a project for Evolvyn.
2. Open **Google Auth Platform**. Complete **Branding**: application name Evolvyn, user-support email and developer-contact email.
3. Configure **Audience** for the intended users. Choose External when users are outside a single managed Google Workspace organization. While the app is in Testing, add the evaluating team's Google email addresses as test users.
4. Use the basic `openid`, `email`, `profile` scopes requested by the application. Additional Drive/advertising scopes are not required for sign-in.
5. Open **Clients → Create client → Web application**.
6. Set the authorized JavaScript origin to:

```
https://evolvyn.vercel.app
```

7. Set this exact authorized redirect URI:

```
https://evolvyn.vercel.app/api/auth/oauth/google/callback
```

8. Create the client and privately retain the provider-issued client ID and client secret. Complete any required Google consent/publishing/domain verification before opening the app to a wider audience; team testing is not proof of production verification.

## GitHub

1. Open https://github.com/settings/developers.
2. Select **OAuth Apps → New OAuth App**.
3. Application name: Evolvyn.
4. Homepage URL:

```
https://evolvyn.vercel.app
```

5. Authorization callback URL:

```
https://evolvyn.vercel.app/api/auth/oauth/github/callback
```

6. Register the application. Copy its client ID and use **Generate a new client secret**. Keep the secret private. This is an OAuth App registration; connecting GitHub to Render/Vercel authorizes deployments and does not register Evolvyn as an identity application.

## Apply privately on Render

Open Render → your **evolvyn API Web Service** → **Environment**. Add the values issued by the providers:

| Variable | Provider-issued value |
| --- | --- |
| `OAUTH_GOOGLE_CLIENT_ID` | Google Web application's client ID |
| `OAUTH_GOOGLE_CLIENT_SECRET` | Google Web application's client secret |
| `OAUTH_GITHUB_CLIENT_ID` | GitHub OAuth application's client ID |
| `OAUTH_GITHUB_CLIENT_SECRET` | GitHub OAuth application's client secret |

Retain `PUBLIC_ORIGIN=https://evolvyn.vercel.app` and `COOKIE_SECURE=1`. Keep the existing vault seed/master key unchanged. Save the new environment settings and redeploy the API. GitHub/Vercel deployment connections and Gemini keys remain separate.

The site is already proxied to the operator-provided Render API via `frontend/vercel.json`; no provider secret is needed in the frontend. Refresh the login page after Render finishes. Configured provider buttons are ordinary links to the server's authorization-code/PKCE start endpoints and immediately redirect to the provider. The public page shows a compact unavailable state for unconfigured providers and never asks end users to configure the deployment. Owner/admin account settings retain setup diagnostics.

## Verify

- Open `https://evolvyn.vercel.app/api/auth/providers`. `enabled:true` confirms configuration is present and origin/cookie checks pass; it does not prove credentials are valid or authorization succeeded. No secret values are returned.
- In a private browser window, click Google, choose a permitted test user and complete consent. Confirm return to Evolvyn with the correct account/workspace, then test logout and sign-in again.
- Test GitHub separately. Existing email accounts are never silently merged: sign in with the original method and explicitly link the provider from account settings when needed.
- Cancel a provider authorization and check that no new session is created. Confirm Secure/HttpOnly cookie metadata without copying cookie values.
- A redirect mismatch means the provider console URI differs from the exact URL above. An invalid-client error means the backend client ID/secret or client type needs correction. A Google access block while Testing requires the intended account to be added as a test user. Do not fix these by relaxing TLS, cookie or origin checks.

Local checks include actual backend redirects/state/PKCE with controlled provider application settings and intercepted provider pages. They are not live Google/GitHub acceptance. Real credentials must be registered and tested on the deployed site by its owner.
