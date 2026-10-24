# Implementation checklist

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
