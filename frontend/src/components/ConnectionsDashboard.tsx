import { useEffect, useState } from "react";
import {
  Plus,
  Search,
  RefreshCw,
  Workflow,
  Server,
  ShieldCheck,
} from "lucide-react";
import type { client } from "../api";
import type { ManageConnections } from "./ToolAccess";
import { AuthorizedConnections } from "./AuthorizedConnections";
import { ConnectorArt, ConnectorGallery } from "./ConnectorGallery";
export function ConnectionsDashboard({
  api,
  onManage,
}: {
  api: ReturnType<typeof client>;
  onManage: ManageConnections;
}) {
  const [servers, setServers] = useState<any[]>([]),
    [loaded, setLoaded] = useState(false),
    [tools, setTools] = useState<any[]>([]),
    [tab, setTab] = useState("connected"),
    [query, setQuery] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  async function load() {
    const [a, b] = await Promise.all([
      api.json("/mcp/servers"),
      api.json("/tool-registry"),
    ]);
    setServers(a);
    setTools(b);
    setLoaded(true);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const visible = servers.filter((s) =>
    (s.name + " " + s.profile + " " + (s.url || ""))
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <div className="studio-page dashboard-page connections-dashboard">
      <header className="dashboard-heading">
        <div>
          <span className="dashboard-kicker">WORKSPACE</span>
          <h1>Connections</h1>
          <p>Your accounts, MCP servers and tools.</p>
        </div>
        <button className="studio-primary" onClick={() => setTab("discover")}>
          <Plus size={17} />
          Add connection
        </button>
      </header>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="dashboard-notice" role="status">
          {notice}
        </p>
      )}
      <section className="dashboard-stat-grid" aria-label="Connection summary">
        {[
          [Server, "MCP servers", servers.length],
          [
            ShieldCheck,
            "MCP ready",
            servers.filter((s) => s.enabled && s.status === "healthy").length,
          ],
          [Workflow, "Registered tools", tools.length],
          [
            ShieldCheck,
            "Read-only tools",
            tools.filter((t) => t.risk === "read").length,
          ],
        ].map(([Icon, label, value]: any) => (
          <article key={label}>
            <Icon size={18} />
            <span>{label}</span>
            <strong>{loaded ? value : "—"}</strong>
          </article>
        ))}
      </section>
      <div className="dashboard-toolbar">
        <nav aria-label="Connection sections">
          {[
            ["connected", "Connected"],
            ["discover", "Discover"],
            ["tools", "Tools"],
          ].map(([id, label]) => (
            <button
              key={id}
              aria-current={tab === id ? "page" : undefined}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </nav>
        {tab !== "discover" && (
          <label className="dashboard-search">
            <Search size={16} />
            <input
              aria-label="Search integrations"
              placeholder="Search connections"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        )}
      </div>
      {tab === "connected" && (
        <>
          <AuthorizedConnections api={api} />
          <a className="dashboard-social-link" href="/growth?social=connect">
            <ConnectorArt name="Instagram" />
            <span>
              <strong>Instagram</strong>
              <small>Professional account analytics</small>
            </span>
            <span>Connect →</span>
          </a>
          <div className="dashboard-connector-grid">
            {visible.map((s) => (
              <article className="dashboard-connector-card" key={s.id}>
                <div className="dashboard-card-head">
                  <ConnectorArt name={s.name + " " + s.profile} />
                  <span
                    className={
                      "dashboard-status " +
                      (!s.enabled || s.status !== "healthy" ? "muted" : "")
                    }
                  >
                    {!s.enabled
                      ? "Disabled"
                      : s.status === "healthy"
                        ? "MCP ready"
                        : s.status === "unavailable"
                          ? "Needs attention"
                          : "Not checked"}
                  </span>
                </div>
                <h3>{s.name}</h3>
                <p>{s.transport === "stdio" ? s.profile : s.url}</p>
                <div className="dashboard-card-meta">
                  <span>{s.tools?.length || 0} tools</span>
                  <span>
                    {s.last_checked_at
                      ? new Date(s.last_checked_at).toLocaleString()
                      : "No check yet"}
                  </span>
                </div>
                {s.last_error && <p className="error">{s.last_error}</p>}
                <footer>
                  <button
                    disabled={busy || !s.enabled}
                    onClick={() =>
                      act(async () => {
                        await api.json("/mcp/servers/" + s.id + "/probe", {
                          method: "POST",
                        });
                        setNotice("MCP check complete");
                      })
                    }
                  >
                    <RefreshCw size={15} />
                    Check
                  </button>
                  <button onClick={() => onManage("servers", s.name)}>
                    Manage
                  </button>
                </footer>
              </article>
            ))}
            {!servers.length && (
              <button
                className="dashboard-empty-card"
                onClick={() => onManage("servers")}
              >
                <Plus size={26} />
                <strong>Connect an MCP server</strong>
                <span>Add an authorized endpoint.</span>
              </button>
            )}
          </div>
          <p className="dashboard-footnote">
            MCP readiness confirms discovery. Account access is verified when a
            tool reads provider data.
          </p>
        </>
      )}
      {tab === "discover" && (
        <ConnectorGallery
          servers={servers}
          busy={busy}
          onConfigure={(name) =>
            name.toLowerCase().includes("instagram")
              ? location.assign("/growth?social=connect")
              : onManage("servers", name)
          }
          onBundled={(name, profile) =>
            act(async () => {
              const s =
                servers.find((r) => r.profile === profile) ||
                (await api.json("/mcp/servers", {
                  method: "POST",
                  body: JSON.stringify({ name, profile, transport: "stdio" }),
                }));
              await api.json("/mcp/servers/" + s.id + "/probe", {
                method: "POST",
              });
              setNotice("MCP check complete");
            })
          }
        />
      )}
      {tab === "tools" && (
        <section className="dashboard-table-panel">
          <div className="dashboard-card-head">
            <h2>Available tools</h2>
            <button onClick={() => onManage("tools")}>Manage registry</button>
          </div>
          <div className="dashboard-table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Tool</th>
                  <th>Source</th>
                  <th>Access</th>
                </tr>
              </thead>
              <tbody>
                {tools
                  .filter((t) =>
                    (t.name + " " + t.description)
                      .toLowerCase()
                      .includes(query.toLowerCase()),
                  )
                  .map((t) => (
                    <tr key={t.name}>
                      <td>
                        <strong>{t.name}</strong>
                        <small>{t.description}</small>
                      </td>
                      <td>{t.adapter === "mcp" ? "MCP" : "Built-in"}</td>
                      <td>
                        <span className="dashboard-status">
                          {t.risk.replaceAll("_", " ")}
                        </span>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
