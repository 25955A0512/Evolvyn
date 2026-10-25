import { useEffect, useState } from "react";
import type { client } from "../api";
import { OAuthSetup } from "./OAuthSetup";
export function AccountTeam({ api }: { api: ReturnType<typeof client> }) {
  const [me, setMe] = useState<any>(null);
  const [members, setMembers] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [audit, setAudit] = useState<any[]>([]);
  async function load() {
    try {
      const identity = await api.json("/auth/me");
      setMe(identity);
      if (identity.account) {
        setMembers(await api.json("/organizations/members"));
        if (["owner", "admin"].includes(identity.role))
          setAudit(await api.json("/audit"));
      }
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    load();
  }, []);
  return (
    <>
      <p className="panel-intro">
        Manage access to the current organization. Each business, document,
        conversation and action belongs to its organization.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {me?.account ? (
        <>
          <div className="saved-report">
            <strong>{me.account.name}</strong>
            <p>{me.account.email}</p>
            <small>Current role: {me.role}</small>
          </div>
          <AccountSecurity
            api={api}
            administrator={["owner", "admin"].includes(me.role)}
          />
          <h3>Organization members</h3>
          {members.map((m) => (
            <div className="integration" key={m.id}>
              <span>
                {m.name}
                <small>{m.email}</small>
              </span>
              <span>{m.role}</span>
            </div>
          ))}
          {["owner", "admin"].includes(me.role) && (
            <form
              className="panel-form"
              onSubmit={async (e) => {
                e.preventDefault();
                const form = e.currentTarget;
                try {
                  await api.json("/organizations/members", {
                    method: "POST",
                    body: JSON.stringify(
                      Object.fromEntries(new FormData(form)),
                    ),
                  });
                  form.reset();
                  await load();
                } catch (e) {
                  setError(String(e));
                }
              }}
            >
              <label>
                Existing account email
                <input name="email" type="email" required />
              </label>
              <label>
                Access level
                <select name="role">
                  <option value="viewer">Viewer · read only</option>
                  <option value="discussant">
                    Discussion · read and ask agents
                  </option>
                  <option value="editor">
                    Editor · analyze and manage tasks
                  </option>
                  <option value="admin">
                    Administrator · approve and manage access
                  </option>
                </select>
              </label>
              <small>
                The person must create an account first. This adds access
                directly; no email is sent.
              </small>
              <button className="primary">Add or update member</button>
            </form>
          )}
          <h3>Create another organization</h3>
          <form
            className="panel-form"
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                const created = await api.json("/organizations", {
                  method: "POST",
                  body: JSON.stringify(
                    Object.fromEntries(new FormData(e.currentTarget)),
                  ),
                });
                setError(
                  "Organization created: " +
                    created.name +
                    ". Reload to select it in the sidebar.",
                );
              } catch (e) {
                setError(String(e));
              }
            }}
          >
            <label>
              Organization name
              <input name="name" required maxLength={100} />
            </label>
            <button className="primary">Create organization</button>
          </form>
          {!!audit.length && (
            <>
              <h3>Recent audit history</h3>
              {audit.slice(0, 25).map((event) => (
                <div className="event" key={event.id}>
                  <span>
                    <strong>
                      {event.method} {event.path}
                    </strong>
                    <small>
                      {new Date(event.at).toLocaleString(undefined, {
                        timeZone: "Asia/Calcutta",
                      })}{" "}
                      · {event.role} · HTTP {event.status}
                    </small>
                  </span>
                </div>
              ))}
            </>
          )}
        </>
      ) : (
        <div className="panel-empty">
          Create an account to manage organizations and team members. Sample and
          private development-token workspaces remain isolated.
        </div>
      )}
    </>
  );
}

function AccountSecurity({
  api,
  administrator,
}: {
  api: ReturnType<typeof client>;
  administrator: boolean;
}) {
  const [security, setSecurity] = useState<any>(null),
    [providers, setProviders] = useState<any[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api.json("/auth/security"), api.json("/auth/providers")])
      .then(([a, b]) => {
        setSecurity(a);
        setProviders(b);
      })
      .catch((e) => setError(e.message));
  }, []);
  async function revoke() {
    try {
      await api.json("/auth/sessions/revoke-all", { method: "POST" });
      sessionStorage.removeItem("evolvyn-token");
      sessionStorage.removeItem("evolvyn-organization");
      window.location.reload();
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <section className="studio-card studio-form">
      <h3>Account security</h3>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <p>
        {security?.active_sessions || 0} active sessions. Linked providers:{" "}
        {security?.linked_providers?.join(", ") || "none"}.
      </p>
      {providers.map((p) => (
        <div key={p.id}>
          <strong>{p.name}</strong>
          {p.enabled ? (
            <button
              disabled={security?.linked_providers?.includes(p.id)}
              onClick={async () => {
                try {
                  const result = await api.json(
                    "/auth/oauth/" + p.id + "/link",
                    { method: "POST" },
                  );
                  window.location.assign(result.authorize_url);
                } catch (e: any) {
                  setError(e.message);
                }
              }}
            >
              {security?.linked_providers?.includes(p.id)
                ? "Linked"
                : "Link account"}
            </button>
          ) : (
            <p>Administrator OAuth configuration required.</p>
          )}
        </div>
      ))}
      {administrator && (
        <details>
          <summary>Deployment sign-in setup</summary>
          <OAuthSetup />
        </details>
      )}
      <details>
        <summary>Change password</summary>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const d = Object.fromEntries(new FormData(e.currentTarget));
            try {
              await api.json("/auth/password", {
                method: "POST",
                body: JSON.stringify(d),
              });
              sessionStorage.removeItem("evolvyn-token");
              window.location.reload();
            } catch (e: any) {
              setError(e.message);
            }
          }}
        >
          <label>
            Current password
            <input
              type="password"
              name="current_password"
              required
              autoComplete="current-password"
            />
          </label>
          <label>
            New password
            <input
              type="password"
              name="new_password"
              minLength={12}
              maxLength={128}
              autoComplete="new-password"
              required
            />
          </label>
          <button>Change password and sign out all sessions</button>
        </form>
      </details>
      <button onClick={revoke}>Sign out all devices</button>
    </section>
  );
}
