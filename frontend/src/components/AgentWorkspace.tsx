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
    [notice, setNotice] = useState("");
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
              <Workflow size={16} />
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
function AgentCatalog({ api }: { api: API }) {
  const [rows, setRows] = useState<any[]>([]),
    [error, setError] = useState("");
  async function load() {
    setRows(await api.json("/agents"));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  return (
    <div className="studio-page">
      <div className="studio-page-title">
        <span className="eyebrow">COMPOSABLE AGENTS</span>
        <h1>Specialists with a shared purpose.</h1>
        <p>
          Distinct role contracts, model routes and capability boundaries.
          Compose specialists into execution graphs in the Agent control center.
        </p>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="agent-catalog">
        {rows.map((a) => (
          <article className="studio-card" key={a.agent}>
            <span className="studio-icon">
              <Users size={19} />
            </span>
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
          </article>
        ))}
      </div>
      <form
        className="studio-card studio-form custom-agent-form"
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
    [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api.json("/mcp/servers"), api.json("/tool-registry")])
      .then(([a, b]) => {
        setServers(a);
        setTools(b);
      })
      .catch((e) => setError(e.message));
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
                <Plug size={21} />
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
  conversation,
  projectId,
  businessId,
  onClose,
  onRefresh,
  onManage,
}: {
  api: API;
  initialTab: StudioTab;
  conversation: Convo | null;
  projectId: string;
  businessId: string;
  onClose: () => void;
  onRefresh: () => void;
  onManage: ManageConnections;
}) {
  const [tab, setTab] = useState<StudioTab>(initialTab);
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
      className="agent-workspace"
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
        <nav>
          {tabs.map((t) => (
            <button
              className={tab === t.id ? "selected" : ""}
              key={t.id}
              onClick={() => setTab(t.id)}
            >
              <t.icon size={18} />
              {t.name}
            </button>
          ))}
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
        </div>
      </aside>
      <main className="studio-content">
        <header className="studio-topbar">
          <span>{tabs.find((t) => t.id === tab)?.name}</span>
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
          {tab === "agents" && <AgentCatalog api={api} />}{" "}
          {tab === "memory" && (
            <MemoryPanel
              api={api}
              projectId={projectId}
              conversation={conversation}
            />
          )}{" "}
          {tab === "vault" && <VaultPanel api={api} />}{" "}
          {tab === "integrations" && (
            <Integrations api={api} onManage={onManage} />
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
