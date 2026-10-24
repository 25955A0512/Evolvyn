# Implementation checklist
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
- [ ] Arbitrary model-authored code execution, additional stack adapters, semantic/vector indexing, production OAuth/SSO/recovery, cloud deployment and independent security certification.

Final automated validation: **86 tests passed**. Generated React compilation, generated FastAPI private-account CRUD, and generated Express against isolated real PostgreSQL were exercised. The complete studio browser flow passed in Chromium, as did existing account and control-center flows. A live four-specialist Qwen discussion completed in 134 seconds without fallback; its missing-citation issue remained visible at human review. Source-build validation is distinguished from a deployed generated runtime. See MODERN_STACK.md and CLOUD_DEPLOYMENT.md.
