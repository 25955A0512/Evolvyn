# Implementation checklist

Public OAuth UX: removed deployment instructions from public sign-in, retained owner/admin diagnostics, added availability/error/retry states and direct configured-provider links with Google/GitHub icons. Browser acceptance verifies the actual start redirects/state/PKCE with controlled provider boundaries, email signup, owner settings and mobile; 54 focused backend tests and the frontend build pass. Real Google/GitHub sign-in awaits provider applications and Render credentials. See [public OAuth setup](PUBLIC_OAUTH_SETUP.md).

Vercel/Render preparation: 265 backend tests passed; production frontend build and actual managed-style API/compiler process checks passed, including SQL health and vault decryption after an API restart. Prepared Render Blueprint, private compiler/DB wiring, stable vault seed custody, Vercel SPA/proxy configuration and deployment guide. Actual resources, public URL wiring and live OAuth remain pending dashboard deployment. See [Vercel + Render](VERCEL_RENDER_DEPLOYMENT.md).

OAuth/AWS preparation update: 239 backend tests passed, production frontend build passed, connected-route browser journey and actual API/proxy OAuth log redaction passed. Added private OAuth setup CLI, strict origin/cookie checks, initiating-session/configuration-bound states, safer callback errors, and locally checked EC2/ALB Compose/nginx overlay. AWS provisioning and live Google/GitHub acceptance still require an operator domain and registered applications. See [AWS first deployment](AWS_FIRST_DEPLOYMENT.md).

Growth workspace update: redesigned Overview/Evidence/Action plan/Monitoring around the existing evidence-to-approved-task-to-measurement loop. Business profiles, source provenance, draft campaigns and restored run/history state persist through the existing APIs/records. Full backend suite: 215 passed; expanded growth suite: 18 passed. Production build and real API/PG desktop/mobile growth journey passed using synthetic uploads and explicit evidence mode. Live native account sync, social publishing and forecasts remain incomplete. See [growth acceptance scope](GROWTH_INSIGHTS_SPEC.md).

Latest interaction update: **145 automated tests pass**. Both supplied smaller recordings were reviewed. The existing agent catalog now supports searched capability selection and real bounded execution; account preferences persist with account isolation; searched recent conversations/evidence, native settings dialogs and the shared connector gallery are integrated. See [REFERENCE_INTERACTIONS.md](REFERENCE_INTERACTIONS.md) for the concrete behavior and checks. Existing cloud/provider launch limits below still apply.
- [x] FastAPI, React/TypeScript, PostgreSQL; reproducible locked dependency installation.
- [x] Private single-owner workspace token; persisted business profiles and goals.
- [x] Saved conversations, file references, decisions and internal artifacts.
- [x] UTF-8 TXT/CSV upload validation (10 files, 2 MB each).
- [x] Numerical funnel calculations with source row attribution.
- [x] BM25-style lexical passage retrieval with original character offsets.
- [x] Conversational context supplied to the provider (last eight messages).
- [x] Background analysis, persisted live execution events and streamed output.
- [x] Explicit evidence-only mode; OpenAI mode never silently falls back on failure.
- [x] Cancellation, 45-second run budget, provider timeout/output limits, four-run capacity.
- [x] Editable approval; atomic replay-safe internal brief creation and viewer.
- [x] Real public discussion research persisted with URLs, publication/retrieval timestamps.
- [x] PostgreSQL snapshot backup and restore validated in a temporary database.
- [x] API tests covering policy boundaries, failures, retrieval, execution and provider adapters.
- [x] Desktop/mobile Chromium vertical-slice validation with refresh persistence.
- [ ] Live OpenAI completion: injected credential returns 401 invalid_api_key.
- [x] Resource-bounded PDF/DOCX extraction in addition to TXT/CSV.
- [x] Evidence-linked recommendation cards with assumptions, risks, tasks and heuristic priorities.
- [x] Project records, internal task status/notes and follow-up CSV outcome comparisons.
- [x] Typed tool registry and a real local MCP strategy integration.
- [x] Recurring analysis schedules with persisted due times and manual triggers.
- [x] One-click isolated sample workspaces with expiring scoped tokens.
- [ ] Embedding-based semantic retrieval.
- [x] Account registration/login, scrypt hashes, HttpOnly sessions and organization RBAC.
- [x] Cookie-origin/application-header checks, bounded auth attempts, payload-free audits and container web security headers.
- [ ] Production identity recovery, email verification and external security review.
- [x] PostgreSQL worker leases, bounded recovery attempts, stale-worker write protection and reuse of completed evidence/strategy checkpoints.
- [ ] Configurable transient-provider retry routing and broader failure evaluation.
- [x] Persistent multi-server MCP registry, health management, scoped auth references and built-in/MCP adapters.
- [x] Bounded declarative execution graphs with branches/joins/loops, checkpoints, same-provider transient retries and argument-bound write approvals.
- [x] Central risk/tool/data policy and restricted project member ACLs, with linked-resource enforcement.
- [x] Agent control center with real registry, execution and governance operations.
- [x] Fixed-destination local/OpenAI/Groq/Gemini adapters, local-only policies, reported usage and schema-validated model proposals.
- [x] Official model downloaded, SHA-256 verified, and served locally without any API key.
- [x] Real model-generated structured recommendations, narration, approval and tasks verified through the application.
- [ ] Live optional remote-provider validation and configured pricing.
- [x] Safe Markdown rendering and attachment removal.
- [x] Workflow inspection and actual tool metadata.
- [x] Grouped/searchable history, draggable workflow canvas, persisted templates and execution of saved configuration.
- [x] Business/project-scoped document reuse across conversations.
- [x] Five bounded operational agent interfaces over uploaded logs/runbooks.
- [x] Built and started Nginx/API/authenticated PostgreSQL Compose stack; readiness and browser journey verified.
- [x] Follow-up measurements from user-uploaded CSVs, with non-causal labeling.
- [ ] Public hosting/TLS deployment, real business experiment outcomes and fresh-cloud-task restoration.

