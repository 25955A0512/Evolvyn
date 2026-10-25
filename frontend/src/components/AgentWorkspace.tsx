import { AuthorizedConnections } from "./AuthorizedConnections";
import { ConnectorArt, ConnectorGallery } from "./ConnectorGallery";
import { UiIcon } from "./UiIcon";
import { useEffect, useState } from "react";
import {
  X,
  Code2,
  Users,
  Brain,
  KeyRound,
  Plug,
  Workflow,
  Plus,
  ArrowRight,
  Shield,
  PanelLeftClose,
  PanelLeftOpen,
  Check,
  Search,
} from "lucide-react";
import type { client } from "../api";
import type { Convo } from "../types";
import { type ManageConnections } from "./ToolAccess";
import { ProductStudio } from "./ProductStudio";
import { DiscussionRoom } from "./DiscussionRoom";
import { DesignCanvas } from "./DesignCanvas";
import { GrowthWorkspace } from "./GrowthWorkspace";
export type StudioTab =
  | "build"
  | "discuss"
  | "agents"
  | "memory"
  | "vault"
  | "integrations"
  | "canvas"
  | "growth"
  | "runtime";
type API = ReturnType<typeof client>;
function VaultPanel({ api }: { api: API }) {
  const [data, setData] = useState<any>(null),
    [provider, setProvider] = useState("provider"),
    [routeProvider, setRouteProvider] = useState("local"),
    [rotation, setRotation] = useState<any>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [modelCatalogs, setModelCatalogs] = useState<Record<string, any[]>>({}),
    [selectedModels, setSelectedModels] = useState<Record<string, string>>({});
  async function load() {
    setData(await api.json("/vault"));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  async function action(fn: () => Promise<void>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await load();
      setNotice(message);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="studio-page">
      <div className="studio-page-title">
        <span className="eyebrow">KEY VAULT & MODEL GATEWAY</span>
        <h1>One default. The right key for every agent.</h1>
        <p>
          Store provider credentials encrypted, choose an organization default,
          and override it for individual agents. Agents receive credentials only
          inside the model gateway.
        </p>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="studio-success" role="status">
          <Check size={15} />
          {notice}
        </p>
      )}
      {data && (
        <>
          <section className="workspace-model-default">
            <h3>Use one saved key across all agents</h3>
            <p>
              A single unassigned Gemini key becomes the workspace default
              automatically. Explicit per-agent routes remain in force until you
              choose “Use for all agents”. A new key does not change a saved
              model. If a model is unavailable, load the models returned by
              Gemini, select one and apply it here.
            </p>
            {data.credentials
              .filter((c: any) => c.enabled && c.provider !== "mcp")
              .map((c: any) => (
                <div className="default-key-choice" key={c.id}>
                  <strong>
                    {c.name} · {c.provider}
                  </strong>
                  {c.provider === "gemini" && (
                    <>
                      <button
                        disabled={busy}
                        onClick={() =>
                          action(async () => {
                            const result = await api.json(
                              "/vault/credentials/" + c.id + "/models",
                              { method: "POST" },
                            );
                            setModelCatalogs((rows) => ({
                              ...rows,
                              [c.id]: result.models,
                            }));
                            if (!result.models.length)
                              throw Error(
                                "Gemini returned no generateContent models for this key.",
                              );
                          }, "Models loaded from Gemini. Select a model, then use it for all agents and test the route.")
                        }
                      >
                        Load available models
                      </button>
                      {modelCatalogs[c.id] && (
                        <label>
                          Available Gemini model
                          <select
                            aria-label={"Available Gemini model: " + c.name}
                            value={selectedModels[c.id] || ""}
                            onChange={(e) =>
                              setSelectedModels((rows) => ({
                                ...rows,
                                [c.id]: e.target.value,
                              }))
                            }
                          >
                            <option value="">
                              Choose a provider-listed model
                            </option>
                            {modelCatalogs[c.id].map((m) => (
                              <option key={m.id} value={m.id}>
                                {m.id}
                              </option>
                            ))}
                          </select>
                        </label>
                      )}
                    </>
                  )}
                  <button
                    disabled={busy}
                    onClick={() =>
                      action(async () => {
                        await api.json("/vault/workspace-default", {
                          method: "PUT",
                          body: JSON.stringify({
                            provider: c.provider,
                            credential_id: c.id,
                            reset_agent_overrides: true,
                            ...(selectedModels[c.id]
                              ? { model: selectedModels[c.id] }
                              : {}),
                          }),
                        });
                      }, "Workspace default saved. All agents now inherit this key.")
                    }
                  >
                    Use for all agents
                  </button>
                </div>
              ))}
            <details>
              <summary>Effective route for every agent</summary>
              {Object.entries(data.effective_routes || {}).map(
                ([agent, route]: [string, any]) => (
                  <p key={agent}>
                    {data.agents[agent]}: {route.provider} ·{" "}
                    {route.resolved_model || "no model"}
                    {route.inferred
                      ? " · saved key selected automatically"
                      : ""}
                  </p>
                ),
              )}
            </details>
          </section>
          <div className="vault-security">
            <Shield size={20} />
            <div>
              <strong>
                {data.ready
                  ? "Vault encryption ready"
                  : "Master key is not provisioned"}
              </strong>
              <p>
                Keys are never returned after saving. The encryption key is held
                separately from PostgreSQL. Revoke or replace a credential
                without putting its value in a prompt.
              </p>
            </div>
          </div>
          <div className="studio-two-columns">
            <form
              className="studio-card studio-form"
              onSubmit={(e) => {
                e.preventDefault();
                const form = e.currentTarget;
                const d = Object.fromEntries(new FormData(form));
                action(
                  async () => {
                    try {
                      await api.json(
                        "/vault/credentials" +
                          (rotation ? "/" + rotation.id : ""),
                        {
                          method: rotation ? "PUT" : "POST",
                          body: JSON.stringify({
                            name: d.name,
                            provider,
                            value: d.value,
                          }),
                        },
                      );
                      setRotation(null);
                    } finally {
                      form.reset();
                    }
                  },
                  rotation
                    ? "Credential replaced; existing bindings retained"
                    : "Credential encrypted and stored",
                );
              }}
            >
              <h3>
                <KeyRound size={17} />
                {rotation ? "Replace credential" : "Add a credential"}
              </h3>
              <label>
                Credential name
                <input
                  key={rotation?.id || "new"}
                  name="name"
                  defaultValue={rotation?.name || ""}
                  required
                  maxLength={100}
                  placeholder="Production model provider"
                />
              </label>
              <label>
                Provider
                <select
                  aria-label="Credential provider"
                  value={provider}
                  disabled={!!rotation}
                  onChange={(e) => setProvider(e.target.value)}
                >
                  <option value="provider">OpenAI</option>
                  <option value="groq">Groq</option>
                  <option value="gemini">Gemini</option>
                  <option value="openrouter">OpenRouter</option>
                  <option value="mcp">MCP server bearer token</option>
                </select>
              </label>
              <div
                className="provider-choice-preview"
                aria-label="Selected credential provider"
              >
                <ConnectorArt name={provider} size={26} />
                <div>
                  <strong>
                    {
                      (
                        {
                          provider: "OpenAI",
                          groq: "Groq",
                          gemini: "Gemini",
                          openrouter: "OpenRouter",
                          mcp: "MCP server",
                        } as Record<string, string>
                      )[provider]
                    }
                  </strong>
                  <small>
                    Credential stays encrypted in your workspace vault
                  </small>
                </div>
              </div>
              <label>
                Secret value
                <input
                  aria-label="Secret value"
                  name="value"
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  maxLength={8192}
                />
              </label>
              <button className="studio-primary" disabled={busy || !data.ready}>
                {rotation ? "Replace encrypted key" : "Save encrypted key"}
              </button>
              {rotation && (
                <button type="button" onClick={() => setRotation(null)}>
                  Cancel replacement
                </button>
              )}
            </form>
            <form
              className="studio-card studio-form"
              onSubmit={(e) => {
                e.preventDefault();
                const d = Object.fromEntries(new FormData(e.currentTarget));
                action(async () => {
                  await api.json("/vault/bindings/" + d.agent, {
                    method: "PUT",
                    body: JSON.stringify({
                      provider: routeProvider,
                      credential_id: d.credential_id || null,
                      model: d.model || "",
                    }),
                  });
                }, "Model route saved");
              }}
            >
              <h3>
                <Workflow size={17} />
                Configure a model route
              </h3>
              <label>
                Agent
                <select name="agent" aria-label="Model route agent">
                  <option value="default">
                    Organization default · inherited by every agent
                  </option>
                  {Object.entries(data.agents).map(
                    ([id, name]: [string, any]) => (
                      <option key={id} value={id}>
                        {name}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label>
                Model provider
                <select
                  aria-label="Route provider"
                  value={routeProvider}
                  onChange={(e) => setRouteProvider(e.target.value)}
                >
                  <option value="local">Local AI · no key</option>
                  <option value="evidence">Deterministic evidence</option>
                  <option value="provider">OpenAI</option>
                  <option value="groq">Groq</option>
                  <option value="gemini">Gemini</option>
                  <option value="openrouter">OpenRouter</option>
                </select>
              </label>
              <label>
                Stored credential
                <select
                  name="credential_id"
                  key={routeProvider}
                  aria-label="Route credential"
                  required={!["local", "evidence"].includes(routeProvider)}
                  disabled={["local", "evidence"].includes(routeProvider)}
                >
                  <option value="">
                    {["local", "evidence"].includes(routeProvider)
                      ? "No credential required"
                      : "Choose an encrypted credential"}
                  </option>
                  {data.credentials
                    .filter(
                      (c: any) => c.enabled && c.provider === routeProvider,
                    )
                    .map((c: any) => (
                      <option key={c.id} value={c.id}>
                        {c.name} · version {c.version}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Model identifier
                <input
                  name="model"
                  maxLength={150}
                  placeholder="Leave blank for the provider default"
                />
              </label>
              <button className="studio-primary" disabled={busy}>
                Save model route
              </button>
            </form>
          </div>
          <h3 className="studio-subtitle">Stored credentials</h3>
          <div className="credential-grid">
            {!data.credentials.length && (
              <div className="studio-card muted">
                No API keys stored. Local AI and deterministic mode remain
                available.
              </div>
            )}
            {data.credentials.map((c: any) => (
              <article className="studio-card credential-card" key={c.id}>
                <div className="studio-card-heading">
                  <KeyRound size={18} />
                  <strong>{c.name}</strong>
                  <span className="status-pill">
                    {c.enabled ? "Encrypted" : "Revoked"}
                  </span>
                </div>
                <p>
                  {c.provider} · version {c.version}
                </p>
                <small>Reference: {c.id}</small>
                <div className="studio-actions">
                  <button
                    disabled={busy}
                    onClick={() => {
                      setRotation(c);
                      setProvider(c.provider);
                    }}
                  >
                    Replace
                  </button>
                  {c.enabled && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        action(async () => {
                          await api.json("/vault/credentials/" + c.id, {
                            method: "DELETE",
                          });
                        }, "Credential revoked and ciphertext removed")
                      }
                    >
                      Revoke
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
          <h3 className="studio-subtitle">Active routing policy</h3>
          {!data.bindings.length && (
            <div className="studio-card muted">
              No override configured. Agents use the local default or the
              explicitly selected analysis mode.
            </div>
          )}
          {data.bindings.map((r: any) => (
            <div className="studio-route" key={r.id}>
              <ConnectorArt name={r.provider} size={22} />
              <div>
                <strong>
                  {r.agent === "default"
                    ? "Organization default"
                    : data.agents[r.agent] || r.agent}
                </strong>
                <small>
                  {r.provider} · {r.model || "provider default"} ·{" "}
                  {r.credential_id ? "vault credential" : "no key"}
                </small>
              </div>
              <button
                disabled={busy}
                onClick={() =>
                  action(async () => {
                    const result = await api.json(
                      "/agents/" + r.agent + "/test",
                      { method: "POST" },
                    );
                    if (!result.available) throw Error(result.reason);
                  }, "Model route responded successfully")
                }
              >
                Test route
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  action(async () => {
                    await api.json("/vault/bindings/" + r.agent, {
                      method: "DELETE",
                    });
                  }, "Route removed; agent inherits the default")
                }
              >
                Remove override
              </button>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
function MemoryPanel({
  api,
  projectId,
  conversation,
}: {
  api: API;
  projectId: string;
  conversation: Convo | null;
}) {
  const [rows, setRows] = useState<any[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [query, setQuery] = useState(""),
    [recalled, setRecalled] = useState<any[] | null>(null);
  async function load() {
    setRows(await api.json("/memory"));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  async function action(fn: () => Promise<void>) {
    setError("");
    setBusy(true);
    try {
      await fn();
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="studio-page">
      <div className="studio-page-title">
        <span className="eyebrow">AGENTIC MEMORY</span>
        <h1>Remember decisions. Keep their context.</h1>
        <p>
          Reviewed facts, preferences, decisions and lessons persist across
          sessions. Scope, provenance and retention are checked whenever an
          agent recalls them.
        </p>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="studio-two-columns">
        <form
          className="studio-card studio-form"
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const d = Object.fromEntries(new FormData(form));
            action(async () => {
              await api.json("/memory", {
                method: "POST",
                body: JSON.stringify({
                  text: d.text,
                  category: d.category,
                  retention_days: Number(d.retention_days),
                  project_id: projectId || null,
                  conversation: conversation?.id || null,
                  source_ids: String(d.sources || "")
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                }),
              });
              form.reset();
            });
          }}
        >
          <h3>
            <Brain size={18} />
            Propose a memory
          </h3>
          <label>
            Type
            <select name="category">
              <option value="decision">Decision</option>
              <option value="preference">Preference</option>
              <option value="fact">Source-linked fact</option>
              <option value="lesson">Lesson learned</option>
              <option value="market_observation">Market observation</option>
            </select>
          </label>
          <label>
            Memory
            <textarea
              name="text"
              required
              minLength={3}
              maxLength={4000}
              placeholder="A decision or preference agents should consider next time…"
            />
          </label>
          <label>
            Source record IDs
            <input
              name="sources"
              placeholder="Optional comma-separated document or execution IDs"
            />
          </label>
          <label>
            Retention (days)
            <input
              name="retention_days"
              type="number"
              min={1}
              max={3650}
              defaultValue={90}
            />
          </label>
          <small>
            Scope:{" "}
            {projectId
              ? "selected project"
              : conversation?.project_id
                ? "conversation project"
                : "organization-level conversations"}
            . New memories require review before recall.
          </small>
          <button className="studio-primary" disabled={busy}>
            Submit for memory review
          </button>
        </form>
        <div>
          <form
            className="studio-card studio-form"
            onSubmit={(e) => {
              e.preventDefault();
              action(async () =>
                setRecalled(
                  await api.json(
                    "/memory/recall?q=" +
                      encodeURIComponent(query) +
                      (projectId ? "&project_id=" + projectId : ""),
                  ),
                ),
              );
            }}
          >
            <h3>Inspect what an agent would recall</h3>
            <label>
              Memory query
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                maxLength={2000}
              />
            </label>
            <button disabled={busy}>
              <Search size={14} />
              Recall reviewed memory
            </button>
            <small>
              Retrieval uses lexical overlap with scope and retention filters.
            </small>
          </form>
          {recalled && (
            <div className="studio-card">
              <h3>{recalled.length} matching memories</h3>
              {recalled.map((m) => (
                <p key={m.id}>{m.text}</p>
              ))}
            </div>
          )}
          <div className="studio-card memory-safeguards">
            <Shield size={22} />
            <h3>Memory cannot authorize an action.</h3>
            <p>
              Source text and agent summaries remain untrusted input. Tool
              policy and human approval are evaluated separately. Forgetting a
              memory removes its stored content; related source records have
              their own retention.
            </p>
          </div>
        </div>
      </div>
      <h3 className="studio-subtitle">Memory review queue and history</h3>
      {rows.map((m) => (
        <article className="studio-card memory-entry" key={m.id}>
          <div className="studio-card-heading">
            <strong>{m.category.replaceAll("_", " ")}</strong>
            <span className="status-pill">{m.state}</span>
          </div>
          <p>{m.text}</p>
          <small>
            {m.provenance} · Expires{" "}
            {new Date(m.expires_at).toLocaleDateString(undefined, {
              timeZone: "Asia/Calcutta",
            })}
          </small>
          <div className="studio-actions">
            {m.state === "DRAFT" && (
              <>
                <button
                  disabled={busy}
                  onClick={() =>
                    action(async () => {
                      await api.json("/memory/" + m.id + "/decision", {
                        method: "POST",
                        body: JSON.stringify({ accept: true }),
                      });
                    })
                  }
                >
                  Accept memory
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    action(async () => {
                      await api.json("/memory/" + m.id + "/decision", {
                        method: "POST",
                        body: JSON.stringify({ accept: false }),
                      });
                    })
                  }
                >
                  Reject
                </button>
              </>
            )}
            <button
              disabled={busy}
              onClick={() =>
                action(async () => {
                  await api.json("/memory/" + m.id, { method: "DELETE" });
                })
              }
            >
              Forget
            </button>
          </div>
        </article>
      ))}
    </div>
  );
}
function AgentCatalog({
  api,
  conversation,
  projectId,
  businessId,
  initialAgent,
  onNavigate,
}: {
  api: API;
  conversation: Convo | null;
  projectId: string;
  businessId: string;
  initialAgent?: string;
  onNavigate?: (id: string) => void;
}) {
  const [rows, setRows] = useState<any[]>([]),
    [error, setError] = useState(""),
    [search, setSearch] = useState(""),
    [category, setCategory] = useState("All"),
    [chosen, setChosen] = useState(initialAgent || ""),
    [creating, setCreating] = useState(false),
    [goal, setGoal] = useState(""),
    [route, setRoute] = useState("default"),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [convos, setConvos] = useState<any[]>([]),
    [convId, setConvId] = useState(conversation?.id || "");
  async function load() {
    const [agents, conversations] = await Promise.all([
      api.json("/agents"),
      api.json("/conversations"),
    ]);
    setRows(agents);
    setConvos(conversations);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  const group = (a: any) =>
    !a.builtin
      ? "Custom"
      : ["architect", "developer", "reviewer"].includes(a.agent)
        ? "Development"
        : "Business";
  const selected = rows.find((a) => a.agent === chosen),
    context = convos.find((c) => c.id === convId);
  return (
    <div className="studio-page">
      <div className="studio-page-title">
        <span className="eyebrow">COMPOSABLE AGENTS / SKILLS</span>
        <h1>Specialists with a shared purpose.</h1>
        <p>
          Distinct role contracts, model routes and capability boundaries.
          Compose specialists into execution graphs in the Agent control center.
        </p>
      </div>
      <div className="capability-toolbar">
        <label>
          <UiIcon name="search" />
          <input
            aria-label="Search agent capabilities"
            placeholder="Search skills, roles and tools"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <button onClick={() => setCreating(!creating)}>
          <Plus size={17} />
          Create specialist
        </button>
      </div>
      <div className="connector-filters">
        {["All", "Business", "Development", "Custom"].map((c) => (
          <button
            key={c}
            className={category === c ? "selected" : ""}
            onClick={() => setCategory(c)}
          >
            {c}
          </button>
        ))}
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {selected && (
        <form
          className="studio-card capability-run-form"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const planned = await api.json("/harness/plan", {
                method: "POST",
                body: JSON.stringify({
                  conversation_id: convId,
                  goal,
                  mode: route,
                }),
              });
              const definition = {
                ...planned.definition,
                name: (selected.name + " · " + goal).slice(0, 100),
                nodes: [
                  ...planned.definition.nodes
                    .filter((n: any) => ["evidence", "explain"].includes(n.id))
                    .map((n: any) =>
                      n.id === "explain"
                        ? { ...n, agent_id: selected.agent }
                        : n,
                    ),
                  {
                    id: "result",
                    type: "result",
                    arguments: { value: { $ref: "nodes.explain.output" } },
                  },
                ],
                edges: [
                  { source: "evidence", target: "explain" },
                  { source: "explain", target: "result" },
                ],
              };
              const graph = await api.json("/harness/graphs", {
                method: "POST",
                body: JSON.stringify(definition),
              });
              const run = await api.json(
                "/harness/graphs/" + graph.id + "/run",
                {
                  method: "POST",
                  body: JSON.stringify({ conversation_id: convId }),
                },
              );
              setNotice(
                "Execution " + run.id + " queued through the shared harness.",
              );
              onNavigate?.(convId);
            } catch (e: any) {
              setError(e.message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="studio-card-heading">
            <h3>Use {selected.name}</h3>
            <button type="button" onClick={() => setChosen("")}>
              Close
            </button>
          </div>
          <label>
            Evidence conversation
            <select
              aria-label="Capability conversation"
              value={convId}
              required
              onChange={(e) => setConvId(e.target.value)}
            >
              <option value="">Choose conversation</option>
              {convos
                .filter(
                  (c) =>
                    c.project_id === (projectId || null) &&
                    (!businessId || c.business_id === businessId),
                )
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Your question
            <textarea
              aria-label="Capability question"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              minLength={3}
              maxLength={2000}
              required
            />
          </label>
          <label>
            Model route
            <select
              aria-label="Capability model route"
              value={route}
              onChange={(e) => setRoute(e.target.value)}
            >
              <option value="default">Workspace vault / per-agent route</option>
              <option value="local">Local model</option>
              <option value="evidence">
                Explicit evidence only · no model
              </option>
            </select>
          </label>
          <p>
            Reads authorized evidence, then invokes this role through the
            existing bounded graph. It does not publish, spend or grant tool
            approvals.
          </p>
          {!context?.files.length && (
            <p>
              Upload evidence in the selected conversation before running this
              capability.
            </p>
          )}
          <button
            className="studio-primary"
            disabled={busy || !context?.files.length}
          >
            Run capability
          </button>
        </form>
      )}
      <div className="agent-catalog">
        {rows
          .filter(
            (a) =>
              (category === "All" || group(a) === category) &&
              (a.name + " " + a.goal + " " + a.allowed_tools.join(" "))
                .toLowerCase()
                .includes(search.toLowerCase()),
          )
          .map((a) => (
            <article className="studio-card" key={a.agent}>
              <div
                className={"capability-cover cover-" + group(a).toLowerCase()}
                aria-hidden="true"
              >
                <UiIcon
                  name={
                    group(a) === "Development"
                      ? "code"
                      : a.agent === "marketing_analyst"
                        ? "chart-line"
                        : "brain"
                  }
                  size={38}
                />
                <span>{group(a)}</span>
              </div>
              <h3>{a.name}</h3>
              <p>{a.goal}</p>
              <div className="agent-catalog-meta">
                <span>{a.builtin ? "Built-in role" : "Custom role"}</span>
                <span>
                  {a.route.provider} ·{" "}
                  {a.route.agent === "default"
                    ? "default route"
                    : "agent override"}
                </span>
                <span>{a.output_tokens} output-token limit</span>
              </div>
              {!!a.allowed_tools?.length && (
                <small>Capabilities: {a.allowed_tools.join(", ")}</small>
              )}
              <button
                className="capability-use"
                onClick={() => {
                  setChosen(a.agent);
                  setNotice("");
                  document
                    .querySelector(".studio-scroll")
                    ?.scrollTo({ top: 0, behavior: "smooth" });
                }}
              >
                Use skill <ArrowRight size={15} />
              </button>
            </article>
          ))}
      </div>
      <form
        className="studio-card studio-form custom-agent-form"
        hidden={!creating}
        onSubmit={async (e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const d = Object.fromEntries(new FormData(form));
          try {
            await api.json("/agents", {
              method: "POST",
              body: JSON.stringify({
                agent: d.agent,
                name: d.name,
                goal: d.goal,
                allowed_tools: String(d.allowed_tools || "")
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
                output_tokens: 384,
              }),
            });
            form.reset();
            await load();
            setCreating(false);
            setNotice("Specialist registered in the shared agent catalog.");
          } catch (e: any) {
            setError(e.message);
          }
        }}
      >
        <h3>Create a scoped specialist</h3>
        <label>
          Agent identifier
          <input
            name="agent"
            pattern="[a-z][a-z0-9_]{2,59}"
            required
            placeholder="customer_success"
          />
        </label>
        <label>
          Display name
          <input name="name" minLength={3} required />
        </label>
        <label>
          Role contract
          <textarea name="goal" required minLength={10} maxLength={2000} />
        </label>
        <label>
          Allowed registered tools
          <input
            name="allowed_tools"
            placeholder="analyze_business, prioritize_actions"
          />
        </label>
        <button className="studio-primary">Register specialist</button>
      </form>
    </div>
  );
}
function Integrations({
  api,
  onManage,
}: {
  api: API;
  onManage: ManageConnections;
}) {
  const [servers, setServers] = useState<any[]>([]),
    [tools, setTools] = useState<any[]>([]),
    [query, setQuery] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  async function load() {
    const [a, b] = await Promise.all([
      api.json("/mcp/servers"),
      api.json("/tool-registry"),
    ]);
    setServers(a);
    setTools(b);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  return (
    <div className="studio-page">
      <div className="studio-page-title">
        <span className="eyebrow">INTEGRATIONS & CAPABILITIES</span>
        <div className="studio-card-heading">
          <h1>Connect the context that matters.</h1>
          <button onClick={() => onManage()}>
            Manage MCP connections <ArrowRight size={14} />
          </button>
        </div>
        <p>
          Bring authorized CRM exports, feedback and tools into your workflows.
          Connected servers and their actual discovery results appear here.
        </p>
      </div>
      {error && <p className="error">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <ConnectorGallery
        servers={servers}
        busy={busy}
        onConfigure={(name) => onManage("servers", name)}
        onBundled={async (name, profile) => {
          if (busy) return;
          setBusy(true);
          setError("");
          setNotice("");
          try {
            const row =
              servers.find((s) => s.profile === profile) ||
              (await api.json("/mcp/servers", {
                method: "POST",
                body: JSON.stringify({ name, profile, transport: "stdio" }),
              }));
            await api.json("/mcp/servers/" + row.id + "/probe", {
              method: "POST",
            });
            await load();
            setNotice(
              "Connection checked. The card shows its actual discovery status.",
            );
          } catch (e: any) {
            setError(e.message);
          } finally {
            setBusy(false);
          }
        }}
      />
      <h3 className="studio-subtitle">Your registered connections & tools</h3>
      <label className="integration-search">
        <Search size={18} />
        <input
          aria-label="Search integrations"
          placeholder="Search connections and capabilities"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </label>
      <div className="studio-two-columns">
        {servers
          .filter((s) =>
            (s.name + " " + s.profile + " " + s.url)
              .toLowerCase()
              .includes(query.toLowerCase()),
          )
          .map((s) => (
            <article className="studio-card integration-tile" key={s.id}>
              <span className="studio-icon">
                <ConnectorArt name={s.name} />
              </span>
              <div>
                <h3>{s.name}</h3>
                <p>{s.transport === "stdio" ? "Bundled MCP profile" : s.url}</p>
                <small>{s.tools?.length || 0} discovered capabilities</small>
              </div>
              <span className="status-pill">
                {!s.enabled ? "disabled" : s.status}
              </span>
            </article>
          ))}
        <article className="studio-card integration-tile">
          <span className="studio-icon">
            <FileTextIcon />
          </span>
          <div>
            <h3>CRM and customer feedback uploads</h3>
            <p>TXT, CSV, PDF and DOCX evidence with source attribution</p>
            <small>Available · add files to a conversation</small>
          </div>
        </article>
        <article className="studio-card integration-tile">
          <span className="studio-icon">
            <Plus size={20} />
          </span>
          <div>
            <h3>Your MCP integration</h3>
            <p>Connect a CRM, social feedback or research server</p>
            <button onClick={() => onManage()}>Configure connection</button>
          </div>
        </article>
      </div>
      <h3 className="studio-subtitle">Discovered tool registry</h3>
      <div className="capability-list">
        {tools
          .filter((t) =>
            (t.name + " " + t.description)
              .toLowerCase()
              .includes(query.toLowerCase()),
          )
          .map((t) => (
            <div key={t.name}>
              <Workflow size={16} />
              <div>
                <strong>{t.name}</strong>
                <p>{t.description}</p>
              </div>
              <span className="status-pill">{t.risk}</span>
            </div>
          ))}
      </div>
    </div>
  );
}
function FileTextIcon() {
  return <span style={{ fontSize: 16 }}>↥</span>;
}
export function AgentWorkspace({
  api,
  initialTab,
  initialAgent,
  onSettings,
  conversation,
  projectId,
  businessId,
  onClose,
  onRefresh,
  onManage,
  onNavigate,
  onTabChange,
}: {
  api: API;
  initialTab: StudioTab;
  onTabChange?: (tab: StudioTab) => void;
  initialAgent?: string;
  onSettings?: () => void;
  onNavigate?: (id: string) => void;
  conversation: Convo | null;
  projectId: string;
  businessId: string;
  onClose: () => void;
  onRefresh: () => void;
  onManage: ManageConnections;
}) {
  const [navHidden, setNavHidden] = useState(
    () =>
      sessionStorage.getItem("evolvyn-studio-nav") === "hidden" ||
      (innerWidth < 650 &&
        sessionStorage.getItem("evolvyn-studio-nav") !== "shown"),
  );
  const [advancedOpen, setAdvancedOpen] = useState(
    () =>
      sessionStorage.getItem("evolvyn-studio-tools") === "open" ||
      !["build", "growth", "discuss", "canvas"].includes(initialTab),
  );
  const [tab, setTabState] = useState<StudioTab>(initialTab);
  function setTab(value: StudioTab) {
    setTabState(value);
    onTabChange?.(value);
  }
  useEffect(() => {
    setTabState(initialTab);
    if (!["build", "growth", "discuss", "canvas"].includes(initialTab))
      setAdvancedOpen(true);
  }, [initialTab]);
  const tabs = [
    { id: "build", name: "Build a product", icon: Code2 },
    { id: "growth", name: "Growth insights", icon: Brain },
    { id: "canvas", name: "Canvas", icon: Workflow },
    { id: "runtime", name: "Shared runtime", icon: Shield },
    { id: "discuss", name: "Discussion room", icon: Users },
    { id: "agents", name: "Agents", icon: Workflow },
    { id: "memory", name: "Agent memory", icon: Brain },
    { id: "vault", name: "Key vault", icon: KeyRound },
    { id: "integrations", name: "Integrations", icon: Plug },
  ] as const;
  return (
    <div
      className={"agent-workspace" + (navHidden ? " studio-nav-hidden" : "")}
      role="dialog"
      aria-modal="true"
      aria-labelledby="agent-workspace-heading"
    >
      <aside className="studio-sidebar">
        <div className="studio-brand">
          <span className="mark">e</span>
          <strong id="agent-workspace-heading">
            evolvyn<span>Business & product studio</span>
          </strong>
        </div>
        <nav aria-label="Studio modules">
          {tabs
            .filter((t) =>
              ["build", "growth", "discuss", "canvas"].includes(t.id),
            )
            .map((t) => (
              <button
                className={tab === t.id ? "selected" : ""}
                key={t.id}
                onClick={() => setTab(t.id)}
              >
                <UiIcon
                  name={
                    t.id === "build"
                      ? "code"
                      : t.id === "growth"
                        ? "chart-line"
                        : t.id === "discuss"
                          ? "users"
                          : "automation"
                  }
                />
                {t.name}
              </button>
            ))}
          <details
            className="studio-advanced-nav"
            open={advancedOpen}
            onToggle={(e) => {
              setAdvancedOpen(e.currentTarget.open);
              sessionStorage.setItem(
                "evolvyn-studio-tools",
                e.currentTarget.open ? "open" : "closed",
              );
            }}
          >
            <summary>Workspace tools</summary>
            <div className="studio-advanced-links">
              {tabs
                .filter(
                  (t) =>
                    !["build", "growth", "discuss", "canvas"].includes(t.id),
                )
                .map((t) => (
                  <button
                    className={tab === t.id ? "selected" : ""}
                    key={t.id}
                    onClick={() => setTab(t.id)}
                  >
                    <UiIcon
                      name={
                        t.id === "vault"
                          ? "key"
                          : t.id === "memory"
                            ? "brain"
                            : t.id === "integrations"
                              ? "plug-connected"
                              : t.id === "runtime"
                                ? "shield-check"
                                : "git-branch"
                      }
                    />
                    {t.name}
                  </button>
                ))}
            </div>
          </details>
        </nav>
        <div className="studio-sidebar-bottom">
          <Shield size={18} />
          <p>
            Private by scope.
            <br />
            Governed by design.
          </p>
          <button onClick={() => onManage()}>
            Agent control center <ArrowRight size={13} />
          </button>
          {onSettings && (
            <button onClick={onSettings}>
              <UiIcon name="layout-dashboard" size={16} />
              Workspace settings
            </button>
          )}
        </div>
      </aside>
      <main className="studio-content">
        <header className="studio-topbar">
          <div>
            <button
              aria-label={
                navHidden ? "Show studio navigation" : "Hide studio navigation"
              }
              onClick={() => {
                sessionStorage.setItem(
                  "evolvyn-studio-nav",
                  navHidden ? "shown" : "hidden",
                );
                setNavHidden(!navHidden);
              }}
            >
              {navHidden ? (
                <PanelLeftOpen size={20} />
              ) : (
                <PanelLeftClose size={20} />
              )}
            </button>
            <span>{tabs.find((t) => t.id === tab)?.name}</span>
          </div>
          <div>
            <span className="studio-private">
              <span className="live-dot" />
              Private workspace
            </span>
            <button aria-label="Close studio" onClick={onClose}>
              <X size={19} />
            </button>
          </div>
        </header>
        <div className="studio-scroll">
          {tab === "canvas" && (
            <DesignCanvas
              onNavigate={onNavigate}
              api={api}
              projectId={projectId}
              conversation={conversation}
            />
          )}
          {tab === "growth" && (
            <GrowthWorkspace
              onManage={onManage}
              api={api}
              projectId={projectId}
              businessId={businessId}
              conversation={conversation}
            />
          )}
          {tab === "runtime" && (
            <RuntimePanel api={api} onTab={setTab} onManage={onManage} />
          )}
          {tab === "build" && (
            <ProductStudio
              api={api}
              projectId={projectId}
              onManage={onManage}
            />
          )}{" "}
          {tab === "discuss" && (
            <DiscussionRoom
              onManage={onManage}
              api={api}
              conversation={conversation}
              projectId={projectId}
              businessId={businessId}
              onRefresh={onRefresh}
            />
          )}{" "}
          {tab === "agents" && (
            <AgentCatalog
              api={api}
              conversation={conversation}
              projectId={projectId}
              businessId={businessId}
              initialAgent={initialAgent}
              onNavigate={onNavigate}
            />
          )}{" "}
          {tab === "memory" && (
            <MemoryPanel
              api={api}
              projectId={projectId}
              conversation={conversation}
            />
          )}{" "}
          {tab === "vault" && <VaultPanel api={api} />}{" "}
          {tab === "integrations" && (
            <>
              <AuthorizedConnections api={api} />
              <Integrations api={api} onManage={onManage} />
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function RuntimePanel({
  api,
  onTab,
  onManage,
}: {
  api: API;
  onTab: (tab: StudioTab) => void;
  onManage: ManageConnections;
}) {
  const [runtime, setRuntime] = useState<any>(null),
    [catalog, setCatalog] = useState<any>(null),
    [entity, setEntity] = useState(""),
    [action, setAction] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api.json("/runtime"), api.json("/runtime/ontology")])
      .then(([a, b]) => {
        setRuntime(a);
        setCatalog(b);
      })
      .catch((e) => setError(e.message));
  }, []);
  const tabs: Record<string, StudioTab> = {
    specialists: "discuss",
    models: "vault",
    memory: "memory",
    canvas: "canvas",
    growth: "growth",
  };
  return (
    <div className="studio-page">
      <div className="studio-page-title">
        <span className="eyebrow">ONE SHARED EXECUTION SYSTEM</span>
        <h1>A connected runtime for every product.</h1>
        <p>
          The builder, growth review and canvas use these same services. Product
          source exports include this complete runtime in an isolated
          deployment, with fresh accounts, policies and credentials.
        </p>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="studio-two-columns">
        {runtime?.components.map((c: any) => (
          <button
            className="studio-card runtime-component"
            key={c.id}
            onClick={() => (tabs[c.id] ? onTab(tabs[c.id]) : onManage())}
          >
            <Shield size={22} />
            <strong>{c.name}</strong>
            <span>Open configuration →</span>
          </button>
        ))}
      </div>
      <h2>Discover tools by ontology</h2>
      <div className="canvas-toolbar">
        <label>
          Entity
          <select
            aria-label="Ontology entity"
            value={entity}
            onChange={(e) => setEntity(e.target.value)}
          >
            <option value="">All entities</option>
            {Array.from(
              new Set<string>(
                catalog?.tools.flatMap((t: any) => t.ontology.entities) || [],
              ),
            )
              .sort()
              .map((e) => (
                <option key={e}>{e}</option>
              ))}
          </select>
        </label>
        <label>
          Action
          <select
            aria-label="Ontology action"
            value={action}
            onChange={(e) => setAction(e.target.value)}
          >
            <option value="">All actions</option>
            {Array.from(
              new Set<string>(
                catalog?.tools.flatMap((t: any) => t.ontology.actions) || [],
              ),
            )
              .sort()
              .map((e) => (
                <option key={e}>{e}</option>
              ))}
          </select>
        </label>
      </div>
      <div className="capability-list">
        {catalog?.tools
          .filter(
            (t: any) =>
              (!entity || t.ontology.entities.includes(entity)) &&
              (!action || t.ontology.actions.includes(action)),
          )
          .map((t: any) => (
            <details className="studio-card" key={t.name}>
              <summary>
                {t.name} · {t.risk}
              </summary>
              <p>{t.description}</p>
              <p>
                Entities: {t.ontology.entities.join(", ")} · Actions:{" "}
                {t.ontology.actions.join(", ")}
              </p>
              <pre>{JSON.stringify(t.ontology.input_contract, null, 2)}</pre>
              <p>
                Adapter: {t.adapter} · Permission: {t.permission}
              </p>
            </details>
          ))}
      </div>
    </div>
  );
}
