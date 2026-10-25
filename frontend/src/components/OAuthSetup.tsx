import { useEffect, useState } from "react";
import { UiIcon } from "./UiIcon";

type Provider = {
  id: "google" | "github";
  name: string;
  enabled: boolean;
  configuration_error?: string;
  setup?: any;
};
const known = [
  { id: "google", name: "Google" },
  { id: "github", name: "GitHub" },
] as const;
async function providers(signal?: AbortSignal): Promise<Provider[]> {
  const response = await fetch("/api/auth/providers", {
    signal,
    cache: "no-store",
  });
  if (!response.ok) throw Error("Sign-in options are temporarily unavailable.");
  const rows = await response.json();
  if (!Array.isArray(rows))
    throw Error("Sign-in options are temporarily unavailable.");
  return known.map((p) => {
    const row = rows.find((r) => r.id === p.id);
    return { ...row, ...p, enabled: row?.enabled === true };
  });
}
function Brand({ provider }: { provider: string }) {
  return (
    <span className="oauth-brand" aria-hidden="true">
      {provider === "github" ? (
        <UiIcon name="brand-github" size={21} />
      ) : (
        <svg width="21" height="21" viewBox="0 0 24 24">
          <path
            fill="#4285F4"
            d="M21.6 12.23c0-.71-.06-1.39-.18-2.05H12v3.88h5.38a4.6 4.6 0 0 1-1.99 3.02v2.51h3.23c1.89-1.74 2.98-4.3 2.98-7.36Z"
          />
          <path
            fill="#34A853"
            d="M12 22c2.7 0 4.96-.9 6.62-2.41l-3.23-2.51c-.9.6-2.04.96-3.39.96-2.6 0-4.8-1.76-5.59-4.12H3.07v2.59A10 10 0 0 0 12 22Z"
          />
          <path
            fill="#FBBC05"
            d="M6.41 13.92a6 6 0 0 1 0-3.84V7.49H3.07a10 10 0 0 0 0 9.02l3.34-2.59Z"
          />
          <path
            fill="#EA4335"
            d="M12 5.96c1.47 0 2.79.51 3.82 1.51l2.87-2.87A9.62 9.62 0 0 0 12 2a10 10 0 0 0-8.93 5.49l3.34 2.59C7.2 7.72 9.4 5.96 12 5.96Z"
          />
        </svg>
      )}
    </span>
  );
}
export function OAuthSetup({ provider }: { provider?: string }) {
  const [rows, setRows] = useState<Provider[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    providers(controller.signal)
      .then(setRows)
      .catch((e) => {
        if (e.name !== "AbortError")
          setError("Provider setup could not be loaded. Refresh to retry.");
      });
    return () => controller.abort();
  }, []);
  return (
    <section className="oauth-setup">
      <h3>Deployment administrator setup</h3>
      <p>
        Register Google and GitHub OAuth applications once for this deployment.
        After configuration, users authorize their own accounts directly. Model
        API keys are separate.
      </p>
      {error && <p role="alert">{error}</p>}
      {rows
        .filter((p) => !provider || p.id === provider)
        .map((p) => (
          <details key={p.id} open={!!provider}>
            <summary>
              {p.name} ·{" "}
              {p.enabled
                ? "configured · verify with a real sign-in"
                : "administrator setup required"}
            </summary>
            {p.configuration_error && (
              <p role="alert">{p.configuration_error}</p>
            )}
            <a
              href={p.setup?.console_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open {p.name} developer console ↗
            </a>
            <ol>
              {p.setup?.instructions.map((text: string, i: number) => (
                <li key={i}>{text}</li>
              ))}
            </ol>
            <label>
              Exact callback URL<code>{p.setup?.callback_url}</code>
            </label>
            <p>Backend environment variable names:</p>
            <pre>
              {p.setup?.client_id_env}=<br />
              {p.setup?.client_secret_env}=
            </pre>
            <p>
              Enter credentials privately in the deployment environment; no
              secret values are shown or requested here.
            </p>
          </details>
        ))}
    </section>
  );
}
export function OAuthButtons({ register = false }: { register?: boolean }) {
  const [rows, setRows] = useState<Provider[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  async function load(signal?: AbortSignal) {
    setLoading(true);
    setError("");
    try {
      const value = await providers(signal);
      if (!signal?.aborted) setRows(value);
    } catch (e: any) {
      if (e.name !== "AbortError")
        setError(
          "Social sign-in could not be checked. Use email or try again.",
        );
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, []);
  const unavailable = rows.filter((p) => !p.enabled).map((p) => p.name);
  return (
    <div className="public-oauth">
      <div className="oauth-providers">
        {known.map((p) => {
          const ready =
            rows.find((r) => r.id === p.id)?.enabled === true &&
            !loading &&
            !error;
          const content = (
            <>
              <Brand provider={p.id} />
              <span>
                {register ? "Sign up" : "Sign in"} with {p.name}
              </span>
            </>
          );
          return ready ? (
            <a
              className="oauth-provider"
              key={p.id}
              href={"/api/auth/oauth/" + p.id + "/start"}
            >
              {content}
            </a>
          ) : (
            <button
              type="button"
              className="oauth-provider"
              key={p.id}
              disabled
              aria-describedby="social-sign-in-status"
            >
              {content}
              <small>{loading ? "Checking…" : "Unavailable"}</small>
            </button>
          );
        })}
      </div>
      <div
        id="social-sign-in-status"
        className="oauth-availability"
        role="status"
      >
        {loading
          ? "Checking sign-in options…"
          : error ||
            (unavailable.length
              ? `${unavailable.join(" and ")} sign-in is currently unavailable. You can continue with email.`
              : "")}
      </div>
      {error && (
        <button type="button" className="oauth-retry" onClick={() => load()}>
          Retry sign-in options
        </button>
      )}
    </div>
  );
}
