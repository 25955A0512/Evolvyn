# E-commerce execution audit

Baseline inspected: `8bea9d6`. The existing React/FastAPI/PostgreSQL application and visual design were retained. The initial application was healthy, and the nine existing workflow/approval tests passed before edits.

## Findings and implemented corrections

| Journey | Before this change | Implemented path |
| --- | --- | --- |
| Business workspace | Private business/project accounts worked; no explicit e-commerce classification | Existing business form now records an e-commerce business type |
| Sales/catalog ingestion | CSV text persisted; numerical analysis only understood `period,visits,paid` | Existing upload validates supported sales/catalog schemas and atomically stores normalized rows in PostgreSQL |
| Business metrics | Revenue/orders/AOV/product sales absent | Exact numeric SQL aggregates; distinct orders, discounts/refunds, posted-status filtering, product contributions and metric definitions |
| Existing chat | Durable job, worker lease, streaming response and saved history worked | Same workflow consumes structured commerce data and explicitly selected read-only registry tools |
| External evidence | Real HN research and MCP discovery/invocation existed, but chat had no connector selection | Shared connection picker in chat/development/discussion/growth; chat can fetch public research and collect actual tool results with retrieval timestamps |
| Recommendations | Generic funnel/feedback rules or optional model proposals | Commerce-specific, evidence-linked investigation proposals; optional model input includes structured metrics; facts and hypotheses remain separate |
| Approval/execution | Approval atomically created real internal briefs/tasks, directly in the route | Existing action is now the registered `create_experiment_brief` tool, with server approval, policy checks, one-shot decision, task-count verification and a persisted execution receipt |
| Outcomes | Conversion-only follow-up | Existing reports form compares new dated sales snapshots to the immutable approved baseline; same currency, nonoverlap and duplicate-baseline checks |
| History | Conversations, runs, decisions and artifacts persisted | Structured imports, connector context/results, verified action receipts and commerce measurements persist alongside that history |
| Readability | Control-center flex items could shrink until wrapped captions overlapped | Navigation items retain their height; labels, captions and supporting text have readable sizing/contrast |

## Actual execution trace

1. `frontend/src/main.tsx`: upload and chat send use the existing authenticated API client. `ToolAccess.tsx` reads the existing registries and supplies selected calls, not a second registry.
2. `backend/app.py:upload`: authorization and file limits → `commerce.parse` → one transaction inserting the document, normalized dataset/lines and conversation attachment metadata. Invalid commerce imports leave no partial document.
3. `POST /api/conversations/{id}/runs`: resource/data policy, tool contracts and evidence preflight → persisted execution and user/assistant messages → existing leased worker.
4. `perform_job`: actual configured public research (or an explicit outage) → registered `analyze_business` → SQL aggregates and source IDs → selected read-only tool invocation → evidence-linked strategy and MCP ranking → streamed narration/report → approval checkpoint. Financial values are calculated by SQL, not an LLM or RAG.
5. `POST /api/executions/{id}/decision`: administrator approval → policy-checked tool gateway → row-locked decision and real internal task/brief writes → verify saved task count → persist receipt. Replay or rejection creates no duplicate tasks. Generic tool-approval records inherit the execution's project scope.
6. `POST /api/artifacts/{id}/measure`: authorized follow-up document in the same conversation → compare stored baseline and new SQL snapshot → persist measured observations → existing reports/history UI.

## Metric and import boundaries

Sales represent one row per order line: `order_id,product_id,quantity,unit_price`. `sku`, `qty`, `price` and several ordinary header aliases are supported. Optional `line_id` disambiguates repeated SKUs within an order. Repeated order lines, invalid amounts, inconsistent dates and mixed currencies are rejected. Imports are bounded to 5,000 rows and the existing 2 MB file limit; they do not silently truncate to the old funnel's 1,000-row window.

Use explicit `discount` and `refund` amounts to calculate net revenue and net AOV. Missing adjustments remain unknown; gross sales/gross AOV are separate available metrics. Currency is never inferred. Cancelled, pending, failed and void lines do not count as posted sales. Gross units are ordered units, not an inferred number of retained/returned units. Shipping, taxes, costs, profit, visitor conversion, acquisition cost and lifetime value are not invented.

Catalogs use `product_id,product_name,unit_price`, with optional inventory/currency and supported aliases. Catalog prices/inventory never become realized revenue. Metric definitions and missing-data warnings appear in the conversation. Multiple sales files are treated as snapshots: analysis chooses the latest attached sales snapshot instead of summing overlapping exports.

Financial comparisons require explicit matching currencies, dated included lines and strictly later, nonoverlapping follow-up dates. Observed date spans are shown, with a warning when duration differs. Uploads do not prove full-period coverage or causal attribution. The executed action is task creation; a later sales change does not prove the task caused that change.

CSV files uploaded before structured imports were introduced retain their original content/history. Re-upload a supported sales/catalog file to create its normalized dataset. Arbitrary merchant-specific export formats still need an explicit mapping adapter.

## Real, unavailable and intentionally bounded capabilities

- MCP stdio discovery and invocation are real. HTTPS MCP supports configured public hosts, credentials and policy, but no third-party merchant MCP credential was provided for live verification.
- Public research is actual Hacker News/Algolia discussion discovery, with publication/retrieval dates. It is a limited source, not verified retail demand, competitor pricing, market share or representative customer sentiment. Dated competitor/store evidence requires an authorized source/integration. No Shopify, advertising, CRM or social account is claimed connected.
- The supported execution here creates real tracked internal tasks and a saved brief. It does not publish an advertisement, spend money, change store prices or modify a third-party system. No simulated external execution is presented as real.
- Evidence mode is deterministic and clearly labeled. Optional configured/local models interpret the same evidence; their hypotheses require review. The product builder's existing trusted source adapters and scoped interactive prototype remain bounded capabilities, not arbitrary code execution.
- Registered/available adapters are distinguished from successful connectivity checks. Tool argument errors produce a sanitized validation response before a workflow is queued.

## Verification

`tests/test_commerce.py` covers exact arithmetic, order deduplication, incomplete adjustments, invalid imports, more than 1,000 sales lines, import limits, tenant/project isolation, live stdio MCP, mocked public-source parsing/dates, external-source outage, approval/replay/denial and persisted outcome history. Existing tests continue to cover the broader platform.

`tests/e2e_commerce.py` exercises the existing business/chat UI, sales upload, real SQL metrics, real MCP context, live public research or its labeled outage, approval and verified task creation, follow-up upload/comparison, reload persistence and mobile layout. Existing account, registry/governance and product-studio browser regressions also run. Test database schemas are isolated per test so scheduled work from one test cannot execute in another test's mocked provider context.

The synthetic acceptance data yields gross sales 50.30, discounts 0.20, refunds 5.00, net revenue 45.10 USD, two orders and net AOV 22.55 USD. Its follow-up yields 70.00 USD net revenue and a 24.90 USD observed difference. These are test-file calculations, not claimed real-company business results.
