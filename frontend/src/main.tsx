import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUp,
  Plus,
  Paperclip,
  PanelLeftClose,
  Sparkles,
  Search,
  Activity,
  Plug,
  LogOut,
  Square,
  ArrowUpRight,
  Code2,
  Users,
  Brain,
  KeyRound,
} from "lucide-react";
import {
  ProfileMenu,
  WorkspaceSettings,
  useWorkspacePreferences,
  playCompletionTone,
} from "./components/WorkspaceSettings";
import { PlatformHelp } from "./components/PlatformHelp";
import { UiIcon, WorkspaceArtwork } from "./components/UiIcon";
import { ComposerActions } from "./components/ComposerActions";
import { ConnectorArt } from "./components/ConnectorGallery";
import { ToolAccess, type ContextCall } from "./components/ToolAccess";
import { client } from "./api";
import type { Business, Convo, Run } from "./types";
import { ReportView } from "./components/ReportView";
import { ExecutionView } from "./components/ExecutionView";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AccountAccess } from "./components/AccountAccess";
import { AgentWorkspace, type StudioTab } from "./components/AgentWorkspace";
import { AgentControlCenter } from "./components/AgentControlCenter";
import { PlatformPanel } from "./components/PlatformPanel";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/700.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/800.css";
import "./style.css";
import "./workspace-refresh.css";
import "./reference-interactions.css";
function App() {
  const [token, setToken] = useState(
    sessionStorage.getItem("evolvyn-token") || "",
  );
  const [entry, setEntry] = useState("");
  const [demoConversation, setDemoConversation] = useState<string | null>(null);
  const [mode, setMode] = useState("default");
  const [analysisKind, setAnalysisKind] = useState("business");
  const [list, setList] = useState<Convo[]>([]);
  const [current, setCurrent] = useState<Convo | null>(null);
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [business, setBusiness] = useState("");
  const [showBusiness, setShowBusiness] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [runs, setRuns] = useState<Record<string, Run>>({});
  const [search, setSearch] = useState("");
  const [sidebar, setSidebar] = useState(innerWidth > 560);
  useEffect(() => {
    const mobile = window.matchMedia("(max-width: 560px)");
    const closeDrawer = () => {
      if (mobile.matches) setSidebar(false);
    };
    mobile.addEventListener("change", closeDrawer);
    return () => mobile.removeEventListener("change", closeDrawer);
  }, []);
  const [settings, setSettings] = useState(false);
  const [integrations, setIntegrations] = useState<
    { name: string; configured: boolean; status?: string }[]
  >([]);
  const [artifact, setArtifact] = useState<{
    id: string;
    plan: string;
    outcome: string;
  } | null>(null);
  const [controlCenter, setControlCenter] = useState(false);
  const [controlServerName, setControlServerName] = useState<
    string | undefined
  >();
  const [controlTab, setControlTab] = useState<"servers" | "tools">("servers");
  const [contextTools, setContextTools] = useState<ContextCall[]>([]);
  const [publicResearch, setPublicResearch] = useState(false);
  const [marketQuery, setMarketQuery] = useState("");
  const uploadInput = useRef<HTMLInputElement>(null);
  function manageConnections(
    tab: "servers" | "tools" = "servers",
    serverName?: string,
  ) {
    setControlTab(tab);
    setControlServerName(serverName);
    setControlCenter(true);
  }
  const [studio, setStudio] = useState<StudioTab | null>(null);
  const [panel, setPanel] = useState<
    | "tasks"
    | "reports"
    | "automation"
    | "workflow"
    | "projects"
    | "account"
    | null
  >(null);
  const [project, setProject] = useState("");
  const [projects, setProjects] = useState<
    { id: string; name: string; goal: string }[]
  >([]);
  const [providers, setProviders] = useState<
    {
      id: string;
      name: string;
      model: string;
      status: string;
      available?: boolean;
    }[]
  >([]);
  const [usage, setUsage] = useState<any>(null);
  const [providerStatus, setProviderStatus] = useState("");
  const [identity, setIdentity] = useState<{
    role: string;
    account: { id: string; name: string; email: string } | null;
    organizations: { id: string; name: string; role: string }[];
  } | null>(null);
  const [organization, setOrganization] = useState(
    sessionStorage.getItem("evolvyn-organization") || "",
  );
  useEffect(() => {
    if (token && business)
      api
        .json("/projects?business_id=" + business)
        .then(setProjects)
        .catch(handleError);
    else setProjects([]);
    setProject("");
  }, [business, token]);
  const [active, setActive] = useState<string | null>(null);
  const watches = useRef(new Map<string, AbortController>());
  const selected = useRef<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const api = client(token);
  const preferences = useWorkspacePreferences(api, identity?.account?.id);
  const preferencesRef = useRef(preferences.prefs);
  preferencesRef.current = preferences.prefs;
  const observedActive = useRef(new Set<string>());
  const [preferencesTab, setPreferencesTab] = useState<
    "general" | "account" | null
  >(null);
  const [selectedCapability, setSelectedCapability] = useState<
    string | undefined
  >();
  const handleError = (e: unknown) =>
    setError(e instanceof Error ? e.message : String(e));
  useEffect(() => {
    if (studio !== "agents") setSelectedCapability(undefined);
  }, [studio]);
  async function reload() {
    setList(await api.json("/conversations"));
  }
  function watch(id: string) {
    if (watches.current.has(id)) return;
    const controller = new AbortController();
    watches.current.set(id, controller);
    api
      .watch(
        id,
        (r: Run) => {
          setRuns((prev) => ({ ...prev, [r.id]: r }));
          if (["CREATED", "RUNNING"].includes(r.state)) {
            observedActive.current.add(id);
            setActive(id);
          } else {
            if (observedActive.current.delete(id)) {
              const p = preferencesRef.current;
              if (p.sound) {
                try {
                  playCompletionTone();
                } catch {}
              }
              if (
                p.browser_notifications &&
                "Notification" in window &&
                Notification.permission === "granted" &&
                document.visibilityState === "hidden"
              ) {
                try {
                  new Notification("Evolvyn task update", {
                    body:
                      r.state === "WAITING_FOR_APPROVAL"
                        ? "A task needs your review."
                        : "A task has finished. Open your workspace to review its status.",
                  });
                } catch {}
              }
            }
            setActive((prev) => (prev === id ? null : prev));
            if (selected.current) refresh(selected.current).catch(handleError);
          }
        },
        controller.signal,
      )
      .catch((e) => {
        if (e.name !== "AbortError") handleError(e);
      })
      .finally(() => watches.current.delete(id));
  }
  async function refresh(id: string) {
    const c = await api.json("/conversations/" + id);
    if (selected.current === id) setCurrent(c);
    return c as Convo;
  }
  async function open(id: string) {
    setBusy(true);
    try {
      selected.current = id;
      setSettings(false);
      setError("");
      const c = await refresh(id);
      for (const m of c.messages) {
        if (m.execution) {
          const r: Run = await api.json("/executions/" + m.execution);
          setRuns((prev) => ({ ...prev, [r.id]: r }));
          if (["CREATED", "RUNNING"].includes(r.state)) watch(r.id);
        }
      }
      if (innerWidth < 560) setSidebar(false);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (token) {
      api.json("/auth/me").then(setIdentity).catch(handleError);
      reload().catch(handleError);
      api.json("/businesses").then(setBusinesses).catch(handleError);
      if (demoConversation) {
        open(demoConversation).catch(handleError);
        setDemoConversation(null);
      }
    }
    return () => {
      watches.current.forEach((c) => c.abort());
      watches.current.clear();
    };
  }, [token]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "auto", block: "end" });
  }, [current?.messages.length]);
  const latestRunId = current?.messages
    .slice()
    .reverse()
    .find((m) => m.execution)?.execution;
  const latestRun = latestRunId ? runs[latestRunId] : null;
  function revealRun(part: "findings" | "approval" = "findings") {
    if (!latestRun) return;
    const root = document.getElementById("result-" + latestRun.id);
    const target =
      part === "approval"
        ? root?.querySelector(".approval")
        : root?.querySelector(".commerce-metrics") || root;
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  useEffect(() => {
    if (
      latestRun?.state === "WAITING_FOR_APPROVAL" ||
      latestRun?.state === "FAILED"
    )
      document
        .getElementById("result-" + latestRun.id)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [latestRun?.id, latestRun?.state]);
  async function create() {
    const b = businesses.find((b) => b.id === business);
    const c = await api.json("/conversations", {
      method: "POST",
      body: JSON.stringify({
        title: text.trim().slice(0, 70) || "New investigation",
        goal: b?.goal || "Improve paid conversion",
        business_id: business || null,
        project_id: project || null,
      }),
    });
    selected.current = c.id;
    setCurrent(c);
    setSettings(false);
    await reload();
    return c as Convo;
  }
  useEffect(() => {
    setContextTools([]);
    setPublicResearch(false);
    setMarketQuery("");
  }, [organization]);
  async function send() {
    if (!text.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const c = current || (await create());
      const r: Run = await api.json("/conversations/" + c.id + "/runs", {
        method: "POST",
        body: JSON.stringify({
          text,
          mode,
          allow_fallback: false,
          analysis_kind: analysisKind,
          context_tools: contextTools,
          public_research: publicResearch,
          market_query: marketQuery,
        }),
      });
      setRuns((prev) => ({ ...prev, [r.id]: r }));
      setActive(r.id);
      observedActive.current.add(r.id);
      setText("");
      document
        .querySelectorAll<HTMLDetailsElement>(".composer details[open]")
        .forEach((node) => (node.open = false));
      await refresh(c.id);
      watch(r.id);
      await reload();
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }
  async function upload(files: FileList | null) {
    if (!files?.length) return;
    const attachments = Array.from(files);
    setBusy(true);
    setError("");
    try {
      const c = current || (await create());
      for (const file of attachments) {
        const form = new FormData();
        form.append("file", file);
        await api.json("/conversations/" + c.id + "/files", {
          method: "POST",
          body: form,
        });
      }
      await refresh(c.id);
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }
  async function decide(
    r: Run,
    approve: boolean,
    plan: string,
    recommendationId?: string,
  ) {
    setBusy(true);
    try {
      const updated = await api.json("/executions/" + r.id + "/decision", {
        method: "POST",
        body: JSON.stringify({
          approve,
          plan,
          recommendation_id: recommendationId,
        }),
      });
      setRuns((prev) => ({ ...prev, [r.id]: updated }));
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }
  async function cancel(id: string) {
    try {
      const r = await api.json("/executions/" + id + "/cancel", {
        method: "POST",
      });
      setRuns((prev) => ({ ...prev, [id]: r }));
      setActive(null);
    } catch (e) {
      handleError(e);
    }
  }
  async function research() {
    if (!text.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const c = current || (await create());
      await api.json("/conversations/" + c.id + "/research", {
        method: "POST",
        body: JSON.stringify({ query: text.slice(0, 200) }),
      });
      setText("");
      await refresh(c.id);
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (!token)
      client("cookie")
        .json("/auth/me")
        .then((me) => {
          if (me.account) {
            sessionStorage.setItem("evolvyn-token", "cookie");
            setToken("cookie");
          }
        })
        .catch(() => {});
  }, []);
  function historyGroup(date?: string) {
    if (!date) return "Earlier";
    const day = (d: Date) =>
      d.toLocaleDateString("en-CA", { timeZone: "Asia/Calcutta" });
    return day(new Date(date)) === day(new Date())
      ? "Today"
      : day(new Date(date)) === day(new Date(Date.now() - 86400000))
        ? "Yesterday"
        : "Earlier";
  }
  let lastGroup = "";
  const activeHere =
    active && current?.messages.some((m) => m.execution === active)
      ? active
      : null;
  const b = businesses.find((b) => b.id === business);
  if (!token)
    return (
      <div className="login">
        <div className="mark">e</div>
        <h1>Your business, evolving.</h1>
        <p>Create your workspace or sign in. No OpenAI key is required.</p>
        <AccountAccess
          onAuthenticated={(organizationId) => {
            sessionStorage.setItem("evolvyn-organization", organizationId);
            sessionStorage.setItem("evolvyn-token", "cookie");
            setOrganization(organizationId);
            setToken("cookie");
          }}
        />
        <details className="private-access">
          <summary>Use private development token</summary>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await client(entry).json("/conversations");
                sessionStorage.setItem("evolvyn-token", entry);
                setError("");
                setToken(entry);
              } catch (e) {
                handleError(e);
              }
            }}
          >
            <input
              aria-label="Workspace token"
              type="password"
              required
              value={entry}
              onChange={(e) => setEntry(e.target.value)}
            />
            <button>Open workspace →</button>
          </form>
        </details>
        <div className="login-separator">or explore the working demo</div>
        <button
          className="demo-launch"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              const response = await fetch("/api/demo/session", {
                method: "POST",
              });
              if (!response.ok) throw Error("Sample workspace could not start");
              const data = await response.json();
              sessionStorage.setItem("evolvyn-token", data.token);
              setMode(data.analysis_mode || "evidence");
              setDemoConversation(data.conversation_id);
              setBusiness(data.business_id);
              setToken(data.token);
            } catch (e) {
              handleError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy
            ? "Preparing your sample workspace…"
            : "Try a sample business →"}
        </button>
        <small>
          Isolated synthetic data · local AI when available · 24-hour session
        </small>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </div>
    );
  return (
    <div className="app">
      {sidebar && (
        <aside>
          <div className="brand">
            <span className="mark">e</span> evolvyn{" "}
            <button
              aria-label="Collapse sidebar"
              onClick={() => setSidebar(false)}
            >
              <PanelLeftClose size={17} />
            </button>
          </div>
          <button
            className="new"
            onClick={() => {
              selected.current = null;
              setCurrent(null);
              setSettings(false);
              setText("");
              setError("");
              if (innerWidth < 560) setSidebar(false);
            }}
          >
            <UiIcon name="plus" size={21} /> New conversation
          </button>
          <label className="search">
            <Search size={15} />
            <input
              placeholder="Search conversations"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <div className="sidebar-scroll">
            {!!identity?.organizations.length && (
              <>
                <div className="section">ORGANIZATION</div>
                <select
                  aria-label="Organization"
                  className="workspace-select"
                  value={organization || identity.organizations[0].id}
                  onChange={async (e) => {
                    const id = e.target.value;
                    sessionStorage.setItem("evolvyn-organization", id);
                    setOrganization(id);
                    watches.current.forEach((w) => w.abort());
                    setCurrent(null);
                    selected.current = null;
                    setBusiness("");
                    setRuns({});
                    try {
                      setBusinesses(await api.json("/businesses"));
                      await reload();
                      setIdentity(await api.json("/auth/me"));
                    } catch (e) {
                      handleError(e);
                    }
                  }}
                >
                  {identity.organizations.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name} · {o.role}
                    </option>
                  ))}
                </select>
              </>
            )}
            <div className="section">BUSINESS WORKSPACE</div>
            <select
              aria-label="Business workspace"
              className="workspace-select"
              value={business}
              onChange={(e) => {
                setBusiness(e.target.value);
                setCurrent(null);
                selected.current = null;
              }}
            >
              <option value="">All investigations</option>
              {businesses.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            <button
              className="add-business"
              onClick={() => setShowBusiness(true)}
            >
              <Plus size={13} /> Add business
            </button>
            {business && (
              <>
                <select
                  className="workspace-select"
                  aria-label="Project"
                  value={project}
                  onChange={(e) => {
                    setProject(e.target.value);
                    setCurrent(null);
                    selected.current = null;
                  }}
                >
                  <option value="">All projects</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <button
                  className="add-business"
                  onClick={() => setPanel("projects")}
                >
                  <Plus size={13} /> New project
                </button>
              </>
            )}
            <div className="workspace-links">
              <button
                className="studio-nav-link"
                onClick={() => setStudio("build")}
              >
                <UiIcon name="code" />
                Build a product
              </button>
              <button
                className="studio-nav-link"
                onClick={() => setStudio("discuss")}
              >
                <UiIcon name="users" />
                Discussion room
              </button>
              <button
                className="studio-nav-link"
                onClick={() => setStudio("agents")}
              >
                <UiIcon name="git-branch" />
                Agents
              </button>
              <button
                className="studio-nav-link"
                onClick={() => setStudio("memory")}
              >
                <UiIcon name="brain" />
                Agent memory
              </button>
              <button
                className="studio-nav-link"
                onClick={() => setStudio("integrations")}
              >
                <UiIcon name="plug-connected" />
                Integrations
              </button>
              <button
                className="studio-nav-link"
                onClick={() => setStudio("vault")}
              >
                <UiIcon name="key" />
                Key vault
              </button>
              <button
                className="control-launch"
                onClick={() => setControlCenter(true)}
              >
                <UiIcon name="shield-check" /> Agent control center
              </button>
              <button onClick={() => setPanel("reports")}>
                <UiIcon name="file-text" /> Saved reports & outcomes
              </button>
              <button onClick={() => setPanel("tasks")}>
                <UiIcon name="check" /> Tasks & action plans
              </button>
              <button onClick={() => setPanel("automation")}>
                <UiIcon name="calendar" /> Recurring analysis
              </button>
              <button onClick={() => setPanel("workflow")}>
                <UiIcon name="automation" /> Agent workflow & tools
              </button>
            </div>
            <div className="section">CONVERSATIONS</div>
            <nav>
              {list
                .filter(
                  (c) =>
                    (!business || c.business_id === business) &&
                    (!project || c.project_id === project) &&
                    (c.title + " " + c.messages.map((m) => m.text).join(" "))
                      .toLowerCase()
                      .includes(search.toLowerCase()),
                )
                .map((c) => {
                  const group = historyGroup(c.created_at);
                  const heading = group !== lastGroup;
                  lastGroup = group;
                  return (
                    <div key={c.id}>
                      {heading && (
                        <small className="history-group">{group}</small>
                      )}
                      <button
                        className={current?.id === c.id ? "selected" : ""}
                        key={c.id}
                        onClick={() => open(c.id).catch(handleError)}
                      >
                        {c.title}
                        <small>{c.goal}</small>
                      </button>
                    </div>
                  );
                })}
              {!list.length && (
                <small className="empty">
                  Your investigations will appear here.
                </small>
              )}
            </nav>
          </div>
          <div className="aside-bottom">
            <ProfileMenu
              name={identity?.account?.name || "My workspace"}
              email={identity?.account?.email}
              role={identity?.role || "demo"}
              onSettings={() => setPreferencesTab("general")}
              onAccount={() => setPreferencesTab("account")}
              onConnections={async () => {
                try {
                  setIntegrations(await api.json("/integrations"));
                  setProviders(await api.json("/providers"));
                  setUsage(await api.json("/usage"));
                  setSettings(true);
                } catch (e) {
                  handleError(e);
                }
              }}
              onSignOut={async () => {
                if (token === "cookie")
                  await api
                    .json("/auth/logout", { method: "POST" })
                    .catch(() => {});
                sessionStorage.removeItem("evolvyn-token");
                sessionStorage.removeItem("evolvyn-organization");
                setOrganization("");
                setIdentity(null);
                watches.current.forEach((c) => c.abort());
                setToken("");
              }}
            />
          </div>
        </aside>
      )}
      <main>
        <header>
          {!sidebar && (
            <button aria-label="Open sidebar" onClick={() => setSidebar(true)}>
              <PanelLeftClose size={18} />
            </button>
          )}
          <span>
            {b?.name || "My business"} <span className="slash">/</span>
            {settings ? "Integrations" : current?.title || "New conversation"}
          </span>
          <div className="workspace-header-actions">
            <PlatformHelp key={organization} api={api} />
            <span className="badge">● Private workspace</span>
          </div>
        </header>
        <div className="scroll">
          {settings ? (
            <section className="welcome">
              <h1>Your connected tools</h1>
              <p>
                Use local AI without an API key, or configure an optional
                provider. Connection checks report what is available.
              </p>
              {providers.map((p) => (
                <div className="provider-card" key={p.id}>
                  <ConnectorArt name={p.name} size={27} />
                  <div>
                    <strong>{p.name}</strong>
                    <small>{p.model}</small>
                    <p>{p.status}</p>
                  </div>
                  <button
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        const result = await api.json(
                          "/providers/" + p.id + "/test",
                          { method: "POST" },
                        );
                        setProviderStatus(
                          p.name +
                            ": " +
                            (result.available
                              ? "Connection verified"
                              : result.reason),
                        );
                      } catch (e) {
                        handleError(e);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Test connection
                  </button>
                </div>
              ))}
              {integrations
                .filter((i) => !i.name.includes("OpenAI"))
                .map((i) => (
                  <div className="integration" key={i.name}>
                    <strong>{i.name}</strong>
                    <span>
                      {i.status ||
                        (i.configured
                          ? "Configured; connectivity unverified"
                          : "Not configured")}
                    </span>
                  </div>
                ))}
              {usage && (
                <p className="muted">
                  {usage.total_runs} saved executions · {usage.note}
                </p>
              )}

              <p role="status">{providerStatus}</p>
              <p>
                Local AI runs on this machine and needs no API key. Optional
                remote providers use encrypted credentials configured in Key
                vault. Local-only projects prevent remote model requests.
              </p>
            </section>
          ) : (
            <>
              {!current?.messages.length && (
                <section className="welcome studio-home">
                  <div className="home-wordmark">
                    <span className="mark">e</span>evolvyn
                  </div>
                  <h1>
                    Your next idea. <br />A team to make it happen.
                  </h1>
                  <p>
                    Build products, understand your business, and turn the right
                    evidence into your next decision.
                  </p>
                  <div className="home-actions">
                    <button
                      className="home-build"
                      onClick={() => setStudio("build")}
                    >
                      <UiIcon name="code" size={25} />
                      <WorkspaceArtwork kind="build" />
                      <strong>
                        Build a product <ArrowUpRight size={15} />
                      </strong>
                      <span>From requirements to a working starter</span>
                    </button>
                    <button
                      className="home-growth"
                      onClick={() => setStudio("growth")}
                    >
                      <UiIcon name="chart-line" size={25} />
                      <WorkspaceArtwork kind="growth" />
                      <strong>
                        Grow your business <ArrowUpRight size={15} />
                      </strong>
                      <span>Start with your customer and conversion data</span>
                    </button>
                    <button
                      className="home-discuss"
                      onClick={() => setStudio("discuss")}
                    >
                      <UiIcon name="users" size={25} />
                      <WorkspaceArtwork kind="discuss" />
                      <strong>
                        Discuss your next move <ArrowUpRight size={15} />
                      </strong>
                      <span>A specialist team, one shared goal</span>
                    </button>
                  </div>
                  <div className="home-utility">
                    <button onClick={() => setStudio("integrations")}>
                      <Plus size={13} />
                      Connect your tools
                    </button>
                    <button onClick={() => setStudio("vault")}>
                      <KeyRound size={13} />
                      Set up model keys
                    </button>
                    <button onClick={() => setStudio("memory")}>
                      <Brain size={13} />
                      Agent memory
                    </button>
                  </div>
                </section>
              )}
              <div className="messages">
                {current?.messages.map((m, i) => {
                  const r = m.execution ? runs[m.execution] : null;
                  const report = m.report || r?.report;
                  return (
                    <article
                      key={i}
                      id={m.execution ? "result-" + m.execution : undefined}
                      className={m.role}
                    >
                      <div className="message-label">
                        {m.role === "user" ? (
                          "You"
                        ) : (
                          <>
                            <span className="assistant-emblem">e</span> Evolvyn
                          </>
                        )}
                      </div>
                      <div className="markdown">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            a: ({ href, children }) => (
                              <a
                                href={href}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                {children}
                              </a>
                            ),
                          }}
                        >
                          {r?.output || m.text}
                        </ReactMarkdown>
                      </div>
                      {m.sources?.map((source, j) => (
                        <a
                          className="source-link"
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          key={j}
                        >
                          {j + 1}. {source.title} ↗
                        </a>
                      ))}
                      {report && <ReportView report={report} />}{" "}
                      {r && (
                        <ExecutionView
                          run={r}
                          busy={busy}
                          onSpecializedReview={(engine) =>
                            engine === "langgraph_discussion"
                              ? setStudio("discuss")
                              : setControlCenter(true)
                          }
                          onDecide={decide}
                          onCancel={cancel}
                          onArtifact={async (id) => {
                            try {
                              setArtifact(await api.json("/artifacts/" + id));
                            } catch (e) {
                              handleError(e);
                            }
                          }}
                        />
                      )}
                    </article>
                  );
                })}
                <div ref={bottom} />
              </div>
            </>
          )}
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
        </div>
        {!settings && latestRun && (
          <div className="run-summary" role="status">
            <span className={"run-dot " + latestRun.state.toLowerCase()} />
            <div>
              <strong>
                {latestRun.state === "WAITING_FOR_APPROVAL"
                  ? "Analysis ready · review your proposed action"
                  : latestRun.state === "COMPLETED"
                    ? "Run completed · result saved"
                    : latestRun.state === "FAILED"
                      ? "Run stopped · see the error"
                      : latestRun.state === "CANCELLED"
                        ? "Run cancelled"
                        : "Agent working · " +
                          (latestRun.events.at(-1)?.stage || "queued")}
              </strong>
              <small>
                {latestRun.events.at(-1)?.detail || "Waiting for the worker"}
              </small>
            </div>
            <button onClick={() => revealRun()}>View results</button>
            {latestRun.state === "WAITING_FOR_APPROVAL" && (
              <button className="primary" onClick={() => revealRun("approval")}>
                Review action
              </button>
            )}
            <button
              aria-label="Refresh run status"
              onClick={async () => {
                try {
                  const r = await api.json("/executions/" + latestRun.id);
                  setRuns((prev) => ({ ...prev, [r.id]: r }));
                  if (["CREATED", "RUNNING"].includes(r.state)) watch(r.id);
                } catch (e) {
                  handleError(e);
                }
              }}
            >
              Refresh
            </button>
          </div>
        )}
        {!settings && (
          <footer
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (!busy && !activeHere) upload(e.dataTransfer.files);
            }}
          >
            <div className="composer">
              {!!current?.files.length && (
                <div className="files">
                  {current.files.map((f) => (
                    <span key={f.id}>
                      <Paperclip size={12} />
                      {f.name}
                      {f.import && <small>Parsed {f.import.kind} data</small>}
                      <button
                        aria-label={"Remove " + f.name}
                        disabled={!!activeHere}
                        onClick={async () => {
                          try {
                            await api.json(
                              "/conversations/" +
                                current!.id +
                                "/files/" +
                                f.id,
                              { method: "DELETE" },
                            );
                            await refresh(current!.id);
                          } catch (e) {
                            handleError(e);
                          }
                        }}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
              <details className="chat-research">
                <summary>Market research options</summary>
                <div className="research-popover">
                  <label>
                    <input
                      aria-label="Include public research"
                      type="checkbox"
                      checked={publicResearch}
                      onChange={(e) => setPublicResearch(e.target.checked)}
                    />
                    Include live public discussion research with this run
                  </label>
                  {publicResearch && (
                    <label>
                      Public research query
                      <input
                        aria-label="Public research query"
                        value={marketQuery}
                        onChange={(e) => setMarketQuery(e.target.value)}
                        maxLength={200}
                        placeholder="Public product/category terms only"
                      />
                      <small>
                        This exact query is sent to Algolia/Hacker News. It is
                        discussion evidence, not verified competitor or
                        market-share data.
                      </small>
                    </label>
                  )}
                </div>
              </details>
              <textarea
                rows={2}
                aria-label="Message Evolvyn"
                placeholder="What would you like to improve?"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (!activeHere) send();
                  }
                }}
              />
              <div className="composer-tools">
                <ComposerActions
                  disabled={busy || !!activeHere}
                  onUpload={() => uploadInput.current?.click()}
                  onConnections={() => manageConnections()}
                  onBuild={() => setStudio("build")}
                  onCanvas={() => setStudio("canvas")}
                  onReports={() => setPanel("reports")}
                  api={api}
                  conversations={(current
                    ? [current, ...list.filter((c) => c.id !== current.id)]
                    : list
                  ).filter(
                    (c) =>
                      (!business || c.business_id === business) &&
                      (!project || c.project_id === project),
                  )}
                  onOpenConversation={(id) => open(id).catch(handleError)}
                  onAgents={(id) => {
                    setSelectedCapability(id);
                    setStudio("agents");
                  }}
                />
                <label
                  className="upload direct-upload"
                  title="Upload TXT, CSV, PDF or DOCX"
                >
                  <span className="sr-only">Upload evidence</span>
                  <input
                    ref={uploadInput}
                    aria-label="Upload evidence files"
                    type="file"
                    disabled={busy || !!activeHere}
                    accept=".txt,.csv,.pdf,.docx"
                    multiple
                    onChange={(e) => {
                      upload(e.target.files);
                      e.target.value = "";
                    }}
                  />
                </label>
                <ToolAccess
                  key={organization}
                  api={api}
                  onManage={manageConnections}
                  calls={contextTools}
                  onChange={setContextTools}
                  conversationId={current?.id}
                />
                <select
                  className="mode-select"
                  aria-label="Analysis type"
                  value={analysisKind}
                  onChange={(e) => setAnalysisKind(e.target.value)}
                >
                  <option value="business">Business</option>
                  <option value="operations">Uploaded logs</option>
                </select>
                <select
                  className="mode-select"
                  aria-label="Analysis mode"
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                >
                  <option value="default">Default model route</option>
                  <option value="local">Local AI · no API key</option>
                  <option value="evidence">Evidence only</option>
                  <option value="provider">OpenAI · optional</option>
                  <option value="groq">Groq · your key</option>
                  <option value="gemini">Gemini · your key</option>
                </select>
                <button
                  disabled={busy || !!activeHere || text.trim().length < 3}
                  onClick={research}
                >
                  Research
                </button>
                {activeHere ? (
                  <button
                    className="send"
                    aria-label="Stop analysis"
                    onClick={() => cancel(activeHere)}
                  >
                    <Square size={16} />
                  </button>
                ) : (
                  <button
                    className="send"
                    aria-label="Run analysis"
                    disabled={busy || !text.trim()}
                    onClick={send}
                  >
                    {busy ? "…" : <ArrowUp size={19} />}
                  </button>
                )}
              </div>
            </div>
            <small>
              Facts have sources. Hypotheses need validation. Actions need your
              approval.
            </small>
          </footer>
        )}
      </main>
      {studio && (
        <AgentWorkspace
          key={organization}
          api={api}
          initialTab={studio}
          initialAgent={selectedCapability}
          onSettings={() => setPreferencesTab("general")}
          onNavigate={(id) => {
            setStudio(null);
            open(id).catch(handleError);
          }}
          conversation={current}
          projectId={project}
          businessId={business}
          onClose={() => setStudio(null)}
          onRefresh={() => {
            reload();
            if (selected.current)
              api
                .json("/conversations/" + selected.current)
                .then(setCurrent)
                .catch(handleError);
          }}
          onManage={manageConnections}
        />
      )}
      {preferencesTab && (
        <WorkspaceSettings
          api={api}
          initialTab={preferencesTab}
          preferences={preferences}
          onClose={() => setPreferencesTab(null)}
          onConnections={() => manageConnections()}
          onVault={() => setStudio("vault")}
          onAgents={() => setStudio("agents")}
        />
      )}
      {controlCenter && (
        <AgentControlCenter
          initialTab={controlTab}
          initialServerName={controlServerName}
          api={api}
          conversation={current}
          onClose={() => setControlCenter(false)}
          onRefresh={() => {
            if (current) open(current.id).catch(handleError);
          }}
        />
      )}
      {panel && (
        <PlatformPanel
          view={panel}
          api={api}
          businessId={business}
          conversation={current}
          onClose={() => setPanel(null)}
          onRefresh={() => {
            if (current) open(current.id).catch(handleError);
          }}
          onProject={async () => {
            if (business)
              setProjects(await api.json("/projects?business_id=" + business));
          }}
        />
      )}
      {showBusiness && (
        <div className="modal-shade">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="business-heading"
          >
            <h2 id="business-heading">Add a business</h2>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const data = new FormData(e.currentTarget);
                try {
                  const created = await api.json("/businesses", {
                    method: "POST",
                    body: JSON.stringify(Object.fromEntries(data)),
                  });
                  setBusinesses((prev) => [created, ...prev]);
                  setBusiness(created.id);
                  setCurrent(null);
                  selected.current = null;
                  setShowBusiness(false);
                } catch (err) {
                  handleError(err);
                }
              }}
            >
              <label>
                Business name
                <input autoFocus name="name" required maxLength={100} />
              </label>
              <label>
                Business type
                <select name="kind" defaultValue="ecommerce">
                  <option value="ecommerce">E-commerce</option>
                  <option value="general">Other business</option>
                </select>
              </label>
              <label>
                Product or service
                <input name="product" maxLength={1000} />
              </label>
              <label>
                Business goal
                <textarea name="goal" required maxLength={1000} />
              </label>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowBusiness(false)}>
                  Cancel
                </button>
                <button className="primary">Create business</button>
              </div>
            </form>
          </section>
        </div>
      )}
      {artifact && (
        <div className="modal-shade">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="brief-heading"
          >
            <h2 id="brief-heading">Approved experiment brief</h2>
            <p>{artifact.plan}</p>
            <p className="muted">{artifact.outcome}</p>
            <button
              onClick={() => {
                setArtifact(null);
                setPanel("tasks");
              }}
            >
              Manage created tasks & measure outcomes →
            </button>
            <button onClick={() => setArtifact(null)}>Close</button>
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