This is a tested development application. The complete P0/P1 brief is not finished.

Earlier milestone: 29 API/unit/integration tests passed; TypeScript and production build passed; Chromium desktop/mobile journey passed with project creation, evidence upload, three recommendation cards, approval, task updates, artifact retrieval and refresh persistence. The one-click sample workspace also passed in Chromium. A real rejected provider request successfully produced a visible deterministic fallback and three recommendations.

Earlier milestone: 47 tests passed; frontend type/build passed; authenticated Chromium journey and saved workflow execution passed through Nginx; local runtime release checksum and container executability verified. The model weights are installed and verified; actual local inference is now working. No OpenAI key is required.

Live local acceptance: Qwen generated valid recommendation cards with allowed citations and a streamed response; explicit approval created internal tasks. No provider fallback was used. The representative run took 50.14 seconds on four CPU cores. Public hosting remains separate from the verified loopback container deployment.

Infrastructure module acceptance: 65 isolated-schema tests pass. Desktop/mobile Chromium exercised account creation, evidence ingestion and analysis, two genuine stdio MCP servers, persistent capability binding and invocation, graph decomposition/save/run/pause/approval/completion, policy save and enforcement, restricted project access settings and refresh persistence. TypeScript/production build and the three-service Compose readiness checks pass. Remote HTTPS credentials remain optional and have not been live-tested against a third-party server.


## Business and product studio extension

- [x] Encrypted organization credential vault, no readback, provider separation, versioned replacement/revocation and default/per-agent model routes.
- [x] Actual LangGraph specialist handoffs and bounded reviewer/product-manager loops with PostgreSQL node checkpoints and recovery.
- [x] Scoped reviewed agent memory with provenance, retention, recall and forgetting; role contracts and graph capability boundaries.
- [x] Requirements interview, revisiting choices, explicit application of reviewed business decisions and immutable source revisions.
- [x] Trusted React/FastAPI/PostgreSQL and React/Express/PostgreSQL source adapters with account authentication and private CRUD.
- [x] Persistent build-scoped interactive prototypes, source inspection/download, honest capability and pending-requirement reporting.
- [x] Model input/output credential guards, per-agent usage, fresh background membership and outbound provider-policy checks, including the compatibility analysis endpoint.
- [x] Conversational studio interface based on the supplied reference, with product/agents/memory/vault/integration areas and desktop/mobile acceptance.
- [ ] Arbitrary model-authored code execution, additional stack adapters, semantic/vector indexing, live OAuth validation, SSO/MFA/recovery, cloud deployment and independent security certification.

