import { useEffect, useState } from "react";
import { Plus, KeyRound, ShieldCheck } from "lucide-react";
import type { client } from "../api";
import { ConnectorArt } from "./ConnectorGallery";
import { WorkspaceDialog } from "./WorkspaceDialog";
const providers: Record<string, string> = {
  gemini: "Google Gemini",
  groq: "Groq",
  mcp: "Connection token",
};
export function KeyVaultPanel({ api }: { api: ReturnType<typeof client> }) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [modal, setModal] = useState(""),
    [selected, setSelected] = useState<any>(null),
    [provider, setProvider] = useState("gemini"),
    [tab, setTab] = useState("keys");
  async function load() {
    setData(await api.json("/vault"));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  async function act(fn: () => Promise<void>, message: string) {
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
  function open(key?: any, kind = "gemini") {
    setSelected(key || null);
    setProvider(key?.provider || kind);
    setError("");
    setModal("key");
  }
  const keys = (data?.credentials || []).filter(
      (c: any) => c.provider in providers,
    ),
    route: any = Object.values(data?.effective_routes || {}).find((r: any) =>
      ["gemini", "groq"].includes(r.provider),
    );
  return (
    <div className="studio-page dashboard-page vault-dashboard">
      <header className="dashboard-heading">
        <div>
          <span className="dashboard-kicker">WORKSPACE</span>
          <h1>Key vault</h1>
          <p>One default key for every agent.</p>
        </div>
        <button
          className="studio-primary"
          disabled={busy || !data?.ready}
          onClick={() => open()}
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
          {!data.ready && (
            <p className="error" role="alert">
              Vault encryption needs administrator setup.
            </p>
          )}
          <section className="dashboard-stat-grid" aria-label="Vault summary">
            <article>
              <KeyRound size={18} />
              <span>Saved keys</span>
              <strong>{keys.length}</strong>
            </article>
            <article>
              <ShieldCheck size={18} />
              <span>Default provider</span>
              <strong>
                {route ? providers[route.provider] : "Not configured"}
              </strong>
            </article>
            <article>
              <span>Agents using workspace key</span>
              <strong>{route ? Object.keys(data.agents).length : 0}</strong>
            </article>
            <article className="default-model-stat">
              <span>Automatic model</span>
              <strong>
                {route?.resolved_model || "Connect Gemini or Groq"}
              </strong>
            </article>
          </section>
          <div className="dashboard-toolbar">
            <nav aria-label="Vault sections">
              <button
                aria-current={tab === "keys" ? "page" : undefined}
                onClick={() => setTab("keys")}
              >
                API keys
              </button>
              <button
                aria-current={tab === "routes" ? "page" : undefined}
                onClick={() => setTab("routes")}
              >
                Agent routes
              </button>
            </nav>
          </div>
          {tab === "keys" ? (
            <div className="dashboard-connector-grid">
              {keys.map((c: any) => (
                <article className="dashboard-connector-card" key={c.id}>
                  <div className="dashboard-card-head">
                    <ConnectorArt name={c.provider} />
                    <span
                      className={
                        "dashboard-status " + (!c.enabled ? "muted" : "")
                      }
                    >
                      {!c.enabled
                        ? "Revoked"
                        : route?.credential_id === c.id
                          ? "Default"
                          : c.verified_model
                            ? "Verified"
                            : "Saved"}
                    </span>
                  </div>
                  <h3>{c.name}</h3>
                  <p>{providers[c.provider]}</p>
                  <div className="key-mask">
                    <KeyRound size={14} />
                    <span>Encrypted key</span>
                    <small>v{c.version}</small>
                  </div>
                  {c.verified_model && (
                    <small>Model checked: {c.verified_model}</small>
                  )}
                  <footer>
                    <button disabled={busy} onClick={() => open(c)}>
                      Replace
                    </button>
                    {c.enabled && c.provider !== "mcp" && (
                      <button
                        disabled={busy}
                        onClick={() =>
                          act(async () => {
                            await api.json(
                              "/vault/credentials/" + c.id + "/test",
                              { method: "POST" },
                            );
                          }, "Key verified. Agents use the workspace default automatically.")
                        }
                      >
                        Test connection
                      </button>
                    )}
                    {c.enabled && (
                      <button
                        disabled={busy}
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
                <button className="dashboard-empty-card" onClick={() => open()}>
                  <Plus size={28} />
                  <strong>Add your first key</strong>
                  <span>Gemini or Groq. Model selection is automatic.</span>
                </button>
              )}
            </div>
          ) : (
            <section className="dashboard-table-panel">
              <h2>Agent routes</h2>
              <p className="dashboard-footnote">
                Every agent inherits the same workspace key. No individual
                assignment is needed.
              </p>
              <div className="dashboard-table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Agent</th>
                      <th>Provider</th>
                      <th>Model</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.agents).map(
                      ([id, name]: [string, any]) => (
                        <tr key={id}>
                          <td>{name}</td>
                          <td>
                            {route
                              ? providers[route.provider]
                              : "Not configured"}
                          </td>
                          <td>{route?.resolved_model || "—"}</td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          <p className="dashboard-footnote">
            Saving a Gemini or Groq key verifies a supported chat model and
            makes it the workspace default.
          </p>
          <details>
            <summary>Connection tokens</summary>
            <p className="dashboard-footnote">
              For integrations that need a manual token.
            </p>
            <button disabled={busy} onClick={() => open(undefined, "mcp")}>
              Add connection token
            </button>
          </details>
        </>
      )}
      {modal && (
        <WorkspaceDialog
          title={
            modal === "revoke"
              ? "Revoke key"
              : selected
                ? "Replace key"
                : "Add a key"
          }
          onClose={() => {
            if (!busy) {
              setModal("");
              setError("");
            }
          }}
        >
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {modal === "key" ? (
            <form
              className="dashboard-dialog-form vault-key-dialog-form"
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                act(
                  async () => {
                    const path =
                      provider === "mcp"
                        ? "/vault/credentials"
                        : "/vault/model-key";
                    await api.json(path + (selected ? "/" + selected.id : ""), {
                      method: selected ? "PUT" : "POST",
                      body: JSON.stringify({
                        name: f.get("name") || providers[provider] + " key",
                        provider,
                        value: f.get("value"),
                      }),
                    });
                    setModal("");
                    setSelected(null);
                  },
                  provider === "mcp"
                    ? "Connection token saved"
                    : "Key verified and set as the workspace default.",
                );
              }}
            >
              {provider !== "mcp" ? (
                <label>
                  Provider
                  <select
                    aria-label="Credential provider"
                    value={provider}
                    disabled={busy || Boolean(selected)}
                    onChange={(e) => setProvider(e.target.value)}
                  >
                    <option value="gemini">Google Gemini</option>
                    <option value="groq">Groq</option>
                  </select>
                </label>
              ) : (
                <p>Connection token</p>
              )}
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
                  disabled={busy}
                />
              </label>
              <label>
                Name (optional)
                <input
                  aria-label="Credential name"
                  name="name"
                  maxLength={100}
                  defaultValue={selected?.name || ""}
                  disabled={busy}
                />
              </label>
              <small>Encrypted at rest. Your key is never displayed.</small>
              <footer>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setModal("");
                    setError("");
                  }}
                >
                  Cancel
                </button>
                <button className="studio-primary" disabled={busy}>
                  {busy ? "Checking key…" : "Save key"}
                </button>
              </footer>
            </form>
          ) : (
            <>
              <p>
                Revoke {selected?.name}? Work using this key will fail until an
                active key is available.
              </p>
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
            </>
          )}
        </WorkspaceDialog>
      )}
    </div>
  );
}
