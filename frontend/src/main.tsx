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
} from "lucide-react";
import { client } from "./api";
import type { Business, Convo, Run } from "./types";
import { ReportView } from "./components/ReportView";
import { ExecutionView } from "./components/ExecutionView";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AccountAccess } from "./components/AccountAccess";
import { AgentControlCenter } from "./components/AgentControlCenter";
import { PlatformPanel } from "./components/PlatformPanel";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/700.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/800.css";
import "./style.css";
function App() {
  const [token, setToken] = useState(
    sessionStorage.getItem("evolvyn-token") || "",
  );
  const [entry, setEntry] = useState("");
  const [demoConversation, setDemoConversation] = useState<string | null>(null);
  const [mode, setMode] = useState("local");
  const [analysisKind,setAnalysisKind]=useState("business");
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
  const [settings, setSettings] = useState(false);
  const [integrations, setIntegrations] = useState<
    { name: string; configured: boolean }[]
  >([]);
  const [artifact, setArtifact] = useState<{
    id: string;
    plan: string;
    outcome: string;
  } | null>(null);
  const [controlCenter,setControlCenter]=useState(false);
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
    account: { email: string } | null;
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
  const handleError = (e: unknown) =>
    setError(e instanceof Error ? e.message : String(e));
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
          if (["CREATED", "RUNNING"].includes(r.state)) setActive(id);
          else {
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
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [current?.messages.length]);
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
  async function send() {
    if (!text.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const c = current || (await create());
      const r: Run = await api.json("/conversations/" + c.id + "/runs", {
        method: "POST",
        body: JSON.stringify({ text, mode, allow_fallback: true,analysis_kind:analysisKind }),
      });
      setRuns((prev) => ({ ...prev, [r.id]: r }));
      setActive(r.id);
      setText("");
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
              setMode(data.analysis_mode||"evidence");
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
            <Plus size={17} /> New conversation
          </button>
          <label className="search">
            <Search size={15} />
            <input
              placeholder="Search conversations"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
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
          <div className="workspace-links"><button className="control-launch" onClick={()=>setControlCenter(true)}>Agent control center <span>New</span></button>
            <button onClick={() => setPanel("reports")}>
              Saved reports & outcomes
            </button>
            <button onClick={() => setPanel("tasks")}>
              Tasks & action plans
            </button>
            <button onClick={() => setPanel("automation")}>
              Recurring analysis
            </button>
            <button onClick={() => setPanel("workflow")}>
              Agent workflow & tools
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
          <div className="aside-bottom">
            <button onClick={() => setPanel("account")}>Account & team</button>
            <button
              onClick={async () => {
                try {
                  setIntegrations(await api.json("/integrations"));
                  setProviders(await api.json("/providers"));
                  setUsage(await api.json("/usage"));
                  setSettings(true);
                } catch (e) {
                  handleError(e);
                }
              }}
            >
              <Plug size={16} /> Integrations & models
            </button>
            <button
              onClick={async () => {
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
            >
              <LogOut size={16} /> Lock workspace
            </button>
            <small>Development edition · Evidence first</small>
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
          <span className="badge">● Private workspace</span>
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
                      {i.configured ? "Configured" : "Not configured"}
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
                remote providers use credentials from your environment settings.
                Local-only projects prevent remote model requests.
              </p>
            </section>
          ) : (
            <>
              {!current?.messages.length && (
                <section className="welcome">
                  <div className="eyebrow">
                    <Sparkles size={16} /> CONTINUOUS BUSINESS EVOLUTION
                  </div>
                  <h1>
                    Turn evidence into
                    <br />
                    your next move.
                  </h1>
                  <p>
                    A focused space to understand your business,
                    <br />
                    challenge assumptions, and act with confidence.
                  </p>
                  <div className="suggestions">
                    <button
                      onClick={() =>
                        setText(
                          "Analyze my funnel and identify conversion opportunities.",
                        )
                      }
                    >
                      <Activity size={19} />
                      <strong>Find growth opportunities</strong>
                      <span>Start with your conversion data ↗</span>
                    </button>
                    <button
                      onClick={() =>
                        setText(
                          "What do customers say about onboarding friction? Cite the relevant passages.",
                        )
                      }
                    >
                      <Sparkles size={19} />
                      <strong>Investigate customer feedback</strong>
                      <span>Bring evidence to your next decision ↗</span>
                    </button>
                  </div>
                  <div className="notice">
                    Attach TXT, CSV, PDF or DOCX evidence to begin.
                    <br />
                    Use sample-data/funnel.csv for a clearly synthetic
                    demonstration.
                  </div>
                  {b && (
                    <p className="business-context">
                      <strong>{b.name}</strong> · {b.goal}
                    </p>
                  )}
                </section>
              )}
              <div className="messages">
                {current?.messages.map((m, i) => {
                  const r = m.execution ? runs[m.execution] : null;
                  const report = m.report || r?.report;
                  return (
                    <article key={i} className={m.role}>
                      <div className="message-label">
                        {m.role === "user" ? "You" : "✳ Evolvyn"}
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
        {!settings && (
          <footer
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (!activeHere) upload(e.dataTransfer.files);
            }}
          >
            <div className="composer">
              {!!current?.files.length && (
                <div className="files">
                  {current.files.map((f) => (
                    <span key={f.id}>
                      <Paperclip size={12} />
                      {f.name}
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
              <textarea
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
                <label className="upload" title="Upload TXT, CSV, PDF or DOCX">
                  <Paperclip size={19} />
                  <input
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
                <select className="mode-select" aria-label="Analysis type" value={analysisKind} onChange={e=>setAnalysisKind(e.target.value)}><option value="business">Business</option><option value="operations">Uploaded logs</option></select><select
                  className="mode-select"
                  aria-label="Analysis mode"
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                >
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
      {controlCenter&&<AgentControlCenter api={api} conversation={current} onClose={()=>setControlCenter(false)} onRefresh={()=>{if(current)open(current.id).catch(handleError)}}/>}
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