Previous studio milestone: **86 tests passed**. Generated React compilation, generated FastAPI private-account CRUD, and generated Express against isolated real PostgreSQL were exercised. The complete studio browser flow passed in Chromium, as did existing account and control-center flows. A live four-specialist Qwen discussion completed in 134 seconds without fallback; its missing-citation issue remained visible at human review. Source-build validation is distinguished from a deployed generated runtime. See MODERN_STACK.md and CLOUD_DEPLOYMENT.md.

## Connected evolution runtime

- [x] Shared runtime discovery and entity/action ontology across actual tools and adapters.
- [x] First-party dated series comparisons, comparable public discussion windows, source outage fallback, source-linked product/promotion experiments and MCP evidence.
- [x] Growth snapshot → specialist discussion → human decision → scoped memory → explicit product revision.
- [x] Versioned page drawing, draggable labeled blocks, freehand annotations, structured design prompts and application to generated UI/prototype.
- [x] Visual executable graph nodes/connections, conditions, approval/resume, bounded cycles and existing runtime execution controls.
- [x] Complete runtime source included in product exports, isolated fresh accounts/vault/database, tested independent startup, real MCP and nested export.
- [x] Google/GitHub OAuth adapters, verified email, PKCE, browser/state/replay defenses and explicit linking; password change and all-session revocation.
- [x] Larger readable typography, responsive canvas and corrected nested-aside/composer overflow on mobile.
- [ ] Live OAuth credential acceptance, native CRM/social OAuth, arbitrary-code sandbox, more source adapters, semantic memory, MFA/recovery and production deployment/security review.

Previous connected-runtime validation: **103 unit/API/integration tests passed**. The connected browser flow passes including a visual three-node graph and approval/resume. Existing account, product studio and control-center browser regressions pass. Exported product and runtime console compile; the exported API starts independently against an isolated real PostgreSQL schema, invokes a real bundled MCP server, enforces governance, and produces another complete export. Live public research returned real indexed counts. OAuth endpoints use mocked external responses in tests; no real OAuth credentials or third-party CRM credentials were available. No public hosting, arbitrary-code execution or production certification is claimed.

## E-commerce intelligence and execution slice

- [x] Existing business/chat UI retained; explicit e-commerce workspace type.
- [x] Atomic validated catalog/sales ingestion into structured PostgreSQL datasets; exact numeric aggregation, distinct orders, gross/net/AOV definitions, refunds/discounts/status handling and product contributions.
- [x] Unknown adjustments/currencies/costs are not invented; catalogs do not imply revenue; snapshots are not summed blindly; bounded imports do not silently truncate sales rows.
- [x] Shared MCP/tool access in development, chat, discussion and growth; selected read-only tool calls are actually invoked and their results/time/trace saved.
- [x] Optional actual public discussion research in the chat run, dated citations and explicit outage continuation with local evidence.
- [x] Existing approval action uses the registered, policy-checked tool; real internal task/brief writes, replay protection, persisted verified receipt and private-project approval scope.
- [x] Same-conversation follow-up sales comparison, immutable baseline, currency/date/duplicate-source checks and explicit causal/coverage limits.
- [x] Control-center purpose explained in-product; readable nonoverlapping captions and contextual connection access.
- [x] Per-test database isolation prevents old test schedules from running inside unrelated mock-provider fixtures.
- [ ] Native merchant/social/ad credentials and live external publication; arbitrary CSV mappings; quantitative competitor/market-share conclusions without an authorized source.

