import { AuthorizedConnections } from "./AuthorizedConnections";
import { ConnectorGallery, ConnectorArt } from "./ConnectorGallery";
import { useEffect, useRef, useState } from "react";
import { UiIcon } from "./UiIcon";
import {
  X,
  Server,
  Shield,
  Blocks,
  Check,
  RefreshCw,
  Plus,
  ArrowRight,
} from "lucide-react";
import type { client } from "../api";
import type { Convo } from "../types";
type Tab = "servers" | "tools";
export function AgentControlCenter({
  api,
  conversation,
  onClose,
  onRefresh,
  initialTab = "servers",
  initialServerName,
}: {
  api: ReturnType<typeof client>;
  conversation: Convo | null;
  onClose: () => void;
  onRefresh: () => void;
  initialTab?: Tab;
  initialServerName?: string;
}) {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [servers, setServers] = useState<any[]>([]);
  const [tools, setTools] = useState<any[]>([]);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [credentialPrefix, setCredentialPrefix] = useState("EVOLVYN_MCP_");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [transport, setTransport] = useState("stdio");
  const [adapter, setAdapter] = useState("mcp");
  const [serverId, setServerId] = useState("");
  const [invoking, setInvoking] = useState<any>(null);
  const [argumentsText, setArgumentsText] = useState("{}");
  const [result, setResult] = useState<any>(null);
  const serverForm = useRef<HTMLFormElement | null>(null);
  useEffect(() => {
    if (!initialServerName) return;
    setTransport("streamable_http");
    const frame = requestAnimationFrame(() => {
      serverForm.current?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
      const input =
        serverForm.current?.querySelector<HTMLInputElement>("input[name=name]");
      if (input) {
        input.value = initialServerName;
        input.focus();
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [initialServerName]);
  const [toolSearch, setToolSearch] = useState("");
  const fail = (e: unknown) =>
    setError(e instanceof Error ? e.message : String(e));
  async function load() {
    const [servers, tools, approvals, prefix] = await Promise.all([
      api.json("/mcp/servers"),
      api.json("/tool-registry"),
      api.json("/tool-approvals"),
      api.json("/mcp/credential-prefix"),
    ]);
    setServers(servers);
    setTools(tools);
    setApprovals(approvals);
    setCredentialPrefix(prefix.prefix);
  }
  useEffect(() => {
    load().catch(fail);
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
                <AuthorizedConnections
                  api={api}
                  onChange={() => load().catch(fail)}
                />
                <ConnectorGallery
                  busy={busy}
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
                    {[...servers]
                      .sort(
                        (a, b) =>
                          Number(b.enabled && b.status === "healthy") -
                          Number(a.enabled && a.status === "healthy"),
                      )
                      .map((s) => (
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
                                    api.json(
                                      "/mcp/servers/" + s.id + "/probe",
                                      {
                                        method: "POST",
                                      },
                                    ),
                                  "Server health and discovery refreshed",
                                )
                              }
                            >
                              <RefreshCw size={13} />
                              Check health
                            </button>
                            {[
                              "google_drive",
                              "slack",
                              "shopify",
                              "github",
                            ].includes(s.profile) ? (
                              <a href="/integrations">Manage account</a>
                            ) : (
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
                                              .concat([
                                                ["enabled", !s.enabled],
                                              ]),
                                          ),
                                        ),
                                      }),
                                    "Server availability updated",
                                  )
                                }
                              >
                                {s.enabled ? "Disable" : "Enable"}
                              </button>
                            )}
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
          </main>
        </div>
      </section>
    </div>
  );
}
