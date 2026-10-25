import { useEffect, useState } from "react";
import {
  CalendarDays,
  FileUp,
  GitBranch,
  ArrowDown,
  Play,
  Pause,
  Clock,
  CheckCircle2,
} from "lucide-react";
import type { client } from "../api";
import { UiIcon } from "./UiIcon";
export function AutomationStudio({
  api,
  projectId,
  conversationId,
  onNavigate,
}: {
  api: ReturnType<typeof client>;
  projectId: string;
  conversationId?: string;
  onNavigate?: (id: string) => void;
}) {
  const [kind, setKind] = useState(""),
    [convos, setConvos] = useState<any[]>([]),
    [schedules, setSchedules] = useState<any[]>([]),
    [triggers, setTriggers] = useState<any[]>([]),
    [events, setEvents] = useState<Record<string, any[]>>({}),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [conversation, setConversation] = useState(conversationId || "");
  async function load() {
    const [a, b, c] = await Promise.all([
      api.json("/conversations"),
      api.json("/schedules"),
      api.json("/automations"),
    ]);
    setConvos(a);
    setSchedules(b);
    setTriggers(c);
    const rows = await Promise.all(
      c.map(async (t: any) => [
        t.id,
        await api.json("/automations/" + t.id + "/events"),
      ]),
    );
    setEvents(Object.fromEntries(rows));
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
  const allowed = new Set(
    convos.filter((c) => c.project_id === (projectId || null)).map((c) => c.id),
  );
  return (
    <div className="automation-studio dashboard-page">
      <div className="automation-title">
        <span className="dashboard-kicker">WORKSPACE</span>
        <h2>Monitoring</h2>
        <p>Schedules, triggers and recent activity.</p>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="studio-success" role="status">
          {notice}
        </p>
      )}
      <section className="dashboard-stat-grid" aria-label="Monitoring summary">
        {[
          [
            "Schedules",
            schedules.filter((s) => allowed.has(s.conversation_id)).length,
          ],
          [
            "Triggers",
            triggers.filter((s) => allowed.has(s.conversation_id)).length,
          ],
          [
            "Enabled",
            [...schedules, ...triggers].filter(
              (s) => allowed.has(s.conversation_id) && s.enabled,
            ).length,
          ],
          [
            "Needs attention",
            [...schedules, ...triggers].filter(
              (s) => allowed.has(s.conversation_id) && s.last_error,
            ).length,
          ],
        ].map(([label, value]) => (
          <article key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </section>
      <div className="automation-templates">
        {[
          {
            id: "schedule",
            name: "Schedule",
            icon: CalendarDays,
            top: "A scheduled time",
            bottom: "Run the next evidence review",
            description: "Review a conversation at a recurring interval.",
          },
          {
            id: "trigger",
            name: "Upload trigger",
            icon: FileUp,
            top: "A new file is uploaded",
            bottom: "Analyze the new business evidence",
            description:
              "Start a review when a document is uploaded to your chosen conversation.",
          },
          {
            id: "condition",
            name: "Conditional review",
            icon: GitBranch,
            top: "An uploaded metric meets your rule",
            bottom: "Queue a focused agent investigation",
            description: "Check a real metric before starting the review.",
          },
        ].map((t) => (
          <button
            key={t.id}
            className={
              "automation-template " + (kind === t.id ? "selected" : "")
            }
            onClick={() => setKind(t.id)}
          >
            <div className="automation-illustration">
              <div>
                <UiIcon
                  name={
                    t.id === "schedule"
                      ? "calendar"
                      : t.id === "trigger"
                        ? "file-text"
                        : "git-branch"
                  }
                  size={25}
                />
                <strong>{t.top}</strong>
              </div>
              <ArrowDown size={22} />
              <div>
                <CheckCircle2 size={23} />
                <strong>{t.bottom}</strong>
              </div>
            </div>
            <section>
              <h3>{t.name}</h3>
              <p>{t.description}</p>
              <span>Configure →</span>
            </section>
          </button>
        ))}
      </div>
      {kind && (
        <form
          className="studio-card automation-config"
          onSubmit={(e) => {
            e.preventDefault();
            const d = Object.fromEntries(new FormData(e.currentTarget));
            act(async () => {
              if (!conversation) throw Error("Choose an evidence conversation");
              if (kind === "schedule") {
                await api.json("/schedules", {
                  method: "POST",
                  body: JSON.stringify({
                    conversation_id: conversation,
                    query: d.query,
                    mode: "default",
                    interval_minutes: Number(d.interval_minutes),
                    allow_fallback: false,
                  }),
                });
              } else {
                await api.json("/automations", {
                  method: "POST",
                  body: JSON.stringify({
                    name: d.name,
                    conversation_id: conversation,
                    query: d.query,
                    mode: "default",
                    condition:
                      kind === "condition"
                        ? { metric: d.metric, op: d.op, value: d.value }
                        : null,
                  }),
                });
              }
              setKind("");
              setNotice(
                "Automation saved. Reviews are queued through the worker; no action is automatically approved.",
              );
            });
          }}
        >
          <h3>
            {kind === "schedule"
              ? "Schedule a review"
              : kind === "condition"
                ? "Define your condition"
                : "Review each new upload"}
          </h3>
          <label>
            Evidence conversation
            <select
              aria-label="Automation conversation"
              value={conversation}
              onChange={(e) => setConversation(e.target.value)}
              required
            >
              <option value="">Choose conversation</option>
              {convos
                .filter((c) => allowed.has(c.id))
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
            </select>
          </label>
          {kind !== "schedule" && (
            <label>
              Name
              <input name="name" required minLength={2} maxLength={100} />
            </label>
          )}
          <label>
            What should the agents investigate?
            <textarea
              aria-label="Automation goal"
              name="query"
              required
              minLength={5}
              maxLength={2000}
              placeholder="Describe the business question and the evidence to check"
            />
          </label>
          <label>
            Model route
            <select name="mode" defaultValue="default">
              <option value="default">Workspace keys</option>
            </select>
          </label>
          {kind === "schedule" ? (
            <label>
              Repeat every (minutes)
              <input
                aria-label="Automation interval"
                name="interval_minutes"
                type="number"
                defaultValue={1440}
                min={1}
                max={10080}
                required
              />
            </label>
          ) : kind === "condition" ? (
            <div className="automation-condition">
              <label>
                Observed metric
                <select name="metric">
                  {[
                    "net_revenue",
                    "gross_sales",
                    "orders",
                    "average_order_value",
                    "inventory_units",
                  ].map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
              </label>
              <label>
                Comparison
                <select name="op">
                  <option value="lt">Below</option>
                  <option value="gt">Above</option>
                  <option value="eq">Equal to</option>
                </select>
              </label>
              <label>
                Threshold
                <input
                  name="value"
                  aria-label="Metric threshold"
                  type="number"
                  step="any"
                  min={0}
                  required
                />
              </label>
            </div>
          ) : null}
          <p>
            Only authorized uploads and their calculated metrics trigger these
            reviews. Shopify/webhook events require a separate verified adapter.
            Missing metrics do not satisfy a condition.
          </p>
          <div className="studio-actions">
            <button className="studio-primary" disabled={busy}>
              Save automation
            </button>
            <button type="button" onClick={() => setKind("")}>
              Cancel
            </button>
          </div>
        </form>
      )}
      <div className="automation-list-heading">
        <h3>Your automations</h3>
        <button onClick={() => act(load)} disabled={busy}>
          Refresh status
        </button>
      </div>
      {!schedules.filter((s) => allowed.has(s.conversation_id)).length &&
        !triggers.filter((s) => allowed.has(s.conversation_id)).length && (
          <p>No saved automations in this project yet.</p>
        )}
      {schedules
        .filter((s) => allowed.has(s.conversation_id))
        .map((s) => (
          <article className="studio-card automation-row" key={s.id}>
            <CalendarDays />
            <div>
              <h3>{s.query}</h3>
              <p>
                Every {s.interval_minutes} minutes ·{" "}
                {s.enabled ? "active" : "paused"} · next{" "}
                {new Date(s.next_run_at).toLocaleString()}
              </p>
              {s.last_run && <p>Last execution: {s.last_run}</p>}
              {s.last_error && <p className="error">{s.last_error}</p>}
            </div>
            <button
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await api.json("/schedules/" + s.id, {
                    method: "PATCH",
                    body: JSON.stringify({ enabled: !s.enabled }),
                  });
                })
              }
            >
              {s.enabled ? <Pause size={16} /> : <Play size={16} />}{" "}
              {s.enabled ? "Pause" : "Resume"}
            </button>
            <button onClick={() => onNavigate?.(s.conversation_id)}>
              Open conversation / results
            </button>
            <button
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const r = await api.json("/schedules/" + s.id + "/run", {
                    method: "POST",
                  });
                  setNotice(
                    "Execution " +
                      r.id +
                      " queued. Open its conversation to follow progress.",
                  );
                })
              }
            >
              Run now
            </button>
          </article>
        ))}
      {triggers
        .filter((s) => allowed.has(s.conversation_id))
        .map((s) => (
          <article className="studio-card automation-trigger" key={s.id}>
            <div className="automation-row">
              <GitBranch />
              <div>
                <h3>{s.name}</h3>
                <p>
                  New upload
                  {s.condition
                    ? ` · ${s.condition.metric} ${s.condition.op} ${s.condition.value}`
                    : ""}{" "}
                  · {s.enabled ? "active" : "paused"}
                </p>
                <p>{s.query}</p>
              </div>
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await api.json("/automations/" + s.id, {
                      method: "PATCH",
                      body: JSON.stringify({ enabled: !s.enabled }),
                    });
                  })
                }
              >
                {s.enabled ? "Pause" : "Resume"}
              </button>
              <button onClick={() => onNavigate?.(s.conversation_id)}>
                Open conversation / results
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await api.json("/automations/" + s.id + "/run", {
                      method: "POST",
                    });
                    setNotice(
                      "Latest upload checked. Each automation/upload pair creates at most one review; inspect its event history below.",
                    );
                  })
                }
              >
                Check latest upload
              </button>
            </div>
            <details>
              <summary>
                Actual event history · {events[s.id]?.length || 0}
              </summary>
              {events[s.id]?.map((e) => (
                <div className="automation-event" key={e.id}>
                  <Clock size={15} />
                  <div>
                    <strong>{e.state}</strong>
                    <p>{e.detail}</p>
                    {e.condition_result && (
                      <p>
                        Observed {e.condition_result.metric}:{" "}
                        {e.condition_result.observed ?? "unavailable"} ·
                        matched: {String(e.condition_result.matched)}
                      </p>
                    )}
                    {e.execution_id && <p>Execution: {e.execution_id}</p>}
                  </div>
                </div>
              ))}
            </details>
          </article>
        ))}
    </div>
  );
}