Validation: **130 tests passed**. The live e-commerce browser journey and existing account, registry/governance and studio browser regressions pass. Actual public research succeeded during acceptance, but it remains limited discussion evidence. No live external store/ad action or causal revenue improvement is claimed. See ECOMMERCE_AUDIT.md for the actual execution path and import/action boundaries.

## Product agent workspace revision

- [x] Existing builder retained; default requirements conversation invokes actual model gateway through bounded graph nodes.
- [x] Confirmed requirement proposals, revision conflict prevention, persistent agent history.
- [x] Enabled PRD/architecture/interface/reviewer phases, typed diagrams, hierarchical source inspection and approval-bound implementation.
- [x] Isolated non-executing frontend compiler with honest passed/failed/unavailable receipts; application runtime status remains separate.
- [x] File-free conversational chat; no CSV preflight for ordinary greetings.
- [ ] Arbitrary generated application execution, domain-specific code repair and cloud preview/deployment broker.
- [ ] Live remote-provider acceptance requires valid private credentials.

Verification for this revision: 158 backend tests pass; TypeScript/Vite production build passes. Live Chromium checks pass for account, e-commerce, control center, guided studio, canvas/evolution, and the new local-model builder. The live source-build case uses PRD, architecture and interface agents plus human approval; the four-agent local run separately verified reviewer rejection blocks source generation. Controlled model fixtures verify the four-agent positive path, stale/replayed approvals and invalid outputs. Both emitted frontend stacks compile through the real isolated service; unauthorized requests, invalid syntax/imports/paths and incomplete receipts are rejected. The exported runtime passes independent startup/accounts/MCP/governance/nested-export checks. Gemini/Groq calls remain unverified without credentials.


## Connected identity and Gemini routing revision

- [x] Native Gemini API gateway, workspace-scoped default inference for one unbound saved Gemini key, explicit “Use for all agents” control and safe actionable provider failure diagnostics. Explicit routes and local-only policy remain authoritative.
- [x] Visible Google/GitHub signup controls with in-app setup guidance, verified OAuth return-session handling and query-free API/proxy logging.
- [x] Browser-bound GitHub connector authorization, encrypted token storage, actual trusted stdio MCP discovery, public read-only repository/issue tools, connection tests and local disconnect.
- [x] Discussion-only membership, no-upload model discussion, workspace-key platform help without business-document context, refreshable module routes and lazy-loaded major panels.
- [x] Editable revision-checked PRD drafts, real DOCX download and responsive product panels; late document loads cannot erase unsaved edits.
- [ ] Live Gemini and OAuth provider acceptance: the user's saved key is in their local database, and OAuth applications have not been registered. In-app setup guidance is implemented as requested.
- [ ] General MCP OAuth, other native service authorizations, private GitHub App scopes/writes, arbitrary generated-app execution/repair/preview, source editing/diffs/rollback and cloud release remain incomplete. See PRODUCT_STATUS.md and CONNECTED_IDENTITY.md.

Validation: **171 backend tests passed**, with one dependency deprecation warning. TypeScript/Vite production build passed. Chromium acceptance passed for routed modules and refresh/back navigation, OAuth setup and return-session handling, default-key controls, saved PRD/DOCX, existing guided studio, account, commerce, control center and canvas/evolution. Both generated frontend stacks passed real isolated compiler checks, including invalid syntax/import/path and unauthorized-request rejection. Independent exported-runtime startup/accounts/MCP/governance/nested-export checks passed. Actual API/nginx logs exclude synthetic OAuth codes and state while retaining request IDs. Controlled native-Gemini and OAuth fixtures cover external boundaries; they do not establish live provider connectivity.

A local readiness-only probe completed 100 requests at concurrency 4 with zero errors, median 46.99 ms and p95 176.78 ms. This measures nginx/API/PostgreSQL health only, excludes authentication, models and tools, and is not an agent-workload or production-capacity benchmark. No cloud deployment or production-readiness certification is claimed.


## Chat-first Product Studio and restored builds

