# Agent visibility and automation update

The main chat keeps a compact composer below a persistent execution status bar. View results and Review action scroll to the actual saved run. Interrupted streams reconnect and fetch persisted state; Refresh status is available if the connection remains unavailable. Discussion room uses one conversational thread with settings collapsed by default. Connector cards are setup recipes, not claims of native integrations. Icons are original vector illustrations and work without external image requests.

Actual browser screenshots: [visible results](screenshots/visible-agent-results.png), [discussion room](screenshots/discussion-room-preview.png), [connector catalog](screenshots/connector-marketplace.png), [Canvas automations](screenshots/canvas-automations.png). These use synthetic acceptance data and explicit evidence mode.

## Configure platform help privately

Add these values to the ignored `.local/deploy.env` on the deployment machine:

```dotenv
EVOLVYN_HELP_GEMINI_KEY=
EVOLVYN_HELP_GEMINI_MODEL=
EVOLVYN_HELP_GROQ_KEY=
EVOLVYN_HELP_GROQ_MODEL=
```

Use model IDs available to your provider accounts. Both key and model are required for a route. Restart with `docker compose --env-file .local/deploy.env up --build -d --wait`. Do not put keys in chat, screenshots or committed files. Gemini is attempted first; Groq is tried if unavailable or rejected. Help conversations persist, with actual provider/model metadata. With no configured provider, help reports unavailable and produces no substitute answer.

These service credentials only support platform questions. Help cannot read business documents, retrieve vault values or execute tools. Business agents continue to use Key vault default/per-agent bindings and organization data policies. New chat/discussion runs default to strict provider execution. Evidence only is a deliberate calculation mode, not model-generated analysis. An optional discussion evidence fallback must be explicitly enabled.

## Test the changes locally

1. Create a private workspace and upload `sample-data/ecommerce-sales.csv`. Select Evidence only and ask for sales metrics and an investigation. Verify 45.10 USD net revenue, two orders and 22.55 USD AOV. Use View results and Review action. No task is created before approval.
2. Open Discussion room. Choose/create a conversation, attach evidence, enter a question and open Discussion settings to select a configured vault route or explicit Evidence only. Check actual specialist checkpoints and the reviewed decision gate.
3. Open Agent control center, search the connector catalog, and configure Evidence utilities. Check the real health/discovered tools below. Remote recipes require your endpoint, allowlist and authorization; choosing a card does not connect a third-party account.
4. Open Canvas → Automations. Create a scheduled review, an upload-triggered review or a conditional review. Choose the evidence conversation, enter a question and select a route. A condition such as net_revenue below 50 matches the sample CSV. Upload a new file or select Check latest upload, then refresh status. Open the linked conversation to inspect the execution. Checking the same automation/upload pair twice creates only one run. Missing metrics do not satisfy conditions. Uploads superseded before processing are skipped.
5. Open Help. Without private service credentials, verify it explicitly reports unconfigured. With valid credentials, ask a platform question and verify provider provenance and reload persistence. Live Gemini/Groq acceptance still requires your credentials; automated provider tests use mocked HTTP responses.

Upload triggers cover authorized local document uploads, not Shopify events or external webhooks. Automations queue reviews; they never auto-approve proposed actions. A paused trigger skips pending events. Revoked creator access prevents new reviews. Scheduling requires a running API worker. Public TLS, independent security review, account recovery/MFA and distributed operational controls remain deployment work; this change is not a production certification.
