import { useEffect, useState } from "react";
import type { client } from "../api";
import { ConnectorArt } from "./ConnectorGallery";
import { OAuthSetup } from "./OAuthSetup";
import { WorkspaceDialog } from "./WorkspaceDialog";
import "../dashboard-refresh.css";
const descriptions: Record<string, string> = {
  github: "Public repositories and issues.",
  google_drive: "Files and documents · read only.",
  slack: "Public channels your bot can access.",
  shopify: "Products and recent order totals.",
};
const instructions: Record<string, string[]> = {
  google_drive: [
    "Enable Google Drive API in Google Cloud.",
    "Create a Web application OAuth client. Add the redirect URL below.",
    "Configure the consent screen and add your team as test users. Request Drive read-only access.",
    "Save the client ID and secret privately in Render → API service → Environment, then redeploy.",
  ],
  slack: [
    "Create a Slack app from scratch in your workspace.",
    "In OAuth & Permissions, add the redirect URL and the bot scopes below. Keep token rotation off for this version.",
    "Save the client ID and client secret from Basic Information in Render → API service → Environment, then redeploy.",
    "Connect your workspace here, then invite the bot to the public channels you want to read.",
  ],
  shopify: [
    "Create an app in the Shopify Dev Dashboard. Use legacy authorization-code installation for this connection flow.",
    "Set the app URL to this platform and add the redirect URL below. Configure the read scopes below and release the app configuration.",
    "Save the app client ID and secret privately in Render → API service → Environment, then redeploy.",
    "Connect using your store’s myshopify.com hostname. Test on a development store before requesting merchant distribution.",
  ],
};
export function AuthorizedConnections({
  api,
  query = "",
  onChange,
}: {
  api: ReturnType<typeof client>;
  query?: string;
  onChange?: () => void;
}) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [setup, setSetup] = useState(""),
    [shop, setShop] = useState("");
  async function load() {
    const [github, business] = await Promise.all([
      api.json("/integrations/connections"),
      api.json("/integrations/business-connections"),
    ]);
    setData({ ...github, ...business });
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
      onChange?.();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function connect(id: string) {
    act(async () => {
      try {
        const result = await api.json("/integrations/" + id + "/authorize", {
          method: "POST",
          ...(id === "github"
            ? {}
            : {
                body: JSON.stringify(
                  id === "shopify" ? { shop: shop.trim().toLowerCase() } : {},
                ),
              }),
        });
        location.assign(result.authorize_url);
      } catch (e: any) {
        if (e.status === 503) {
          setSetup(id);
          await load();
        }
        throw e;
      }
    });
  }
  const names: Record<string, string> = {
    github: "GitHub",
    google_drive: "Google Drive",
    slack: "Slack",
    shopify: "Shopify",
  };
  const ids = Object.keys(names).sort((a, b) => {
    const rank = (id: string) =>
      data?.[id]?.connection?.state === "connected"
        ? 0
        : data?.[id]?.configured
          ? 1
          : 2;
    return rank(a) - rank(b);
  });
  return (
    <section className="oauth-account-section" aria-label="OAuth accounts">
      <div className="dashboard-card-head">
        <h2>Account connections</h2>
        <span className="dashboard-footnote">OAuth · read only</span>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {!data && <p role="status">Loading accounts…</p>}
      <div className="dashboard-connector-grid">
        {ids
          .filter((id) =>
            (names[id] + " " + descriptions[id])
              .toLowerCase()
              .includes(query.toLowerCase()),
          )
          .map((id) => {
            const provider = data?.[id],
              connection = provider?.connection,
              active = connection && connection.state !== "disconnected";
            return (
              <article className="dashboard-connector-card" key={id}>
                <div className="dashboard-card-head">
                  <ConnectorArt name={names[id]} />
                  <span
                    className={
                      "dashboard-status " +
                      (connection?.state === "connected" ? "" : "muted")
                    }
                  >
                    {connection
                      ? connection.state.replaceAll("_", " ")
                      : provider?.configured
                        ? "Ready to connect"
                        : "Setup required"}
                  </span>
                </div>
                <h3>{names[id]}</h3>
                <p>{descriptions[id]}</p>
                {active && (
                  <small>
                    {connection.login}
                    {connection.last_success_at &&
                      " · Checked " +
                        new Date(connection.last_success_at).toLocaleString()}
                  </small>
                )}
                <footer>
                  <button
                    disabled={busy || !provider}
                    onClick={() =>
                      id !== "shopify" ? connect(id) : setSetup(id)
                    }
                  >
                    {active ? "Reconnect " : "Connect "}
                    {names[id]}
                  </button>
                  {active && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        act(async () => {
                          const result = await api.json(
                            "/integrations/" + id + "/test",
                            { method: "POST" },
                          );
                          setNotice(
                            names[id] +
                              ": " +
                              result.state.replaceAll("_", " "),
                          );
                        })
                      }
                    >
                      Test connection
                    </button>
                  )}
                  <button onClick={() => setSetup(id)}>Setup</button>
                </footer>
                {active && (
                  <button
                    disabled={busy}
                    onClick={() => setSetup(id + ":disconnect")}
                  >
                    Disconnect {names[id]}
                  </button>
                )}
              </article>
            );
          })}
      </div>
      {setup && (
        <WorkspaceDialog
          title={
            setup.endsWith(":disconnect")
              ? "Disconnect account"
              : names[setup] + " setup"
          }
          onClose={() => {
            if (!busy) setSetup("");
          }}
        >
          {setup.endsWith(":disconnect") ? (
            <>
              <p>Remove the saved grant and disable its tools?</p>
              <button
                className="studio-primary"
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    const result = await api.json(
                      "/integrations/" + setup.split(":")[0],
                      { method: "DELETE" },
                    );
                    setNotice(result.provider_authorization);
                    setSetup("");
                  })
                }
              >
                Disconnect
              </button>
            </>
          ) : setup === "github" ? (
            <OAuthSetup provider="github" />
          ) : (
            <div className="connector-setup-body">
              <p role="status">
                {data?.[setup]?.configured
                  ? "Ready to connect. Continue to authorize your account."
                  : "App credentials are missing from the running API. Add the variables below in Render, then redeploy."}
              </p>
              {instructions[setup] && (
                <details>
                  <summary>Provider setup steps</summary>
                  <ol className="connector-setup-steps">
                    {instructions[setup].map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ol>
                </details>
              )}
              <a
                href={data?.[setup]?.setup.console_url}
                target="_blank"
                rel="noreferrer"
              >
                Open provider console ↗
              </a>
              <label>
                Redirect URL
                <input
                  readOnly
                  value={data?.[setup]?.setup.callback_url || ""}
                />
              </label>
              <label>
                Render environment variables
                <textarea
                  readOnly
                  rows={2}
                  value={(data?.[setup]?.setup.variables || []).join("\n")}
                />
              </label>
              <p className="dashboard-footnote">
                Scopes: {(data?.[setup]?.setup.scopes || []).join(", ")}
              </p>
              {setup === "google_drive" && (
                <p className="dashboard-footnote">
                  Google may require verification for public Drive access.
                  Testing-mode grants can expire after seven days.
                </p>
              )}
              {setup === "shopify" && (
                <label>
                  Store hostname
                  <input
                    aria-label="Shopify store hostname"
                    placeholder="mystore.myshopify.com"
                    value={shop}
                    onChange={(e) => setShop(e.target.value)}
                  />
                </label>
              )}
              <footer className="connector-oauth-actions">
                <button disabled={busy} onClick={() => act(load)}>
                  Refresh status
                </button>
                <button
                  className="studio-primary"
                  disabled={
                    busy ||
                    !data?.[setup]?.configured ||
                    (setup === "shopify" && !shop.trim())
                  }
                  onClick={() => connect(setup)}
                >
                  Continue to {names[setup]}
                </button>
              </footer>
            </div>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
        </WorkspaceDialog>
      )}
    </section>
  );
}
