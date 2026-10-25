# Growth Insights: current acceptance scope

Growth Insights is Evolvyn's business decision workspace, not a collection of fabricated KPI dashboards. The implementation preserves React/FastAPI/PostgreSQL, the existing governed tool registry, specialist graph, vault, approval gateway and durable scheduler.

## Audit and delivered slice

| Requirement | Status | Implementation / boundary |
| --- | --- | --- |
| Business onboarding | Working in local scope | Existing business API extended with validated IANA timezone, reporting currency, HTTPS website, model and objectives; editable profile in Growth Insights. Profile setup grants no provider access and performs no FX conversion. |
| Source connections | Partial | Existing shared MCP discovery/health/tool access reused. User uploads and opt-in Hacker News/Algolia public discussion reads work. Public discussions are not store/social account analytics. Native store/CRM/social account authorization and sync remain missing; no credentials supplied for live acceptance. |
| Quality and KPI pipeline | Working for current CSV contract | Existing normalized commerce parser, exact PostgreSQL metrics, duplicate-line/date/currency/null checks and explicit warnings reused. Current mapping version identifies Evolvyn's generic CSV contract, not Shopify/CRM native support. No silent row dropping or inferred zero amounts. |
| Immutable growth snapshot | Working in local scope | `backend/growth.py` persists metrics, facts, evidence, actions and upload provenance: source IDs/hash, mapping version, periods, included/excluded/dated rows, currency, warnings and capture time. Capture time explicitly does not establish provider freshness. Previous snapshots do not change on later uploads. |
| Growth UI | Working | Overview, Evidence, Action plan and Monitoring. KPI cards, accessible product-contribution meters with numeric labels, evidence quality/provenance, public citations/dates, hypothesis cards, real run progress and persisted receipts. No synthetic chart histories. |
| Model-backed intelligence | Existing capability reused | Snapshot extraction/SQL and starting hypotheses are explicitly deterministic. Action workflow and specialist review use the selected workspace/agent model route; evidence rules require explicit selection. No credentials copied from platform Help. No live Gemini acceptance claimed for this change. |
| Forecast | Missing, safely suppressed | No comparable-complete-history/backtest adapter exists. UI shows unavailable and explains why; no extrapolation or promise of business lift. |
| Monitoring | Partial | Existing PostgreSQL scheduler/worker queues evidence reviews; UI configures daily/weekly elapsed cadence, pause/resume, manual run, latest actual state and errors. Reopening restores state. This is not provider sync, webhook ingestion or a complete freshness/threshold/quiet-hours monitor. Sources must be refreshed by uploads or separately configured tooling. |
| Proposed actions and execution | Working for internal tasks | Existing analysis → explicit human approval → registered `create_experiment_brief` tool → verified SQL tasks/receipt. Replays remain rejected. Growth actions can also be proposed as draft memory; this does not execute anything. |
| Campaign planning | Working for local drafts only | Validated persisted objective, audience/consent/exclusions, channel, creative copy, CTA/HTTPS URL, aware schedule/timezone, duration, budget/currency, attribution, baseline/metric/guardrails/stop rules. No publisher exists. Draft saving grants no approval, delivery or spend. |
| Social publishing and spend | Missing / live acceptance blocked | Needs a provider-specific write adapter, authorized account/scopes, policy validation, argument/config/account/budget-bound approval, idempotency, uncertain-write reconciliation and verified delivery receipts. UI explicitly says publishing unavailable. |
| Outcome measurement | Working for supplied observations | Existing follow-up CSV comparison reuses saved baseline and validates date/currency compatibility. Outcomes/notes persist in the workspace. Raw pre/post differences are not causal lift; duration mismatch is shown. |
| Security | Working in tested scope; production review outstanding | Existing identity, project/tenant ACL, vault/data policy and approval boundaries reused for every route. Negative tests cover unauthorized project/member, viewer writes, other tenant, trash, malformed campaigns and replay. Does not constitute external penetration testing or production certification. |

## UI path

Open **Growth insights** (`/growth`). Configure/select a business, create/select an evidence workspace, then:

1. **Evidence:** upload sales/catalog/funnel CSV or consented feedback; enter a business question; create a snapshot. Optional public research sends that question to Algolia with explicit opt-in.
2. **Overview:** inspect the saved snapshot's actual metrics, product contributions, hypotheses and evidence limitations.
3. **Action plan:** start the growth workflow on current attached evidence. Use a configured model route, or explicitly select evidence rules. Inspect activity and proposals before approving an internal brief. Inspect verified tasks and upload/select a later CSV to compare outcomes. Campaign drafts are saved here without publication.
4. **Monitoring:** schedule an evidence-only review of the current files. Pause/resume or run it now; approvals remain human-controlled. Refresh retrieves persisted latest state. Cadence is fixed elapsed time, with due dates in the browser timezone.

Evidence workspace and business selection restore within the current project/business scope after navigation/refresh. Pending growth workflows and specialist reviews reconnect through the existing streaming API; campaign drafts, schedules, tasks and measurements are loaded from PostgreSQL.

## Operator setup and external acceptance

No extra service, migration engine, scheduler or connector registry is introduced. Records use the existing tenant JSONB store and commerce tables. Install/rebuild with the repository's existing Docker Compose instructions.

- For remote intelligence, configure a workspace default/per-agent route and credential in Key vault, and allow the chosen provider in organization/project data policy. This environment does not contain the user's locally saved Gemini key.
- For remote read tools, use the existing MCP registry: configure an approved-host transport, encrypted credential reference and read-only tool schema; successfully test/discover it, then select it from Connections & tools. Provider-specific scopes/account identity/freshness must be verified separately. Do not paste secrets into tool arguments or campaign copy.
- Algolia public discussion activity requires opt-in and internet access, not a provider account. Its sample is nonrepresentative and cannot establish market size or customer demand.
- No social publisher is implemented by this change. Providing a key alone does not enable publishing. Finish the adapter/approval/reconciliation contract and live provider tests before exposing a publish action.

## Verification

`tests/test_growth_workspace.py` exercises profile/schema validation, persisted provenance and snapshot immutability, draft validation/persistence, tenant/project/viewer/trash boundaries, real approval/verified-task history, replay rejection and follow-up metrics.

`tests/e2e_growth_workspace.py` runs an isolated real API/PG/browser journey using **synthetic uploaded CSVs and explicit evidence mode**, not a mocked live LLM. It checks profile → evidence → SQL snapshot → accessible overview → restored pending workflow → human approval → actual tasks → follow-up comparison → saved campaign draft → persisted paused schedule, plus mobile overflow. `tests/e2e_evolution.py` preserves the specialist-review/canvas/export regression through the updated tabs.
