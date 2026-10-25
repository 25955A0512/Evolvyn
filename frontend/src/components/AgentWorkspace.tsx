import { ConnectionsDashboard as Integrations } from "./ConnectionsDashboard";
import { KeyVaultPanel as VaultPanel } from "./KeyVaultPanel";
import "../dashboard-refresh.css";
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
import { GrowthWorkspace } from "./GrowthWorkspace";
export type StudioTab =
  | "build"
  | "discuss"
  | "agents"
  | "memory"
  | "vault"
  | "integrations"
  | "growth"
  | "runtime";
type API = ReturnType<typeof client>;
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
              <option value="default">Workspace key</option>
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
      !["build", "growth", "discuss"].includes(initialTab),
  );
  const [tab, setTabState] = useState<StudioTab>(initialTab);
  function setTab(value: StudioTab) {
    setTabState(value);
    onTabChange?.(value);
  }
  useEffect(() => {
    setTabState(initialTab);
    if (!["build", "growth", "discuss"].includes(initialTab))
      setAdvancedOpen(true);
  }, [initialTab]);
  const tabs = [
    { id: "build", name: "Build a product", icon: Code2 },
    { id: "growth", name: "Growth insights", icon: Brain },
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
            .filter((t) => ["build", "growth", "discuss"].includes(t.id))
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
                .filter((t) => !["build", "growth", "discuss"].includes(t.id))
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
    growth: "growth",
  };
  return (
    <div className="studio-page">
      <div className="studio-page-title">
        <span className="eyebrow">ONE SHARED EXECUTION SYSTEM</span>
        <h1>A connected runtime for every product.</h1>
        <p>
          The builder and growth review use these same services. Product source
          exports include this complete runtime in an isolated deployment, with
          fresh accounts, policies and credentials.
        </p>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="studio-two-columns">
        {runtime?.components
          .filter((c: any) => c.id !== "canvas")
          .map((c: any) => (
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
