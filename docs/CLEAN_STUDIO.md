# Studio usability, source generation and conversation retention

The screenshots that prompted this revision exposed three concrete gaps: nested minimum heights pushed the composer below the browser viewport; AI builds displayed the trusted template adapter's manifest before source existed; and the Gemini artifact allowance was too small for the requested drafts. Conversation deletion and studio navigation collapse were missing.

## Implemented behavior

- The studio has one viewport-sized layout. The transcript scrolls internally, while the composer remains visible at short desktop, zoom-equivalent and mobile sizes. The sidebar toggle persists across refresh. Four daily work areas remain in the main navigation; configuration is grouped under Workspace tools.
- Connections use a compact searched menu with actual server test status, add/manage actions and tool access. Disabled tools cannot be newly selected. A historical successful test is labeled as such, rather than inferred live connectivity.
- Ordinary and product conversations support soft deletion, restore and a 15-day retention timestamp. Active/waiting jobs and in-progress source builds are cancelled. Parent/child resource checks hide trashed data from direct reads, lists, approvals, retrieval and agent memory. Shared documents remain accessible through another permitted conversation.
- Retention cleanup runs at server startup, approximately once per minute while running, and when trash is opened. Expired entries cannot be restored. It removes conversation-owned executions, artifacts, source builds, documents/datasets and source-linked memories. Shared documents and shared graphs are preserved. Minimal audit metadata remains. This is application-store retention; infrastructure backups require their own retention policy.

## Actual AI-source path

The existing chat → validated setup → durable graph → PRD/architecture/interface/review → exact-argument human approval path remains. New AI pipelines pass `generation=model` to the source tool. Existing guided template builds remain explicit and separate.

`backend/model_source.py` calls the scoped developer model for a manifest and then each file's contents. It does not invoke the template generator or attach an inventory of runtime files. Completed files are saved individually under the product's organization/project and revision. A transaction locks that revision during each save, so trash/revision changes cannot be overwritten by a late model response. The browser reconnects to the saved run and polls build progress only during the implementation phase. Source from a previous execution is not passed off as the current run's output.

Manifests allow at most 16 safe text paths. Source calls have a bounded token allowance, one bounded retry for truncation, a total reserved-output allowance and a call limit. Those limits are included in the approval arguments. Typical React entry points and the selected backend entry point are required; module names/folders and file contents are model-authored. Binary assets, fabricated dependency locks and unapproved frontend dependencies are rejected. Source syntax/JSON and basic Compose privilege/private-host-mount boundaries are checked. The non-executing compiler accepts nested frontend modules, with fixed installed dependency resolution and no arbitrary filesystem imports.

A saved source artifact is not a verified product runtime. Backend behavior, authentication/security acceptance, generated deployment behavior and arbitrary-app execution remain unverified. The in-app data sandbox is explicitly distinguished from the generated application. No third-party connection or live Gemini acceptance is inferred from the controlled tests.

## Verification

- Full backend suite and TypeScript/Vite production build.
- An isolated PostgreSQL/API/browser journey with controlled model responses: visible composer, navigation persistence, compact connections, actual per-file saves, a nested source tree, no previous-build contamination after navigation, business/product trash and restore, and mobile layout.
- Native Gemini HTTP boundaries checked with controlled transports: scoped credential headers and the larger file allowance. No live key exists in this cloud workspace.
- The actual private compiler bundles a nested React component and rejects a disallowed host-file import. Generated code is not evaluated.
- Existing routed OAuth/vault/PRD, guided studio and exported-runtime regression paths remain checked.

The exact final test totals are recorded in PROGRESS.md.
