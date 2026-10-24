# Workspace visual refresh

The existing React/FastAPI/PostgreSQL architecture, approvals and execution path are retained. The supplied Manus screenshots inform the restrained layout and task interactions; this is Evolvyn's own interface and branding, not a claim of identical Manus capabilities.

## Implemented

- Illustrated entry cards for product development, growth evidence and specialist discussion; all open existing working areas.
- A keyboard-accessible composer `+` menu for local uploads, MCP configuration, saved reports, product development and Canvas. Escape and clicking outside dismiss it. Uploads use the original authenticated file endpoint and existing validation.
- Consistent locally hosted Tabler navigation icons, calmer surfaces, larger chat text, recognizable provider/connector logos and a stage-specific execution timeline. Execution states, tools, approvals and results remain real saved backend records.
- Seven unchanged images from the user's `images.zip`: Shopify, GitHub, Google Drive, Slack (original file `slcak.png`), Notion, Gemini and Groq. These identify services, not active connections. They are embedded in `frontend/src/assets/connector-logos.ts` so exported consoles retain the exact image bytes. SHA-256/source metadata is recorded in `CONNECTOR_ASSETS.json`.
- Tabler SVG icons from the official author repository, with its MIT license and hash/source manifest in `frontend/public/assets/tabler`. Runtime exports explicitly include these public assets and attribution; private uploads/configuration remain excluded.
- Responsive menus/cards/chat and reduced-motion support.

## Reference access limits

Both `https://www.figma.com/community/icons?resource_type=files` and `https://manus.im/app` were blocked by the execution environment's network proxy. No live signed-in Manus inspection or direct Figma Community download is claimed. Icons were downloaded from the official Tabler distribution instead. The uploaded recording could not be transferred because it exceeds the tool's 32 MiB file limit; it was not viewed. Screenshots already supplied in the conversation were used as reference. A shorter recording remains useful for further interaction review.

Subsequently, two smaller recordings were successfully transferred and visually reviewed. Their working interaction patterns are implemented in the [recording-driven update](REFERENCE_INTERACTIONS.md).

## Verify

```bash
npm --prefix frontend run build
.venv/bin/python -m pytest tests/test_visual_assets.py tests/test_studio_agents.py -q
python tests/e2e_visual_workspace.py
python tests/e2e_experience.py
python tests/e2e_commerce.py
python tests/e2e_studio.py
python tests/e2e_control_center.py
.venv/bin/python tests/live_exported_runtime.py
```

The browser scripts require the running local app at `EVOLVYN_TEST_URL` (default `http://localhost:3000`). Visual acceptance uses synthetic business data and explicit Evidence only mode; no provider connection or business outcome is invented.

Verified: **140 automated tests passed**; the new visual acceptance and existing experience, e-commerce, control-center and product-studio browser checks passed. Exported frontends compiled and the independent runtime passed account/MCP/governance and nested export checks. The production frontend build passes, with Vite's existing large-chunk advisory; the seven embedded logos add about 70 KB of source data and avoid external image requests. Public deployment and live remote model/provider acceptance are unchanged.

Actual browser screenshots: [home](screenshots/workspace-refreshed-home.png), [contextual menu](screenshots/workspace-add-menu.png), [supplied logos](screenshots/workspace-uploaded-connectors.png), [provider selection](screenshots/workspace-model-logos.png), [mobile](screenshots/workspace-refreshed-mobile.png).
