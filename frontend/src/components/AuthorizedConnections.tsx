import { useEffect, useState } from "react";
import type { client } from "../api";
import { ConnectorArt } from "./ConnectorGallery";
import { OAuthSetup } from "./OAuthSetup";
export function AuthorizedConnections({
  api,
}: {
  api: ReturnType<typeof client>;
}) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [setup, setSetup] = useState(false);
  async function load() {
    setData(await api.json("/integrations/connections"));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const gh = data?.github,
    connection = gh?.connection;
  return (
    <section className="authorized-connections">
      <div className="authorized-connector">
        <ConnectorArt name="GitHub" size={30} />
        <div>
          <h3>GitHub</h3>
          <p>Read repositories and issues.</p>
          <p role="status">
            {connection
              ? `${connection.login} · ${connection.state}`
              : "Not connected"}
          </p>
        </div>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <div className="authorized-connector-actions">
        <button
          disabled={busy || !gh}
          onClick={() =>
            gh.configured
              ? act(async () => {
                  const result = await api.json(
                    "/integrations/github/authorize",
                    { method: "POST" },
                  );
                  location.assign(result.authorize_url);
                })
              : setSetup(!setup)
          }
        >
          {connection && connection.state !== "disconnected"
            ? "Reconnect GitHub"
            : "Connect GitHub"}
        </button>
        {connection && connection.state !== "disconnected" && (
          <>
            <button
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const result = await api.json("/integrations/github/test", {
                    method: "POST",
                  });
                  setNotice(
                    `${result.state} · ${result.tools} tools discovered`,
                  );
                })
              }
            >
              Test connection
            </button>
            <button
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const result = await api.json("/integrations/github", {
                    method: "DELETE",
                  });
                  setNotice(result.provider_authorization);
                })
              }
            >
              Disconnect GitHub
            </button>
          </>
        )}
        <button onClick={() => setSetup(!setup)}>OAuth setup guidance</button>
      </div>
      {setup && <OAuthSetup provider="github" />}
    </section>
  );
}
