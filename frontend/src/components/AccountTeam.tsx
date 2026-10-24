import { useEffect, useState } from "react";
import type { client } from "../api";
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
