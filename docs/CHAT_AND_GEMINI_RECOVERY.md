> Model setup below is historical. The current Gemini/Groq-only automatic key workflow is documented in [CLOUD_MODEL_DEFAULTS.md](CLOUD_MODEL_DEFAULTS.md).

# Product chat keyboard, queue feedback and model recovery

The reported Product Studio screenshot showed a saved provider failure, not a completed model response. A valid replacement credential does not change an explicit model identifier, environment default or per-agent override. The workspace cannot determine live account/model access from a screenshot and must not silently swap keys/providers/models.

## Operator recovery after deploying this revision

1. Open **Key vault**. Find the enabled credential saved as **Gemini**.
2. Click **Load available models**. This calls Gemini's fixed model-list endpoint using that encrypted credential in `x-goog-api-key`, filters provider-advertised `generateContent` models and returns model metadata only. Nothing is hardcoded into this list. Listing does not prove successful generation, sufficient quota or support for every agent output contract.
3. Choose **Available Gemini model**, then **Use for all agents**. This explicitly saves the selected model and key as the workspace default and resets per-agent overrides. Merely saving/replacing a key does not select another model.
4. Click **Test route** on the organization default. This performs a real bounded model request; follow any authentication, quota, unavailable-model or budget error. Never share the key in chat.
5. Return to Product Studio and send the request again. Old failed turns remain in saved history; no failure is relabeled as a successful AI reply.

Effective route details now show the resolved model, including environment/provider defaults. Existing custom route configuration remains available. A Gemini 404 gives model-specific recovery guidance; no automatic provider/model fallback was added.

## Interaction changes

- Product Studio sends on **Enter** and inserts a new line with **Shift+Enter**. Composition/IME Enter is preserved. Held/repeated Enter and a pending request cannot queue duplicate submissions.
- The user message and an explicit saving/queue status appear immediately, before product creation or the agent POST finishes. This is client-side pending state, not a claim that the server saved it or that a model responded.
- Queue failure clears pending state and restores the unsent draft without overwriting a newer typed draft. Real persisted graph/user/model outputs continue through the existing backend harness and history.
- Initial restore reuses the product/build catalog already loaded; first-message creation no longer waits for another catalog round trip before queuing the message. Visible progress does not eliminate provider latency or a sleeping Render service's cold start.
- Existing project/tenant policies, source-write approvals, backend generation boundaries and durable history remain unchanged.

## Validation

`tests/test_gemini_model_discovery.py` exercises provider-advertised inventory, explicit route selection through an actual Product Studio graph, wrong-tenant/policy denial, malformed/oversized/reflected provider data, bounded pagination and unavailable-model errors without silent switching. It uses a controlled Gemini HTTP boundary; no private live key was supplied to this workspace.

`python tests/e2e_chat_input.py` checks the actual browser/API/PostgreSQL/vault flow with controlled model/inventory boundaries: model selection, Enter/Shift+Enter, a deliberately held queue request with immediate UI feedback, deduplication, saved replies/navigation restoration, rejected-queue draft recovery and desktop/mobile composer visibility. Live cloud/provider acceptance still requires the operator's route test.

Final checks: 40 focused model/routing/product/export tests passed; chat-input/model-selection and existing full source-build/approval/restore browser journeys passed; production frontend build passed. A full regression run found one older uploaded-logo registry compatibility failure alongside 337 passes; preserving that original registry and keeping the vector Instagram mark separate fixed it, verified by both export tests in the final focused run. No live Gemini credential/cloud route was accessed or claimed tested.
