# Workspace dashboards

The key vault, connections, discussion room, Growth Insights overview and monitoring screens use compact cards and short labels. Existing APIs, permissions and approval flows remain in place.

- **Key vault:** Add/replace/revoke a key in a dialog; load actual Gemini models and explicitly apply one to all agents. Agent routes show effective configuration, with override, reset and test controls. Saved credentials are not labeled verified connections.
- **Connections:** Connected, Discover and Tools separate actual MCP discovery from available setup recipes. GitHub authorization and the Instagram Growth Insights connection entry remain available. Discovery status is not proof of provider account access.
- **Discussion room:** Prompt shortcuts, inline conversation and a visible bottom composer; Enter sends, Shift+Enter inserts a newline. Models and tools are in Discussion settings. Decisions still require approval.
- **Growth Insights:** Customize shows/hides overview widgets and saves the layout per scope in this browser session. Chart/Table uses actual product revenue and units from the selected evidence snapshot. Forecast details remain available when evidence is insufficient.
- **Monitoring:** Compact schedule counts and existing enable/pause/run controls use persisted schedule records.

## Verification

`python tests/e2e_dashboard_refresh.py` exercises encrypted key storage, model selection, route overrides/reset, discussion submission, actual local MCP stdio discovery, tool browsing, widget persistence, SQL product metrics, monitor pause and mobile layouts. Provider HTTP responses are explicitly controlled fixtures; this does not establish live Gemini or Meta acceptance.

`python tests/e2e_growth_workspace.py` checks the existing evidence-to-approval-to-task-to-measurement flow. `python tests/e2e_chat_input.py` covers Product Studio submission and model selection regression. `npm --prefix frontend run build` checks TypeScript and the production bundle; visual asset tests ensure the new components are included in exported runtimes.

After frontend deployment, visit Key vault, Connections, Discussion room, Growth Insights and Monitoring. Validate real provider credentials privately; no key values or synthetic usage charts are displayed.

Discussion reader correction: the transcript uses the available width/height, collapses specialist handoff chips under Team progress, and reveals the first answer once instead of scrolling to the approval form on every event. View responses and Review decision move only the internal transcript; the composer stays visible. Long text/code/tables remain scrollable. The browser check now supplies long controlled replies and asserts actual viewport visibility at 1440×960, 1280×650 and 390×844, including navigation between replies and the approval form.
