import { ConnectorGallery, ConnectorArt } from "./ConnectorGallery";
import { useEffect, useRef, useState } from "react";
import { UiIcon } from "./UiIcon";
import {
  X,
  Server,
  Workflow,
  Shield,
  Blocks,
  Check,
  Play,
  RefreshCw,
  Plus,
  ArrowRight,
} from "lucide-react";
import type { client } from "../api";
import type { Convo } from "../types";
type Tab = "servers" | "tools" | "harness" | "governance";
export function AgentControlCenter({
  api,
  conversation,
  onClose,
  onRefresh,
  initialTab = "servers",
}: {
  api: ReturnType<typeof client>;
  conversation: Convo | null;
  onClose: () => void;
  onRefresh: () => void;
  initialTab?: Tab;
}) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [servers, setServers] = useState<any[]>([]);
  const [tools, setTools] = useState<any[]>([]);
  const [graphs, setGraphs] = useState<any[]>([]);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [executions, setExecutions] = useState<any[]>([]);
  const [policy, setPolicy] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [members, setMembers] = useState<any[]>([]);
  const [credentialPrefix, setCredentialPrefix] = useState("EVOLVYN_MCP_");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [transport, setTransport] = useState("stdio");
  const [adapter, setAdapter] = useState("mcp");
  const [serverId, setServerId] = useState("");
  const [goal, setGoal] = useState(
    "Analyze conversion evidence and save a reviewed project note",
  );
  const [graphText, setGraphText] = useState("");
  const [graphId, setGraphId] = useState("");
  const [subgoals, setSubgoals] = useState<any[]>([]);
  const [mode, setMode] = useState("evidence");
  const [active, setActive] = useState<any>(null);
  const [invoking, setInvoking] = useState<any>(null);
  const [argumentsText, setArgumentsText] = useState("{}");
  const [result, setResult] = useState<any>(null);
  const serverForm = useRef<HTMLFormElement | null>(null);
  const [toolSearch, setToolSearch] = useState("");
  const watch = useRef<AbortController | null>(null);
  const fail = (e: unknown) =>
    setError(e instanceof Error ? e.message : String(e));
  async function load() {
    const [a, b, c, d, e, f, g, h, i] = await Promise.all([
      api.json("/mcp/servers"),
      api.json("/tool-registry"),
      api.json("/harness/graphs"),
      api.json("/tool-approvals"),
      api.json("/governance/policy"),
      api.json("/projects"),
      api.json("/organizations/members"),
      api.json("/harness/executions"),
      api.json("/mcp/credential-prefix"),
    ]);
    setServers(a);
    setTools(b);
    setGraphs(c);
    setApprovals(d);
    setPolicy(e);
    setProjects(f);
    setMembers(g);
    setExecutions(h);
    setCredentialPrefix(i.prefix);
  }
  useEffect(() => {
    load().catch(fail);
    return () => watch.current?.abort();
  }, []);
  async function action(fn: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await load();
      setNotice(message);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  function startWatch(id: string) {
    watch.current?.abort();
    const controller = new AbortController();
    watch.current = controller;
    api
      .watch(
        id,
        (run: any) => {
          setActive(run);
          if (!["CREATED", "RUNNING"].includes(run.state)) {
            load().catch(fail);
            onRefresh();
          }
        },
        controller.signal,
      )
      .catch((e) => {
        if (e.name !== "AbortError") fail(e);
      });
  }
  function invoke(tool: any) {
    setInvoking(tool);
    setResult(null);
    const values: Record<string, unknown> = {};
    for (const [key, schema] of Object.entries(
      tool.input_schema.properties || {},
    ) as [string, any][]) {
      values[key] =
        key === "conversation_id"
          ? conversation?.id || ""
          : key === "query"
            ? "Analyze current business evidence"
            : key === "before"
              ? 5
              : key === "after"
                ? 6
                : schema.type === "integer" || schema.type === "number"
                  ? 1
                  : schema.type === "array"
                    ? []
                    : schema.type === "object"
                      ? {}
                      : "";
    }
    setArgumentsText(JSON.stringify(values, null, 2));
  }
  const chosenServer = servers.find((s) => s.id === serverId);
  const pending = active?.graph_checkpoint?.pending;
  return (
    <div className="control-overlay">
      <section
        className="control-center"
        role="dialog"
        aria-modal="true"
        aria-labelledby="control-heading"
      >
        <header className="control-header">
          <div className="control-brand">
            <span className="mark">e</span>
            <div>
              <small>EVOLVYN / AGENT INFRASTRUCTURE</small>
              <h1 id="control-heading">Agent control center</h1>
            </div>
          </div>
          <div className="control-header-actions">
            <span className="control-live">
              <i />
              Backend governed
            </span>
            <button
              aria-label="Refresh control center"
              onClick={() => load().catch(fail)}
            >
              <RefreshCw size={16} />
            </button>
            <button aria-label="Close agent control center" onClick={onClose}>
              <X size={20} />
            </button>
          </div>
        </header>
        <div className="control-body">
          <nav className="control-nav">
            {(
              [
                {
                  id: "servers",
                  name: "MCP servers",
                  icon: Server,
                  caption: "Connections & discovery",
                },
                {
                  id: "tools",
                  name: "Tool registry",
                  icon: Blocks,
                  caption: "Capabilities & approvals",
                },
                {
                  id: "harness",
                  name: "Agent harness",
                  icon: Workflow,
                  caption: "Plans, graphs & execution",
                },
                {
                  id: "governance",
                  name: "Governance",
                  icon: Shield,
                  caption: "Policies & project access",
                },
              ] as const
            ).map((item) => (
              <button
                className={tab === item.id ? "active" : ""}
                key={item.id}
                onClick={() => {
                  setTab(item.id);
                  setError("");
                  setNotice("");
                }}
              >
                <UiIcon
                  name={
                    (
                      {
                        servers: "plug-connected",
                        tools: "layout-grid",
                        harness: "git-branch",
                        governance: "shield-check",
                      } as const
                    )[item.id]
                  }
                  size={20}
                />
                <span>
                  {item.name}
                  <small>{item.caption}</small>
                </span>
                <ArrowRight size={13} />
              </button>
            ))}
            <div className="control-nav-note">
              <Shield size={17} />
              <p>
                Tools cannot grant themselves access. Consequential actions wait
                for human approval.
              </p>
            </div>
          </nav>
          <main className="control-main">
            <details className="control-purpose">
              <summary>What does the Agent control center do?</summary>
              <p>
                This is Evolvyn’s shared configuration and operations area.
                Connect MCP servers and verify health, register their tools,
                inspect workflow executions and approval requests, and set
                organization/project permissions. The development and business
                screens use these same connections through Connections & tools.
                Reading evidence and approving a write are separate permissions;
                a connected tool cannot approve its own actions.
              </p>
            </details>
            {error && (
              <div role="alert" className="error">
                {error}
              </div>
            )}
            {notice && (
              <div role="status" className="control-notice">
                <Check size={15} />
                {notice}
              </div>
            )}
            {tab === "servers" && (
              <>
                <div className="control-title">
                  <span className="eyebrow">INTEGRATION LAYER</span>
                  <h2>Connect your agent tools.</h2>
                  <p>
                    Register MCP servers, discover their capabilities, and
                    verify connectivity before use.
                  </p>
                </div>
                <ConnectorGallery
                  servers={servers}
                  onConfigure={(name) => {
                    setTransport("streamable_http");
                    requestAnimationFrame(() => {
                      serverForm.current?.scrollIntoView({
                        behavior: "smooth",
                        block: "center",
                      });
                      const input =
                        serverForm.current?.querySelector<HTMLInputElement>(
                          "input[name=name]",
                        );
                      if (input) {
                        input.value = name;
                        input.focus();
                      }
                    });
                  }}
                  onBundled={(name, profile) => {
                    const existing = servers.find((s) => s.profile === profile);
                    if (existing) {
                      document
                        .getElementById("mcp-" + existing.id)
                        ?.scrollIntoView({
                          behavior: "smooth",
                          block: "center",
                        });
                      return;
                    }
                    action(async () => {
                      const row = await api.json("/mcp/servers", {
                        method: "POST",
                        body: JSON.stringify({
                          name,
                          profile,
                          transport: "stdio",
                        }),
                      });
                      await api.json("/mcp/servers/" + row.id + "/probe", {
                        method: "POST",
                      });
                    }, "Bundled server registered and health checked");
                  }}
                />
                <div className="control-stats">
                  <div>
                    <strong>{servers.length}</strong>
                    <span>Registered servers</span>
                  </div>
                  <div>
                    <strong>
                      {servers.filter((s) => s.status === "healthy").length}
                    </strong>
                    <span>Healthy connections</span>
                  </div>
                  <div>
                    <strong>
                      {servers.reduce((n, s) => n + (s.tools?.length || 0), 0)}
                    </strong>
                    <span>Discovered tools</span>
                  </div>
                </div>
                <div className="control-columns">
                  <div>
                    <h3>Registered connections</h3>
                    {!servers.length && (
                      <div className="control-empty">
                        Add a bundled server to start. Connections and discovery
                        results persist in your organization.
                      </div>
                    )}
                    {servers.map((s) => (
                      <article
                        className="control-card server-card"
                        id={"mcp-" + s.id}
                        key={s.id}
                      >
                        <div className="control-card-heading">
                          <span className="server-icon">
                            <ConnectorArt name={s.name + " " + s.profile} />
                          </span>
                          <div>
                            <strong>{s.name}</strong>
                            <small>
                              {s.transport === "stdio" ? s.profile : s.url}
                            </small>
                          </div>
                          <span
                            className={
                              "status-pill " +
                              (s.status === "healthy" ? "healthy" : "")
                            }
                          >
                            {!s.enabled ? "Disabled" : s.status}
                          </span>
                        </div>
                        <div className="tool-chips">
                          {s.tools?.map((t: any) => (
                            <span key={t.name}>{t.name}</span>
                          ))}
                        </div>
                        <small>
                          {s.last_checked_at
                            ? "Checked " +
                              new Date(s.last_checked_at).toLocaleString(
                                undefined,
                                { timeZone: "Asia/Calcutta" },
                              )
                            : "Not checked yet"}{" "}
                          · Risk: {s.risk}
                        </small>
                        {s.last_error && (
                          <p className="control-error">{s.last_error}</p>
                        )}
                        <div className="control-card-actions">
                          <button
                            disabled={busy || !s.enabled}
                            onClick={() =>
                              action(
                                () =>
                                  api.json("/mcp/servers/" + s.id + "/probe", {
                                    method: "POST",
                                  }),
                                "Server health and discovery refreshed",
                              )
                            }
                          >
                            <RefreshCw size={13} />
                            Check health
                          </button>
                          <button
                            disabled={busy}
                            onClick={() =>
                              action(
                                () =>
                                  api.json("/mcp/servers/" + s.id, {
                                    method: "PUT",
                                    body: JSON.stringify(
                                      Object.fromEntries(
                                        [
                                          "name",
                                          "transport",
                                          "profile",
                                          "url",
                                          "auth_env",
                                          "credential_id",
                                          "risk",
                                          "timeout_seconds",
                                        ]
                                          .map((k) => [k, s[k]])
                                          .concat([["enabled", !s.enabled]]),
                                      ),
                                    ),
                                  }),
                                "Server availability updated",
                              )
                            }
                          >
                            {s.enabled ? "Disable" : "Enable"}
                          </button>
                          <button
                            disabled={busy}
                            onClick={() =>
                              action(
                                () =>
                                  api.json("/mcp/servers/" + s.id, {
                                    method: "DELETE",
                                  }),
                                "Server removed",
                              )
                            }
                          >
                            Remove
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                  <form
                    ref={serverForm}
                    className="control-card control-form"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const form = e.currentTarget;
                      const d = Object.fromEntries(new FormData(form));
                      action(async () => {
                        await api.json("/mcp/servers", {
                          method: "POST",
                          body: JSON.stringify({
                            name: d.name,
                            transport,
                            profile: transport === "stdio" ? d.profile : null,
                            url: transport === "streamable_http" ? d.url : null,
                            auth_env: d.auth_env || null,
                            credential_id: d.credential_id || null,
                            risk: transport === "stdio" ? "read" : d.risk,
                            timeout_seconds: 15,
                            enabled: true,
                          }),
                        });
                        form.reset();
                      }, "Server registered; check its health to discover tools");
                    }}
                  >
                    <h3>
                      <Plus size={16} />
                      Register a server
                    </h3>
                    <label>
                      Display name
                      <input
                        name="name"
                        required
                        maxLength={100}
                        placeholder="Business evidence tools"
                      />
                    </label>
                    <label>
                      Transport
                      <select
                        value={transport}
                        onChange={(e) => setTransport(e.target.value)}
                      >
                        <option value="stdio">Bundled stdio profile</option>
                        <option value="streamable_http">
                          Remote HTTPS MCP
                        </option>
                      </select>
                    </label>
                    {transport === "stdio" ? (
                      <label>
                        Server profile
                        <select aria-label="Server profile" name="profile">
                          <option value="evidence_utilities">
                            Evidence utilities · rates & validation
                          </option>
                          <option value="business_strategy">
                            Business strategy · prioritization
                          </option>
                        </select>
                      </label>
                    ) : (
                      <>
                        <label>
                          HTTPS endpoint
                          <input
                            name="url"
                            type="url"
                            required
                            placeholder="https://approved.example/mcp"
                          />
                        </label>
                        <small>
                          Add the endpoint hostname to Governance first. Private
                          network destinations and embedded credentials are
                          rejected.
                        </small>
                        <label>
                          Vault credential ID
                          <input
                            name="credential_id"
                            placeholder="Copy an MCP credential reference from Key vault"
                          />
                        </label>
                        <label>
                          Credential variable reference
                          <input
                            name="auth_env"
                            placeholder={credentialPrefix + "TOKEN"}
                          />
                        </label>
                        <small>
                          Enter a variable name only. Configure its value
                          securely in the environment.
                        </small>
                        <label>
                          Maximum tool risk
                          <select name="risk">
                            <option value="external_write">
                              External write · approval required
                            </option>
                            <option value="read">
                              Read only · administrator declaration
                            </option>
                            <option value="critical">
                              Critical · requires policy allowance
                            </option>
                          </select>
                        </label>
                      </>
                    )}
                    <button className="primary" disabled={busy}>
                      <Plus size={14} />
                      Register connection
                    </button>
                  </form>
                </div>
              </>
            )}
            {tab === "tools" && (
              <>
                <div className="control-title">
                  <span className="eyebrow">CAPABILITY REGISTRY</span>
                  <h2>The right tool. The right permission.</h2>
                  <p>
                    Persistent adapters expose validated capabilities. Write
                    operations require an argument-bound, one-time approval.
                  </p>
                </div>
                <div className="control-columns">
                  <div>
                    <label className="tool-registry-search">
                      Find a registered capability
                      <input
                        aria-label="Search registered tools"
                        value={toolSearch}
                        onChange={(e) => setToolSearch(e.target.value)}
                        placeholder="Search tools, entities or capabilities"
                      />
                    </label>
                    {tools
                      .filter((t) =>
                        (
                          t.name +
                          " " +
                          t.description +
                          " " +
                          t.entities?.join(" ") +
                          " " +
                          t.capabilities?.join(" ")
                        )
                          .toLowerCase()
                          .includes(toolSearch.toLowerCase()),
                      )
                      .map((t) => (
                        <article className="control-card" key={t.name}>
                          <div className="control-card-heading">
                            <ConnectorArt name={t.name} size={23} />
                            <strong>{t.name}</strong>
                            <span className="status-pill">{t.risk}</span>
                          </div>
                          <p>{t.description}</p>
                          <div className="tool-chips">
                            {t.capabilities?.map((c: string) => (
                              <span key={c}>{c}</span>
                            ))}
                          </div>
                          <details>
                            <summary>Input / output contracts</summary>
                            <pre>
                              {JSON.stringify(
                                {
                                  input: t.input_schema,
                                  output:
                                    t.output_schema || t.protocol_output_schema,
                                },
                                null,
                                2,
                              )}
                            </pre>
                          </details>
                          <div className="control-card-actions">
                            <button onClick={() => invoke(t)}>
                              {t.risk === "read"
                                ? "Invoke tool"
                                : "Request approval"}
                              <ArrowRight size={13} />
                            </button>
                            {t.id && (
                              <button
                                onClick={() =>
                                  action(
                                    () =>
                                      api.json("/tool-registry/" + t.id, {
                                        method: "DELETE",
                                      }),
                                    "Tool registration removed",
                                  )
                                }
                              >
                                Remove
                              </button>
                            )}
                          </div>
                        </article>
                      ))}
                  </div>
                  <div>
                    <form
                      className="control-card control-form"
                      onSubmit={(e) => {
                        e.preventDefault();
                        const form = e.currentTarget;
                        const d = Object.fromEntries(new FormData(form));
                        action(async () => {
                          await api.json("/tool-registry", {
                            method: "POST",
                            body: JSON.stringify({
                              name: d.name,
                              description: d.description,
                              adapter,
                              builtin: adapter === "builtin" ? d.builtin : null,
                              server_id: adapter === "mcp" ? serverId : null,
                              remote_tool:
                                adapter === "mcp" ? d.remote_tool : null,
                              capabilities: String(d.capabilities || "")
                                .split(",")
                                .map((x) => x.trim())
                                .filter(Boolean),
                              entities: String(d.entities || "")
                                .split(",")
                                .map((x) => x.trim())
                                .filter(Boolean),
                              enabled: true,
                            }),
                          });
                          form.reset();
                        }, "Persistent capability registered");
                      }}
                    >
                      <h3>
                        <Plus size={16} />
                        Register a capability
                      </h3>
                      <label>
                        Tool name
                        <input
                          name="name"
                          required
                          placeholder="evidence.compare"
                          pattern="[A-Za-z][A-Za-z0-9_.-]*"
                        />
                      </label>
                      <label>
                        Description
                        <input name="description" required maxLength={1000} />
                      </label>
                      <label>
                        Adapter
                        <select
                          value={adapter}
                          onChange={(e) => setAdapter(e.target.value)}
                        >
                          <option value="mcp">Discovered MCP tool</option>
                          <option value="builtin">
                            Existing built-in implementation
                          </option>
                        </select>
                      </label>
                      {adapter === "mcp" ? (
                        <>
                          <label>
                            Healthy server
                            <select
                              aria-label="Healthy server"
                              required
                              value={serverId}
                              onChange={(e) => setServerId(e.target.value)}
                            >
                              <option value="">
                                Choose a discovered server
                              </option>
                              {servers
                                .filter((s) => s.enabled && s.tools?.length)
                                .map((s) => (
                                  <option key={s.id} value={s.id}>
                                    {s.name}
                                  </option>
                                ))}
                            </select>
                          </label>
                          <label>
                            Discovered tool
                            <select
                              aria-label="Discovered tool"
                              required
                              name="remote_tool"
                            >
                              <option value="">Choose a tool</option>
                              {chosenServer?.tools?.map((t: any) => (
                                <option key={t.name} value={t.name}>
                                  {t.name}
                                </option>
                              ))}
                            </select>
                          </label>
                        </>
                      ) : (
                        <label>
                          Built-in implementation
                          <select name="builtin">
                            {tools
                              .filter(
                                (t) =>
                                  t.adapter === "builtin" && !t.registration_id,
                              )
                              .map((t) => (
                                <option key={t.name} value={t.name}>
                                  {t.name}
                                </option>
                              ))}
                          </select>
                        </label>
                      )}
                      <label>
                        Capabilities
                        <input
                          name="capabilities"
                          placeholder="analytics.compare, business.metrics"
                        />
                      </label>
                      <label>
                        Business entities
                        <input
                          name="entities"
                          placeholder="conversion, customer"
                        />
                      </label>
                      <button className="primary" disabled={busy}>
                        Register tool
                      </button>
                    </form>
                    {invoking && (
                      <form
                        className="control-card control-form"
                        onSubmit={(e) => {
                          e.preventDefault();
                          action(
                            async () => {
                              const body = {
                                arguments: JSON.parse(argumentsText),
                              };
                              const data = await api.json(
                                "/tool-registry/" +
                                  invoking.name +
                                  (invoking.risk === "read"
                                    ? "/invoke"
                                    : "/request-approval"),
                                { method: "POST", body: JSON.stringify(body) },
                              );
                              setResult(data);
                            },
                            invoking.risk === "read"
                              ? "Tool invocation completed"
                              : "Approval request saved",
                          );
                        }}
                      >
                        <h3>{invoking.name}</h3>
                        <label>
                          Validated arguments
                          <textarea
                            aria-label="Tool arguments"
                            className="code-editor"
                            value={argumentsText}
                            onChange={(e) => setArgumentsText(e.target.value)}
                          />
                        </label>
                        <button className="primary" disabled={busy}>
                          {invoking.risk === "read"
                            ? "Run validated tool"
                            : "Submit for human approval"}
                        </button>
                        {result && (
                          <pre className="tool-result">
                            {JSON.stringify(result, null, 2)}
                          </pre>
                        )}
                      </form>
                    )}
                  </div>
                </div>
                <h3>Human approval queue</h3>
                {!approvals.length && (
                  <div className="control-empty">
                    No tool actions are waiting for a decision.
                  </div>
                )}
                {approvals.map((a) => (
                  <article className="control-card" key={a.id}>
                    <div className="control-card-heading">
                      <strong>{a.tool}</strong>
                      <span className="status-pill">
                        {a.state.replaceAll("_", " ")}
                      </span>
                    </div>
                    <pre>{JSON.stringify(a.arguments, null, 2)}</pre>
                    {a.state === "WAITING_FOR_APPROVAL" && (
                      <div className="control-card-actions">
                        <button
                          className="primary"
                          disabled={busy}
                          onClick={() =>
                            action(
                              () =>
                                api.json(
                                  "/tool-approvals/" + a.id + "/decision",
                                  {
                                    method: "POST",
                                    body: JSON.stringify({ approve: true }),
                                  },
                                ),
                              "Approved action executed once",
                            )
                          }
                        >
                          Approve & execute
                        </button>
                        <button
                          disabled={busy}
                          onClick={() =>
                            action(
                              () =>
                                api.json(
                                  "/tool-approvals/" + a.id + "/decision",
                                  {
                                    method: "POST",
                                    body: JSON.stringify({ approve: false }),
                                  },
                                ),
                              "Action rejected",
                            )
                          }
                        >
                          Reject
                        </button>
                      </div>
                    )}
                    {a.result && (
                      <details>
                        <summary>Execution result</summary>
                        <pre>{JSON.stringify(a.result, null, 2)}</pre>
                      </details>
                    )}
                    {a.error && <p className="control-error">{a.error}</p>}
                  </article>
                ))}
              </>
            )}
            {tab === "harness" && (
              <>
                <div className="control-title">
                  <span className="eyebrow">EXECUTION RUNTIME</span>
                  <h2>From goal to governed execution.</h2>
                  <p>
                    Generate a task decomposition, edit its graph, and inspect
                    real checkpoints. Branches, joins, retries and loops run
                    within explicit budgets.
                  </p>
                </div>
                <div className="control-columns">
                  <div>
                    <form
                      className="control-card control-form"
                      onSubmit={(e) => {
                        e.preventDefault();
                        action(async () => {
                          if (!conversation)
                            throw Error(
                              "Open a conversation with evidence first",
                            );
                          const plan = await api.json("/harness/plan", {
                            method: "POST",
                            body: JSON.stringify({
                              goal,
                              conversation_id: conversation.id,
                              mode,
                            }),
                          });
                          setGraphText(
                            JSON.stringify(plan.definition, null, 2),
                          );
                          setSubgoals(plan.subgoals);
                          setGraphId("");
                        }, "Goal decomposed into executable subgoals");
                      }}
                    >
                      <h3>Decompose a goal</h3>
                      <label>
                        Business goal
                        <textarea
                          value={goal}
                          onChange={(e) => setGoal(e.target.value)}
                          required
                          minLength={3}
                        />
                      </label>
                      <label>
                        Agent model
                        <select
                          value={mode}
                          onChange={(e) => setMode(e.target.value)}
                        >
                          <option value="evidence">
                            Deterministic evidence
                          </option>
                          <option value="default">
                            Per-agent vault routes
                          </option>
                          <option value="local">Local AI · no key</option>
                        </select>
                      </label>
                      <small>
                        {conversation
                          ? "Evidence scope: " + conversation.title
                          : "Open a business conversation to provide an authorized evidence scope."}
                      </small>
                      <button
                        className="primary"
                        disabled={busy || !conversation}
                      >
                        Generate execution plan
                      </button>
                    </form>
                    {!!subgoals.length && (
                      <div className="control-card subgoal-plan">
                        {subgoals.map((g, i) => (
                          <div key={g.node}>
                            <span>{String(i + 1).padStart(2, "0")}</span>
                            <div>
                              <strong>{g.node}</strong>
                              <p>{g.purpose}</p>
                            </div>
                            <span className="status-pill">{g.type}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <label>
                      Saved graphs
                      <select
                        value={graphId}
                        onChange={(e) => {
                          const graph = graphs.find(
                            (g) => g.id === e.target.value,
                          );
                          if (graph) {
                            const { id, ...definition } = graph;
                            setGraphId(id);
                            setGraphText(JSON.stringify(definition, null, 2));
                            setSubgoals([]);
                          }
                        }}
                      >
                        <option value="">New graph</option>
                        {graphs.map((g) => (
                          <option key={g.id} value={g.id}>
                            {g.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    {graphText && (
                      <form
                        className="control-card control-form"
                        onSubmit={(e) => {
                          e.preventDefault();
                          action(async () => {
                            const graph = await api.json(
                              "/harness/graphs" +
                                (graphId ? "/" + graphId : ""),
                              {
                                method: graphId ? "PUT" : "POST",
                                body: JSON.stringify(JSON.parse(graphText)),
                              },
                            );
                            setGraphId(graph.id);
                          }, "Graph validated and saved");
                        }}
                      >
                        <label>
                          Executable graph definition
                          <textarea
                            className="code-editor graph-editor"
                            aria-label="Graph definition"
                            value={graphText}
                            onChange={(e) => setGraphText(e.target.value)}
                          />
                        </label>
                        <div className="control-card-actions">
                          <button className="primary" disabled={busy}>
                            Save graph
                          </button>
                          {graphId && (
                            <button
                              type="button"
                              disabled={busy || !conversation}
                              onClick={() =>
                                action(async () => {
                                  const run = await api.json(
                                    "/harness/graphs/" + graphId + "/run",
                                    {
                                      method: "POST",
                                      body: JSON.stringify({
                                        conversation_id: conversation!.id,
                                      }),
                                    },
                                  );
                                  setActive(run);
                                  startWatch(run.id);
                                }, "Graph execution started")
                              }
                            >
                              Run graph
                              <Play size={13} />
                            </button>
                          )}
                        </div>
                      </form>
                    )}
                  </div>
                  <div>
                    <h3>Execution inspector</h3>
                    {!active && (
                      <div className="control-empty">
                        Run a saved graph to watch its actual nodes,
                        checkpoints, approvals and budgets.
                      </div>
                    )}
                    {active && (
                      <article className="control-card">
                        <div className="control-card-heading">
                          <strong>{active.definition?.name}</strong>
                          <span
                            className={
                              "status-pill " +
                              (active.state === "COMPLETED" ? "healthy" : "")
                            }
                          >
                            {active.state.replaceAll("_", " ")}
                          </span>
                        </div>
                        <div className="execution-metrics">
                          <span>
                            {active.graph_checkpoint?.steps || 0} steps
                          </span>
                          <span>
                            {active.graph_checkpoint?.tools_used || 0} tool
                            calls
                          </span>
                          <span>
                            {active.graph_checkpoint?.tokens_reserved || 0}{" "}
                            token budget reserved
                          </span>
                        </div>
                        <div className="control-events">
                          {active.events?.map((event: any, i: number) => (
                            <div key={i}>
                              <Check size={12} />
                              <span>
                                <strong>{event.stage}</strong>
                                {event.detail}
                              </span>
                            </div>
                          ))}
                        </div>
                        {pending && active.state === "WAITING_FOR_APPROVAL" && (
                          <section className="approval">
                            <h3>Review exact action arguments</h3>
                            <p>
                              {pending.tool || pending.node} · {pending.risk}
                            </p>
                            <pre>
                              {JSON.stringify(pending.arguments, null, 2)}
                            </pre>
                            <div className="control-card-actions">
                              {[true, false].map((approve) => (
                                <button
                                  key={String(approve)}
                                  className={approve ? "primary" : ""}
                                  disabled={busy}
                                  onClick={() =>
                                    action(
                                      async () => {
                                        const run = await api.json(
                                          "/harness/executions/" +
                                            active.id +
                                            "/decision",
                                          {
                                            method: "POST",
                                            body: JSON.stringify({
                                              approve,
                                              binding: pending.binding,
                                            }),
                                          },
                                        );
                                        setActive(run);
                                        if (run.state === "CREATED")
                                          startWatch(run.id);
                                      },
                                      approve
                                        ? "Action approved; graph resumed"
                                        : "Action rejected",
                                    )
                                  }
                                >
                                  {approve ? "Approve & continue" : "Reject"}
                                </button>
                              ))}
                            </div>
                          </section>
                        )}
                        {active.error && (
                          <p className="control-error">{active.error}</p>
                        )}
                        {active.output && (
                          <details open={active.state === "COMPLETED"}>
                            <summary>Actual execution output</summary>
                            <pre>{active.output}</pre>
                          </details>
                        )}
                        {["CREATED", "RUNNING"].includes(active.state) && (
                          <button
                            onClick={() =>
                              action(async () => {
                                setActive(
                                  await api.json(
                                    "/executions/" + active.id + "/cancel",
                                    { method: "POST" },
                                  ),
                                );
                              }, "Graph cancelled")
                            }
                          >
                            Cancel execution
                          </button>
                        )}
                      </article>
                    )}
                    <h3>Persistent execution history</h3>
                    {executions.slice(0, 10).map((run) => (
                      <button
                        className="execution-history"
                        key={run.id}
                        onClick={() => {
                          setActive(run);
                          if (["CREATED", "RUNNING"].includes(run.state))
                            startWatch(run.id);
                        }}
                      >
                        <Workflow size={15} />
                        <span>
                          {run.definition?.name}
                          <small>{run.state}</small>
                        </span>
                        <ArrowRight size={14} />
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
            {tab === "governance" && policy && (
              <>
                <div className="control-title">
                  <span className="eyebrow">BACKEND POLICY LAYER</span>
                  <h2>Set the boundaries. Keep control.</h2>
                  <p>
                    These rules are evaluated during actual resource access and
                    tool execution. Model output cannot change them.
                  </p>
                </div>
                <div className="control-columns">
                  <form
                    className="control-card control-form"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const d = Object.fromEntries(
                        new FormData(e.currentTarget),
                      );
                      action(
                        () =>
                          api.json("/governance/policy", {
                            method: "PUT",
                            body: JSON.stringify({
                              tool_allowlist: String(d.tool_allowlist)
                                .split(",")
                                .map((v) => v.trim())
                                .filter(Boolean),
                              denied_tools: String(d.denied_tools)
                                .split(",")
                                .map((v) => v.trim())
                                .filter(Boolean),
                              max_tool_risk: d.max_tool_risk,
                              max_tool_calls: Number(d.max_tool_calls),
                              max_run_seconds: Number(d.max_run_seconds),
                              allow_external_processing:
                                d.allow_external_processing === "on",
                              allowed_mcp_hosts: String(d.allowed_mcp_hosts)
                                .split(",")
                                .map((v) => v.trim())
                                .filter(Boolean),
                            }),
                          }),
                        "Organization governance policy saved",
                      );
                    }}
                  >
                    <h3>Organization execution policy</h3>
                    <label>
                      Allowed tools
                      <input
                        name="tool_allowlist"
                        defaultValue={policy.tool_allowlist.join(", ")}
                        placeholder="* or comma-separated tool names"
                      />
                    </label>
                    <label>
                      Denied tools
                      <input
                        name="denied_tools"
                        defaultValue={policy.denied_tools.join(", ")}
                      />
                    </label>
                    <label>
                      Maximum risk
                      <select
                        name="max_tool_risk"
                        defaultValue={policy.max_tool_risk}
                      >
                        <option value="read">Read only</option>
                        <option value="internal_write">
                          Internal writes with approval
                        </option>
                        <option value="external_write">
                          External writes with approval
                        </option>
                        <option value="critical">
                          Critical actions with approval
                        </option>
                      </select>
                    </label>
                    <div className="control-form-row">
                      <label>
                        Tool-call budget
                        <input
                          name="max_tool_calls"
                          type="number"
                          min={1}
                          max={64}
                          defaultValue={policy.max_tool_calls}
                        />
                      </label>
                      <label>
                        Run duration (seconds)
                        <input
                          name="max_run_seconds"
                          type="number"
                          min={10}
                          max={600}
                          defaultValue={policy.max_run_seconds}
                        />
                      </label>
                    </div>
                    <label className="control-checkbox">
                      <input
                        name="allow_external_processing"
                        type="checkbox"
                        defaultChecked={policy.allow_external_processing}
                      />
                      Allow explicitly selected remote providers
                    </label>
                    <label>
                      Approved remote MCP hostnames
                      <input
                        name="allowed_mcp_hosts"
                        defaultValue={policy.allowed_mcp_hosts.join(", ")}
                        placeholder="mcp.example.com"
                      />
                    </label>
                    <small>
                      Approval is always required for consequential tools,
                      regardless of this policy's risk ceiling.
                    </small>
                    <button className="primary" disabled={busy}>
                      <Shield size={14} />
                      Save governance policy
                    </button>
                  </form>
                  <div>
                    <h3>Project resource access</h3>
                    {!projects.length && (
                      <div className="control-empty">
                        Create a business project to configure its member-level
                        access.
                      </div>
                    )}
                    {projects.map((p) => (
                      <form
                        className="control-card control-form"
                        key={p.id}
                        onSubmit={(e) => {
                          e.preventDefault();
                          const d = new FormData(e.currentTarget);
                          action(
                            () =>
                              api.json("/projects/" + p.id + "/access", {
                                method: "PUT",
                                body: JSON.stringify({
                                  access: d.get("access"),
                                  members: d.getAll("members"),
                                }),
                              }),
                            "Project resource access updated",
                          );
                        }}
                      >
                        <h3>{p.name}</h3>
                        <p>{p.goal}</p>
                        <label>
                          Visibility
                          <select
                            name="access"
                            defaultValue={p.access || "organization"}
                          >
                            <option value="organization">
                              Organization members
                            </option>
                            <option value="restricted">
                              Selected members and administrators
                            </option>
                          </select>
                        </label>
                        {members.map((member) => (
                          <label className="control-checkbox" key={member.id}>
                            <input
                              type="checkbox"
                              name="members"
                              value={member.id}
                              defaultChecked={p.members?.includes(member.id)}
                            />
                            <span>
                              {member.name}
                              <small>
                                {member.email} · {member.role}
                              </small>
                            </span>
                          </label>
                        ))}
                        <button className="primary" disabled={busy}>
                          Save project access
                        </button>
                      </form>
                    ))}
                    <div className="control-card control-safeguards">
                      <Shield size={22} />
                      <h3>Enforced at every boundary</h3>
                      <p>
                        Organization scope · Project membership · Tool allowlist
                        · Input/output schemas · Risk ceiling · Argument-bound
                        approval · Runtime budgets · Private-network protection
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}
          </main>
        </div>
      </section>
    </div>
  );
}
