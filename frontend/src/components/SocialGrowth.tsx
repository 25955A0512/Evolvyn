import { useEffect, useRef, useState } from "react";
import {
  Activity,
  RefreshCw,
  Plus,
  ShieldCheck,
  Radio,
  Download,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { client } from "../api";
import type { ManageConnections } from "./ToolAccess";
const date = (s: string) => (s ? new Date(s).toLocaleString() : "Never");
export function SocialGrowth({
  api,
  conversationId,
  onManage,
}: {
  api: ReturnType<typeof client>;
  conversationId: string;
  onManage: ManageConnections;
}) {
  const [sources, setSources] = useState<any[]>([]),
    [tools, setTools] = useState<any[]>([]),
    [credentials, setCredentials] = useState<any[]>([]),
    [schedules, setSchedules] = useState<any[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [adding, setAdding] = useState(false),
    [kind, setKind] = useState("instagram_social"),
    [run, setRun] = useState<any>(null),
    [mode, setMode] = useState("default"),
    [instagram, setInstagram] = useState<any>(null),
    [comments, setComments] = useState(false);
  const watch = useRef<AbortController | null>(null),
    scope = useRef(conversationId);
  async function load() {
    const id = conversationId;
    if (!id) {
      setSources([]);
      return;
    }
    const [a, b, c, d, ig] = await Promise.all([
      api.json("/growth/social?conversation_id=" + encodeURIComponent(id)),
      api.json("/tool-registry"),
      api.json("/vault").catch(() => null),
      api.json("/schedules"),
      api.json("/integrations/instagram"),
    ]);
    if (scope.current !== id) return;
    setInstagram(ig);
    setSources(a);
    setTools(b.filter((t: any) => t.adapter === "mcp" && t.risk === "read"));
    setCredentials(
      c?.credentials.filter((v: any) => v.provider === "mcp" && v.enabled) ||
        [],
    );
    setSchedules(d);
  }
  useEffect(() => {
    scope.current = conversationId;
    setRun(null);
    setError("");
    load().catch((e) => setError(e.message));
    return () => watch.current?.abort();
  }, [conversationId]);
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
  function follow(r: any) {
    watch.current?.abort();
    watch.current = new AbortController();
    setRun(r);
    api
      .watch(
        r.id,
        (v) => {
          setRun(v);
          if (!["CREATED", "RUNNING"].includes(v.state))
            load().catch((e) => setError(e.message));
        },
        watch.current.signal,
      )
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
  }
  useEffect(() => {
    if (run) return;
    const active = sources
      .flatMap((s) => [s.last_execution, s.last_review])
      .find((r) => r && ["CREATED", "RUNNING"].includes(r.state));
    if (active) follow(active);
  }, [sources]);
  return (
    <section className="social-growth">
      <div className="growth-section-heading">
        <div>
          <span className="growth-badge">
            <Radio size={15} />
            Authorized social evidence
          </span>
          <h2>Listen to your audience. Measure what changes.</h2>
          <p>
            Connect a professional account through the shared MCP registry.
            Observations feed one business, research and strategy workflow.
            Reviews include uploaded business data from this evidence workspace.
          </p>
        </div>
        <div className="social-toolbar">
          <button
            disabled={!conversationId || busy}
            onClick={() => setAdding(!adding)}
          >
            <Plus size={17} />
            Connect social account
          </button>
          <button
            disabled={busy || !conversationId}
            onClick={() =>
              act(async () => {
                await load();
              })
            }
          >
            <RefreshCw size={16} />
            Refresh observations
          </button>
        </div>
      </div>
      {!conversationId && (
        <p className="growth-panel">
          Choose or create an evidence workspace above before connecting an
          account.
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="growth-notice" role="status">
          {notice}
        </p>
      )}
      {adding && (
        <form
          className="growth-panel growth-analysis-form"
          onSubmit={(e) => {
            e.preventDefault();
            const d = Object.fromEntries(new FormData(e.currentTarget));
            act(async () => {
              await api.json(
                kind === "mcp"
                  ? "/growth/social/sources"
                  : "/growth/social/native",
                {
                  method: "POST",
                  body: JSON.stringify(
                    kind === "mcp"
                      ? {
                          conversation_id: conversationId,
                          tool: d.tool,
                          provider: d.provider,
                          account_id: d.account_id,
                          name: d.name,
                        }
                      : {
                          conversation_id: conversationId,
                          profile: kind,
                          credential_id: d.credential_id,
                          account_id: d.account_id,
                          name: d.name,
                        },
                  ),
                },
              );
              setAdding(false);
              setNotice(
                "Source registered. Sync it to verify real provider access; MCP discovery alone is not account connectivity.",
              );
            });
          }}
        >
          <h3>Add an authorized source</h3>
          <div className="growth-form-grid">
            <label>
              Connection type
              <select
                aria-label="Social connection type"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
              >
                <option value="instagram_social">
                  Instagram professional · Facebook Login token
                </option>
                <option value="instagram_login_social">
                  Instagram professional · Instagram Login token
                </option>
                <option value="youtube_social">
                  YouTube · read-only OAuth
                </option>
                <option value="mcp">Approved MCP · social-v1 contract</option>
              </select>
            </label>
            <label>
              Display name
              <input name="name" required maxLength={100} />
            </label>
            <label>
              Authorized account / channel ID
              <input name="account_id" required maxLength={200} />
            </label>
            {kind === "mcp" ? (
              <>
                <label>
                  Read-only registered tool
                  <select
                    aria-label="Read-only registered tool"
                    name="tool"
                    required
                  >
                    <option value="">Choose social-v1 MCP tool</option>
                    {tools.map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Provider
                  <select aria-label="Provider" name="provider">
                    <option value="instagram">Instagram</option>
                    <option value="youtube">YouTube</option>
                    <option value="linkedin">LinkedIn organization</option>
                  </select>
                </label>
              </>
            ) : (
              <label>
                Saved provider credential
                <select
                  aria-label="Saved provider credential"
                  name="credential_id"
                  required
                >
                  <option value="">Choose encrypted MCP credential</option>
                  {credentials.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <p className="growth-help">
            Save the authorized provider access token in Key vault as an MCP
            credential, then select it here. No token goes in this form or tool
            arguments. For manual credentials, expired tokens must be replaced
            and the source reconnected. Instagram users can instead use Connect
            with Instagram below.
          </p>
          <details>
            <summary>Provider permissions and collection limits</summary>
            <p>
              Use the Instagram business account ID, not an @username or
              Facebook Page ID. Instagram needs a professional account and the
              matching Meta login flow, account-read and approved comment-read
              permissions. A Google/GitHub sign-in token is not social API
              access. YouTube requires Data API access and youtube.readonly
              OAuth. LinkedIn uses your separately approved MCP adapter; no
              native LinkedIn authorization is claimed.
            </p>
            <p>
              Reads at most 25 posts and 20 permitted Instagram comments.
              Views/reach/shares/saves are unavailable when not supplied. The
              social-v1 MCP output must match this account/provider and contain
              current timezone-aware timestamps. No private messages, author
              profiles or publishing.
            </p>
          </details>
          <button type="button" onClick={() => onManage("servers")}>
            Manage shared MCP connections
          </button>
          <a href="/keyvault">Open encrypted Key vault</a>
          <button className="studio-primary" disabled={busy}>
            Register social source
          </button>
        </form>
      )}
      {conversationId && (
        <section className="growth-panel social-oauth">
          <div className="growth-section-heading">
            <div>
              <h3>Connect Instagram directly</h3>
              <p>
                Authorize your professional account with Instagram. Evolvyn
                stores the token securely and creates the account connection;
                you do not need to copy a token.
              </p>
            </div>
            <button
              className="studio-primary"
              disabled={busy || !instagram?.configured}
              onClick={() =>
                act(async () => {
                  const result = await api.json(
                    "/integrations/instagram/authorize",
                    {
                      method: "POST",
                      body: JSON.stringify({
                        conversation_id: conversationId,
                        read_comments: comments,
                      }),
                    },
                  );
                  window.location.assign(result.authorize_url);
                })
              }
            >
              Connect with Instagram
            </button>
          </div>
          <label>
            <input
              type="checkbox"
              checked={comments}
              onChange={(e) => setComments(e.target.checked)}
            />
            Request access to comment text (optional permission)
          </label>
          <p className="growth-help">{instagram?.token_lifecycle}</p>
          {instagram && !instagram.configured && (
            <p role="status">
              Instagram connection needs one-time administrator setup.
              Individual users do not need to create developer applications.
            </p>
          )}
          {instagram?.setup && !instagram.configured && (
            <details>
              <summary>Administrator: configure Instagram OAuth</summary>
              <p>{instagram.setup.instructions}</p>
              <p>
                Redirect URI: <code>{instagram.callback_url}</code>
              </p>
              <p>
                Private Render variables:{" "}
                <code>{instagram.setup.variables.join(", ")}</code>. Never enter
                app secrets in the frontend or chat.
              </p>
            </details>
          )}
        </section>
      )}
      {!sources.length && conversationId && !adding && (
        <div className="growth-panel growth-empty">
          <Activity size={32} />
          <h3>Your social evidence starts with a verified read.</h3>
          <p>
            No social source is connected to this workspace. Add an authorized
            Instagram account, YouTube channel or approved social MCP. We never
            fill charts with sample engagement.
          </p>
        </div>
      )}
      {run && (
        <section className="growth-panel" role="status">
          <strong>Agent workflow · {run.state.replaceAll("_", " ")}</strong>
          {run.events?.slice(-5).map((e: any, i: number) => (
            <p key={i}>
              {e.stage}: {e.detail}
            </p>
          ))}
          {run.error && <p className="error">{run.error}</p>}
          {["CREATED", "RUNNING"].includes(run.state) && (
            <button
              onClick={() =>
                act(async () => {
                  await api.json("/executions/" + run.id + "/cancel", {
                    method: "POST",
                  });
                })
              }
            >
              Stop workflow
            </button>
          )}
        </section>
      )}
      {sources.map((s) => {
        const latest = s.latest,
          obs = latest?.observation,
          m = latest?.metrics,
          monitor = schedules.find((x) => x.social_source_id === s.id),
          review = s.last_review;
        const stale =
          s.last_success_at &&
          Date.now() - new Date(s.last_success_at).getTime() > 36 * 3600000;
        return (
          <article className="growth-panel" key={s.id}>
            <div className="growth-section-heading">
              <div>
                <span className="growth-badge">
                  {s.provider} ·{" "}
                  {!s.enabled
                    ? "Disconnected"
                    : s.connection_issue
                      ? "Needs reconnection"
                      : s.last_execution?.state === "FAILED"
                        ? "Last sync failed"
                        : stale
                          ? "Stale"
                          : s.last_success_at
                            ? "Verified observation saved"
                            : "Not verified yet"}
                </span>
                <h2>{s.name}</h2>
                <p>
                  Account {s.account_id} · Last successful read{" "}
                  {date(s.last_success_at)}
                </p>
              </div>
              <button
                disabled={busy || !s.enabled}
                onClick={() =>
                  act(async () =>
                    follow(
                      await api.json("/growth/social/" + s.id + "/sync", {
                        method: "POST",
                      }),
                    ),
                  )
                }
              >
                <RefreshCw size={16} />
                Sync account
              </button>
            </div>
            {s.oauth_provider && (
              <p className="growth-help">
                Instagram authorization expires {date(s.oauth_expires_at)}. The
                running backend renews eligible grants before expiry. Reconnect
                if the grant expires or is revoked. Paused monitoring stays
                paused.
              </p>
            )}
            {s.oauth_refresh_error && (
              <p className="error">{s.oauth_refresh_error}</p>
            )}
            {s.connection_issue && (
              <p className="error">{s.connection_issue}</p>
            )}
            {s.last_execution?.error && (
              <p className="error">{s.last_execution.error}</p>
            )}
            {m && (
              <>
                <div className="growth-kpis">
                  {[
                    ["Observed posts", m.posts_observed],
                    ["Reported followers", m.followers],
                    ["Reported likes", m.likes],
                    ["Reported comments", m.comments],
                    ["Reported views", m.views],
                  ].map(([k, v]) => (
                    <div className="social-kpi" key={k}>
                      <span>{k}</span>
                      <strong>{v === null ? "Unavailable" : v}</strong>
                    </div>
                  ))}
                </div>
                <p>{obs.coverage}</p>
                <p className="growth-help">
                  Provider account: {obs.account_name} · Captured{" "}
                  {date(obs.captured_at)} · social:{latest.id}. Cumulative
                  sampled counters; changes in sampled posts are not comparable
                  growth rates. Interactions per 100 views:{" "}
                  {m.interactions_per_100_views ?? "Unavailable"}; views are not
                  unique customers.
                </p>
                <details>
                  <summary>
                    Observation history and accessible chart values
                  </summary>
                  <div className="social-history">
                    {s.history
                      .slice()
                      .reverse()
                      .map((p: any) => {
                        const n = p.metrics.interactions,
                          max = Math.max(
                            ...s.history.map(
                              (x: any) => x.metrics.interactions || 0,
                            ),
                            1,
                          );
                        return (
                          <div key={p.id}>
                            <time>{date(p.captured_at)}</time>
                            {n === null ? (
                              <span>Unavailable</span>
                            ) : (
                              <>
                                <meter
                                  min={0}
                                  max={max}
                                  value={n}
                                  aria-label={
                                    "Sampled interactions at " +
                                    date(p.captured_at)
                                  }
                                />
                                <strong>{n}</strong>
                              </>
                            )}
                          </div>
                        );
                      })}
                  </div>
                  <p className="growth-help">
                    Counts are snapshots of cumulative counters, not new likes
                    per day. Changing cohorts and missing values are not
                    interpolated.
                  </p>
                </details>
                <div className="table-wrap">
                  <table>
                    <caption>Observed posts · {date(obs.captured_at)}</caption>
                    <thead>
                      <tr>
                        <th>Post</th>
                        <th>Published</th>
                        <th>Likes</th>
                        <th>Comments</th>
                        <th>Views</th>
                      </tr>
                    </thead>
                    <tbody>
                      {obs.posts.map((p: any) => (
                        <tr key={p.id}>
                          <td>
                            <a
                              href={p.url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {p.text || p.id}
                            </a>
                          </td>
                          <td>{date(p.published_at)}</td>
                          <td>{p.likes ?? "Unavailable"}</td>
                          <td>{p.comments ?? "Unavailable"}</td>
                          <td>{p.views ?? "Unavailable"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <details>
                  <summary>
                    Permitted comment sample · {obs.comment_sample.length}
                  </summary>
                  <p className="growth-help">
                    Email addresses, handles and phone-like numbers are
                    redacted. Text remains untrusted input; no customer identity
                    or representative sentiment is inferred.
                  </p>
                  {obs.comment_sample.map((c: any) => (
                    <blockquote key={c.id}>
                      <p>{c.text}</p>
                      <small>
                        {date(c.published_at)} · {c.id}
                      </small>
                    </blockquote>
                  ))}
                </details>
                <section className="growth-finding">
                  <h3>Forecast eligibility</h3>
                  {s.forecast.status === "available" ? (
                    <>
                      <p>
                        Daily new interactions estimate:{" "}
                        {s.forecast.daily_estimate} · range{" "}
                        {s.forecast.daily_low}–{s.forecast.daily_high} · next{" "}
                        {s.forecast.horizon_days} days on this unchanged post
                        cohort.
                      </p>
                      <p>
                        Model {s.forecast.model} · {s.forecast.sample_size}{" "}
                        daily observations · backtest MAE {s.forecast.mae},
                        last-day baseline MAE {s.forecast.naive_mae}.
                      </p>
                      <p>
                        {s.forecast.uncertainty} {s.forecast.limitations}
                      </p>
                    </>
                  ) : (
                    <p>{s.forecast.reason}</p>
                  )}
                </section>
                <div className="growth-inline-form">
                  <label>
                    Review model route
                    <select
                      aria-label="Review model route"
                      value={mode}
                      onChange={(e) => setMode(e.target.value)}
                    >
                      <option value="default">Workspace default model</option>
                      <option value="local">Local model</option>
                      <option value="evidence">Evidence rules · no LLM</option>
                    </select>
                  </label>
                  <button
                    className="studio-primary"
                    disabled={busy}
                    onClick={() =>
                      act(async () =>
                        follow(
                          await api.json("/growth/social/" + s.id + "/review", {
                            method: "POST",
                            body: JSON.stringify({ mode }),
                          }),
                        ),
                      )
                    }
                  >
                    Run business + research + strategy review
                  </button>
                  <button
                    disabled={busy}
                    onClick={() =>
                      api
                        .download(
                          "/growth/social/" + s.id + "/report",
                          "social-growth-report.json",
                        )
                        .catch((e) => setError(e.message))
                    }
                  >
                    <Download size={16} />
                    Export evidence report
                  </button>
                </div>
              </>
            )}
            {review && (
              <section className="growth-finding">
                <h3>
                  Saved specialist review · {review.state.replaceAll("_", " ")}
                </h3>
                <p className="growth-help">
                  Review snapshot: social:{review.snapshot_id}.{" "}
                  {latest && review.snapshot_id !== latest.id
                    ? "A newer observation exists; rerun the review to include it. "
                    : ""}{" "}
                  Model interpretations and experiment proposals require human
                  validation. No post, campaign or spend was executed.
                </p>
                {review.error && <p className="error">{review.error}</p>}
                {[
                  ["business_intelligence", "Business intelligence"],
                  ["customer_research", "Research & customer intelligence"],
                  ["growth_strategy", "Growth strategy"],
                ].map(([id, label]) => (
                  <details key={id} open={id === "growth_strategy"}>
                    <summary>{label}</summary>
                    <ReactMarkdown>
                      {review.graph_checkpoint?.nodes?.[id]?.output?.text ||
                        "No completed handoff yet."}
                    </ReactMarkdown>
                  </details>
                ))}
              </section>
            )}
            <div className="growth-inline-form">
              <label>
                Monitoring cadence
                <select
                  aria-label={"Social cadence: " + s.name}
                  defaultValue={monitor?.interval_minutes || 1440}
                  id={"social-cadence-" + s.id}
                >
                  <option value={60}>Hourly</option>
                  <option value={1440}>Daily</option>
                  <option value={10080}>Weekly</option>
                </select>
              </label>
              <button
                disabled={busy || !s.enabled}
                onClick={() =>
                  act(async () => {
                    await api.json("/growth/social/" + s.id + "/monitor", {
                      method: "POST",
                      body: JSON.stringify({
                        enabled: !monitor?.enabled,
                        interval_minutes: Number(
                          (
                            document.getElementById(
                              "social-cadence-" + s.id,
                            ) as HTMLSelectElement
                          ).value,
                        ),
                      }),
                    });
                    setNotice(
                      monitor?.enabled
                        ? "Social monitoring paused."
                        : "Social monitoring scheduled. It runs only while the backend is awake and provider authorization remains valid.",
                    );
                  })
                }
              >
                {monitor?.enabled
                  ? "Pause social monitoring"
                  : "Enable social monitoring"}
              </button>
              <button
                disabled={busy || !s.enabled}
                onClick={() =>
                  act(async () => {
                    await api.json("/growth/social/" + s.id, {
                      method: "DELETE",
                    });
                    setNotice(
                      "Disconnected: polling stopped. Saved evidence retained. OAuth credentials are erased locally; revoke the provider grant separately if required. Manual tokens stay in the vault until revoked.",
                    );
                  })
                }
              >
                Disconnect source
              </button>
            </div>
            <p className="growth-help">
              {monitor
                ? (monitor.enabled ? "Scheduled" : "Paused") +
                  " · Next due " +
                  date(monitor.next_run_at)
                : "Monitoring not configured"}
              . A sleeping free backend cannot provide continuous monitoring.
              Forecasts need comparable daily history.
            </p>
          </article>
        );
      })}
      <p className="growth-help">
        <ShieldCheck size={14} /> Read-only collection never approves actions.
        Publishing, ads, spend, native social OAuth refresh and comprehensive
        analytics permissions remain separate integration work.
      </p>
    </section>
  );
}