- [x] Reviewed both supplied screen recordings: the old UI required repeated two-field proposals, left the build control behind eleven missing decisions, and remounted without restoring a selected product.
- [x] Replaced the initial name/goal form with a broad conversation. The real model proposes a complete, typed starting setup for explicit review; clarification and subsequent edits remain in the same chat. Ordinary questions after setup use the conversational contract rather than proposing the entire setup again.
- [x] Confirmation saves the revision and launches the existing durable graph in the same backend request. Partial plans and configuration failures retain reviewed decisions and show an actionable launch error; stale/replayed confirmations cannot create another build.
- [x] Added a read-only source-manifest planning tool. Actual adapter paths appear before implementation, the folder pane opens automatically, and saved source contents replace planned paths after approval and compilation. No arbitrary generated code is executed in the API.
- [x] Product selection survives module navigation and refresh through an organization/project-scoped session selection and the product URL. The UI reloads database history/builds and reconnects to active execution streams; leaving the module does not cancel a job. Explicit new conversations remain new on refresh.
- [x] Current agent phases, recent events, model output, review issues, implementation approval and failure states are visible in the conversation. Restored pipeline options match the saved graph. Readable desktop/mobile layout and the offline guided form are retained.
- [x] Planning rejects empty decisions and normalizes typed entity arrays through the existing requirement validator. Opaque response schemas avoid graph-reference depth failures without relaxing the graph's argument-depth limit. Product design review is explicitly distinct from permission to execute; exact-argument human approval remains mandatory.

Validation: **176 unit/API/integration tests passed** with one dependency deprecation warning, and TypeScript/Vite production build passed. The actual local-model Chromium journey verified complete planning, navigation away/back during both model and build runs, a persisted folder plan, human approval, real isolated frontend compilation, generated source, refresh/new-product/history and mobile layout. The live four-agent model requested scope changes and correctly produced no source; an explicitly selected three-agent workflow plus human review then generated the compiled artifact. Controlled model tests cover a positive four-agent path as well as reviewer rejection. Final routed-module/OAuth/vault/PRD and guided-studio browser regressions passed. Both exported frontends compiled, and the independent exported API passed fresh-account, actual MCP, governance and nested-export checks. Live Gemini acceptance still requires the user's privately configured local credential; none was copied into this cloud workspace.

Generated source remains limited to the supported trusted adapters, private accounts and scoped entity CRUD. A compiled source artifact and the working data prototype are not an arbitrary generated application runtime or a cloud deployment. See PRODUCT_STATUS.md for broader unfinished modules.


## Usability, model-authored files and 15-day trash

- [x] Viewport-sized Product Studio with a continuously visible composer, internal transcript scrolling, persistent sidebar collapse, four core work areas and grouped configuration.
- [x] Compact searched connections/tool access with actual historical test states and disabled-tool enforcement.
- [x] Business/product conversation trash, restore, 15-day expiry, scheduled cleanup, active-run cancellation and linked-data access checks. Shared documents/graphs are preserved; associated source-linked memories are removed with expired content.
- [x] AI builds use a model-authored manifest and individual model calls for each file. Only completed persisted files appear in the tree. Prior builds are not shown as the current run's output. The offline guided source adapter stays separately labeled.
- [x] Larger bounded artifact/source allowances, one bounded truncated-file retry, approval-bound source budgets, partial-file retention, revision/trash-safe writes and truthful compilation/runtime boundaries.
- [x] Private compiler supports nested source modules while rejecting filesystem escapes and unapproved dependencies.

Verification: **198 backend tests passed** (one dependency deprecation warning), production build passed, and the isolated API/PostgreSQL/browser acceptance passed desktop/short-window/zoom-equivalent/mobile layout, navigation, connectors, model-boundary-controlled per-file generation, old-build isolation, and business/product trash/restore. The real private compiler bundled nested React source and rejected a host import. Existing route/OAuth/vault/PRD, guided studio and independent exported-runtime checks passed. Model and OAuth external boundaries remain controlled where live credentials are unavailable; no live Gemini or arbitrary generated-backend execution is claimed. See CLEAN_STUDIO.md for exact retention and execution limits.
