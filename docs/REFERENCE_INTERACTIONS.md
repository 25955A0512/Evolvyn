# Recording-driven UI and behavior

Both smaller supplied recordings were accessible and visually reviewed (approximately 27 and 24 seconds). They show nested composer menus, skills browsing, connectors, automation entry points, and account/general settings. Reference frames remain in ignored private storage; no recordings or screenshots containing the user's Manus account details are published.

Implemented using the existing Evolvyn architecture:

- A bottom profile menu opens account/team controls, General settings, existing model connection checks and sign-out. General uses a native modal dialog with keyboard focus containment and Escape dismissal. The existing account/security/membership component is reused.
- Light, dark and device-dependent themes, larger text, optional completion tone and opt-in browser notifications persist in PostgreSQL **per authenticated account**, across sessions and organization changes. Personal preference updates do not grant business write access to viewers; the exact preferences PUT is the only viewer-write exception, with the same origin/application-header checks retained. Unknown fields and non-boolean values are rejected. Demo/token-only sessions cannot persist account settings.
- Notification permission is requested on the enabling gesture. Background notifications contain generic run status only; no business data or document text. Watched runs notify once after observed active work finishes or needs review. Historic completed runs do not generate new notifications. Browser/OS permission and audio policies still control delivery.
- The composer menu has searched submenus for authorized recent conversations, uploaded evidence and actual agent skills. Selecting evidence opens its owning conversation. No implicit cross-project file copying or native Drive connection is introduced.
- The existing Agents catalog has searchable/filterable illustrated cards, built-in/custom capabilities and custom specialist registration. **Use skill** takes a user question and an authorized conversation with evidence; it creates a graph through the existing plan/graph APIs, invokes the selected role after the evidence tool, and saves the real output/history. This read-only review does not silently create tasks or publish. Consequential tools retain existing approval enforcement. Skills here are registered role contracts, not arbitrary downloaded executable packages.
- Non-evidence graph agents now check provider configuration before inference, preventing implicit deterministic substitution when a selected remote provider lacks credentials. Explicit Evidence only remains clearly labeled and testable without keys.
- Capability graph inference honors the registered role's output-token limit as well as the remaining graph budget.
- The Integrations workspace reuses the same connector gallery and registry. Bundled cards actually register/check the MCP transport. Remote cards hand off directly to the existing server form with the service name and HTTPS transport preselected. Cards show actual saved discovery state.

The task composer already preserves the next typed message during active work. General explains this supported behavior; it does not offer an unimplemented automatic queue. Billing credits, remote desktops, advertising settings and third-party native OAuth are not fabricated from the reference.

Checks:

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend run build
python tests/e2e_reference_interactions.py
EVOLVYN_TEST_URL=http://localhost:3000 python tests/e2e_account.py
python tests/e2e_visual_workspace.py
python tests/e2e_commerce.py
python tests/e2e_studio.py
python tests/e2e_control_center.py
.venv/bin/python tests/live_exported_runtime.py
```

The browser acceptance uses synthetic sales data and explicit Evidence only, verifies exact 45.10 USD calculations in the selected-role graph, theme persistence/device changes, searched context, permission handling, custom-role persistence and mobile settings. Provider completions still require valid workspace vault routes; this change does not claim live Gemini/Groq credentials or production security certification.

Backend validation: **145 tests pass**, including personal settings isolation, strict schema/origin checks, viewer business-write denial, missing-provider failure without substitution, and the registered role's token limit. Source builds and the independent exported runtime have also passed. Desktop/mobile screenshots use only synthetic acceptance data.

Browser validation passed for the new recording-driven journey, account/team controls, e-commerce metrics/approval/outcomes, product studio/discussion memory, and MCP/graph/governance. The new journey also checks immediate discovery of freshly uploaded evidence, dark automation controls, bundled MCP connection checks and the prefilled remote server form. Remote-model acceptance still requires real vault credentials; browser notification delivery depends on the user's browser/OS permissions.

Screenshots: [profile menu](screenshots/reference-profile-menu.png), [light settings](screenshots/reference-settings-light.png), [dark settings](screenshots/reference-settings-dark.png), [nested skill picker](screenshots/reference-nested-capabilities.png), [agent catalog](screenshots/reference-agent-skills.png), [shared connector gallery](screenshots/reference-integration-gallery.png), [mobile settings](screenshots/reference-settings-mobile.png).
