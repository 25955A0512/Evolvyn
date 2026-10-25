import { useEffect, useState } from "react";
import {
  Plus,
  KeyRound,
  ShieldCheck,
  Search,
} from "lucide-react";
import type { client } from "../api";
import { ConnectorArt } from "./ConnectorGallery";
import { WorkspaceDialog } from "./WorkspaceDialog";
const providers: Record<string, string> = {
  gemini: "Google Gemini",
  groq: "Groq",
  provider: "OpenAI",
  openrouter: "OpenRouter",
  mcp: "MCP connection",
};
export function KeyVaultPanel({ api }: { api: ReturnType<typeof client> }) {
  const [data, setData] = useState<any>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [query, setQuery] = useState(""),
    [tab, setTab] = useState("keys");
  const [modal, setModal] = useState(""),
    [selected, setSelected] = useState<any>(null),
    [provider, setProvider] = useState("gemini"),
    [models, setModels] = useState<any[]>([]),
    [model, setModel] = useState("");
  async function load() {
    setData(await api.json("/vault"));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  async function act(fn: () => Promise<void>, message = "Saved") {
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
  function openAdd(c?: any) {
    setSelected(c || null);
    setProvider(c?.provider || "gemini");
    setModal("key");
    setError("");
  }
  async function chooseModel(c: any) {
    setSelected(c);
    setModels([]);
    setModel("");
    setModal("models");
    await act(async () => {
      const r = await api.json("/vault/credentials/" + c.id + "/models", {
        method: "POST",
      });
      setModels(r.models);
      if (!r.models.length)
        throw Error("No generation models available for this key.");
    }, "Models loaded");
  }
  async function test(agent: string) {
    await act(async () => {
      const r = await api.json("/agents/" + agent + "/test", {
        method: "POST",
      });
      if (!r.available) throw Error(r.reason);
    }, "Model route responded successfully");
  }
  const keys = data?.credentials || [],
    active = keys.filter((c: any) => c.enabled),
    routes = data?.effective_routes || {},
    defaultRoute =
      data?.bindings.find((r: any) => r.agent === "default") ||
      (Object.entries(routes).find(
        ([agent]) => !data?.bindings.some((r: any) => r.agent === agent),
      )?.[1] as any);
  const close = () => {
    if (!busy) {
      setModal("");
      setSelected(null);
      setError("");
    }
  };
  return (
    <div className="studio-page dashboard-page vault-dashboard">
      <header className="dashboard-heading">
        <div>
          <span className="dashboard-kicker">WORKSPACE</span>
          <h1>Key vault</h1>
          <p>Models and secure connections.</p>
        </div>
        <button
          className="studio-primary"
          disabled={!data || busy || !data.ready}
          onClick={() => openAdd()}
        >
          <Plus size={17} />
          Add key
        </button>
      </header>
      {error && !modal && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="dashboard-notice" role="status">
          {notice}
        </p>
      )}
      {!data ? (
        <p role="status">Loading keys…</p>
      ) : (
        <>
          <section className="dashboard-stat-grid" aria-label="Vault summary">
            <article>
              <KeyRound size={18} />
              <span>Saved keys</span>
              <strong>{keys.length}</strong>
            </article>
            <article>
              <ShieldCheck size={18} />
              <span>Enabled</span>
              <strong>{active.length}</strong>
            </article>
            <article>
              <span>Agent routes</span>
              <strong>{Object.keys(routes).length}</strong>
            </article>
            <article className="default-model-stat">
              <span>Default model</span>
              <strong>
                {defaultRoute?.model ||
                  defaultRoute?.resolved_model ||
                  (defaultRoute ? "Provider default" : "Not configured")}
              </strong>
              <button disabled={busy} onClick={() => setTab("routes")}>
                Agent routes
              </button>
            </article>
          </section>
          {!data.ready && (
            <p className="error" role="alert">
              Vault encryption needs administrator setup.
            </p>
          )}
          <div className="dashboard-toolbar">
            <nav aria-label="Vault sections">
              <button
                aria-current={tab === "keys" ? "page" : undefined}
                onClick={() => setTab("keys")}
              >
                API keys <span>{keys.length}</span>
              </button>
              <button
                aria-current={tab === "routes" ? "page" : undefined}
                onClick={() => setTab("routes")}
              >
                Agent routes
              </button>
            </nav>
            <label className="dashboard-search">
              <Search size={17} />
              <input
                aria-label="Search keys"
                placeholder="Search keys"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
          </div>
          {tab === "keys" ? (
            <div className="dashboard-connector-grid">
              {keys
                .filter((c: any) =>
                  (c.name + " " + c.provider)
                    .toLowerCase()
                    .includes(query.toLowerCase()),
                )
                .map((c: any) => (
                  <article className="dashboard-connector-card" key={c.id}>
                    <div className="dashboard-card-head">
                      <ConnectorArt name={c.provider} size={26} />
                      <span
                        className={
                          "dashboard-status " + (c.enabled ? "" : "muted")
                        }
                      >
                        {c.enabled ? "Saved" : "Revoked"}
                      </span>
                    </div>
                    <h3>{c.name}</h3>
                    <p>{providers[c.provider] || c.provider}</p>
                    <div className="key-mask">
                      <KeyRound size={14} />
                      <span>Encrypted key</span>
                      <small>v{c.version}</small>
                    </div>
                    <footer>
                      <button disabled={busy} onClick={() => openAdd(c)}>
                        Replace
                      </button>
                      {c.enabled && c.provider === "gemini" && (
                        <button
                          aria-label="Load available models"
                          disabled={busy}
                          onClick={() => chooseModel(c)}
                        >
                          Models
                        </button>
                      )}
                      {c.enabled &&
                        c.provider !== "mcp" &&
                        c.provider !== "gemini" && (
                          <button
                            disabled={busy}
                            onClick={() =>
                              act(async () => {
                                await api.json("/vault/workspace-default", {
                                  method: "PUT",
                                  body: JSON.stringify({
                                    provider: c.provider,
                                    credential_id: c.id,
                                    reset_agent_overrides: true,
                                  }),
                                });
                              }, "All agents now inherit this key")
                            }
                          >
                            Use for all agents
                          </button>
                        )}
                      {c.enabled && (
                        <button
                          className="danger-text"
                          aria-label={"Revoke " + c.name}
                          onClick={() => {
                            setSelected(c);
                            setModal("revoke");
                          }}
                        >
                          Revoke
                        </button>
                      )}
                    </footer>
                  </article>
                ))}
              {!keys.length && (
                <button
                  className="dashboard-empty-card"
                  onClick={() => openAdd()}
                >
                  <Plus size={28} />
                  <strong>Add your first key</strong>
                  <span>Gemini, Groq, OpenAI or an MCP token.</span>
                </button>
              )}
            </div>
          ) : (
            <section className="dashboard-table-panel">
              <div className="dashboard-card-head">
                <h2>Agent routes</h2>
                {data.bindings.some((r: any) => r.agent === "default") && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      act(async () => {
                        await api.json("/vault/bindings/default", {
                          method: "DELETE",
                        });
                      }, "Workspace default reset")
                    }
                  >
                    Reset default
                  </button>
                )}
                <button
                  onClick={() => {
                    setProvider("gemini");
                    setModal("route");
                  }}
                >
                  <Plus size={16} />
                  Add override
                </button>
              </div>
              <div className="dashboard-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Agent</th>
                      <th>Provider / model</th>
                      <th>Routing</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(routes).map(
                      ([agent, route]: [string, any]) => (
                        <tr key={agent}>
                          <td>{data.agents[agent] || agent}</td>
                          <td>
                            {providers[route.provider] || route.provider}
                            <small>
                              {route.resolved_model || "Evidence rules"}
                            </small>
                          </td>
                          <td>
                            {data.bindings.some((r: any) => r.agent === agent)
                              ? "Override"
                              : "Workspace default"}
                          </td>
                          <td>
                            <button disabled={busy} onClick={() => test(agent)}>
                              Test
                            </button>
                            {data.bindings.some(
                              (r: any) => r.agent === agent,
                            ) && (
                              <button
                                disabled={busy}
                                onClick={() =>
                                  act(async () => {
                                    await api.json("/vault/bindings/" + agent, {
                                      method: "DELETE",
                                    });
                                  }, "Agent uses workspace default")
                                }
                              >
                                Reset
                              </button>
                            )}
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          <p className="dashboard-footnote">
            <ShieldCheck size={14} />
            Encrypted at rest. Keys are never displayed.
          </p>
        </>
      )}
      {modal && (
        <WorkspaceDialog
          title={
            modal === "key"
              ? selected
                ? "Replace key"
                : "Add a key"
              : modal === "models"
                ? "Choose a model"
                : modal === "revoke"
                  ? "Revoke key?"
                  : "Model route"
          }
          onClose={close}
        >
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {modal === "key" && (
            <form
              className="dashboard-dialog-form"
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                act(async () => {
                  await api.json(
                    "/vault/credentials" + (selected ? "/" + selected.id : ""),
                    {
                      method: selected ? "PUT" : "POST",
                      body: JSON.stringify({
                        name: f.get("name") || providers[provider] + " key",
                        provider,
                        value: f.get("value"),
                      }),
                    },
                  );
                  setModal("");
                  setSelected(null);
                }, "Key saved");
              }}
            >
              <label>
                Provider
                <select
                  aria-label="Credential provider"
                  disabled={!!selected}
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                >
                  {Object.entries(providers).map(([id, name]) => (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                API key
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
              <label>
                Display name <small>optional</small>
                <input
                  aria-label="Credential name"
                  name="name"
                  defaultValue={selected?.name || ""}
                  maxLength={100}
                  placeholder="Production key"
                />
              </label>
              <p className="dashboard-footnote">
                Encrypted and stored in your workspace.
              </p>
              <footer>
                <button type="button" disabled={busy} onClick={close}>
                  Cancel
                </button>
                <button
                  className="studio-primary"
                  disabled={busy || !data?.ready}
                >
                  {busy ? "Saving…" : "Save key"}
                </button>
              </footer>
            </form>
          )}
          {modal === "models" && (
            <div className="dashboard-dialog-form">
              <div className="dashboard-selected-provider">
                <ConnectorArt name={selected?.provider || "gemini"} />
                <div>
                  <strong>{selected?.name}</strong>
                  <small>Google Gemini</small>
                </div>
              </div>
              {busy ? (
                <p>Loading models…</p>
              ) : (
                <label>
                  Available model
                  <select
                    aria-label={"Available Gemini model: " + selected?.name}
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                  >
                    <option value="">Select a model</option>
                    {models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.id}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <p className="dashboard-footnote">
                Applies this key and model to every agent.
              </p>
              <footer>
                <button disabled={busy} onClick={close}>
                  Cancel
                </button>
                <button
                  className="studio-primary"
                  disabled={busy || !model}
                  onClick={() =>
                    act(async () => {
                      await api.json("/vault/workspace-default", {
                        method: "PUT",
                        body: JSON.stringify({
                          provider: "gemini",
                          credential_id: selected.id,
                          model,
                          reset_agent_overrides: true,
                        }),
                      });
                      setModal("");
                    }, "All agents now inherit this key")
                  }
                >
                  Use for all agents
                </button>
              </footer>
            </div>
          )}
          {modal === "route" && (
            <form
              className="dashboard-dialog-form"
              onSubmit={(e) => {
                e.preventDefault();
                const f = Object.fromEntries(new FormData(e.currentTarget));
                act(async () => {
                  await api.json("/vault/bindings/" + f.agent, {
                    method: "PUT",
                    body: JSON.stringify({
                      provider,
                      credential_id: f.credential_id || null,
                      model: f.model || "",
                    }),
                  });
                  setModal("");
                }, "Route saved");
              }}
            >
              <label>
                Agent
                <select name="agent" aria-label="Model route agent">
                  <option value="default">Workspace default</option>
                  {Object.entries(data?.agents || {}).map(([id, name]) => (
                    <option key={id} value={id}>
                      {String(name)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Provider
                <select
                  aria-label="Route provider"
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                >
                  {Object.entries(providers)
                    .filter(([p]) => p !== "mcp")
                    .map(([id, name]) => (
                      <option key={id} value={id}>
                        {name}
                      </option>
                    ))}
                  <option value="local">Local model</option>
                  <option value="evidence">Evidence rules</option>
                </select>
              </label>
              <label>
                Key
                <select
                  name="credential_id"
                  aria-label="Route credential"
                  key={provider}
                  disabled={provider === "local" || provider === "evidence"}
                  required={provider !== "local" && provider !== "evidence"}
                >
                  <option value="">Select key</option>
                  {active
                    .filter((c: any) => c.provider === provider)
                    .map((c: any) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Model
                <input
                  name="model"
                  aria-label="Route model"
                  placeholder="Provider default"
                  maxLength={150}
                />
              </label>
              <footer>
                <button type="button" disabled={busy} onClick={close}>
                  Cancel
                </button>
                <button className="studio-primary" disabled={busy}>
                  Save route
                </button>
              </footer>
            </form>
          )}
          {modal === "revoke" && (
            <div className="dashboard-dialog-form">
              <p>{selected?.name} will stop working for its assigned agents.</p>
              <footer>
                <button disabled={busy} onClick={close}>
                  Cancel
                </button>
                <button
                  className="studio-primary"
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      await api.json("/vault/credentials/" + selected.id, {
                        method: "DELETE",
                      });
                      setModal("");
                    }, "Key revoked")
                  }
                >
                  Revoke key
                </button>
              </footer>
            </div>
          )}
        </WorkspaceDialog>
      )}
    </div>
  );
}
