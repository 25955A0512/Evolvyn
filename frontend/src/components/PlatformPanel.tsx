import "../dashboard-refresh.css";
import { WorkflowCanvas } from "./WorkflowCanvas";
import { AccountTeam } from "./AccountTeam";
import { useEffect, useState } from "react";
import { X, Check, Play, Pause, LoaderCircle } from "lucide-react";
import type { client } from "../api";
import type { Convo } from "../types";
type View =
  "tasks" | "reports" | "automation" | "workflow" | "projects" | "account";
type Task = {
  id: string;
  title: string;
  status: string;
  notes: string;
  artifact: string;
};
type Report = {
  id: string;
  plan: string;
  outcome: string;
  conversation: string;
  baseline?: { conversion: number; period: string };
  commerce_baseline?: any;
  execution_result?: { tool: string; verified_task_count: number };
  tasks: string[];
};
type Schedule = {
  id: string;
  query: string;
  enabled: boolean;
  interval_minutes: number;
  next_run_at: string;
  last_run?: string;
  last_error?: string;
};
type Measurement = {
  kind?: string;
  changes?: Record<
    string,
    {
      before: any;
      after: any;
      absolute_change: string | null;
      percent_change: string | null;
    }
  >;
  comparable_duration?: boolean;
  id: string;
  baseline: { conversion: number; period: string };
  followup: { conversion: number; period: string };
  change_percentage_points: number;
  classification: string;
  notes: string;
};
export function PlatformPanel({
  view,
  api,
  businessId,
  conversation,
  onClose,
  onProject,
  onRefresh,
  onTabChange,
}: {
  view: View;
  onTabChange?: (tab: View) => void;
  api: ReturnType<typeof client>;
  businessId: string;
  conversation: Convo | null;
  onClose: () => void;
  onProject: () => void;
  onRefresh?: () => void;
}) {
  const [tab, setTabState] = useState<View>(view);
  function setTab(value: View) {
    setTabState(value);
    onTabChange?.(value);
  }
  useEffect(() => setTabState(view), [view]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [projects, setProjects] = useState<
    { id: string; name: string; goal: string }[]
  >([]);
  const [workflow, setWorkflow] = useState<{
    nodes: { id: string; label: string; detail: string }[];
    limits: Record<string, number>;
  } | null>(null);
  const [tools, setTools] = useState<
    { name: string; description: string; risk: string }[]
  >([]);
  const [measures, setMeasures] = useState<Record<string, Measurement[]>>({});
  const fail = (e: unknown) =>
    setError(e instanceof Error ? e.message : String(e));
  async function load() {
    setLoading(true);
    try {
      if (tab === "tasks")
        setTasks(
          await api.json(
            "/tasks" +
              (conversation ? "?conversation_id=" + conversation.id : ""),
          ),
        );
      if (tab === "reports") {
        const records: Report[] = await api.json("/reports");
        const filtered = records.filter(
          (r) => !conversation || r.conversation === conversation.id,
        );
        setReports(filtered);
        for (const r of filtered)
          setMeasures((prev) => ({ ...prev, [r.id]: prev[r.id] || [] }));
        const results = await Promise.all(
          filtered.map(async (r) => [
            r.id,
            await api.json("/artifacts/" + r.id + "/measurements"),
          ]),
        );
        setMeasures(Object.fromEntries(results));
      }
      if (tab === "automation") setSchedules(await api.json("/schedules"));
      if (tab === "projects")
        setProjects(
          await api.json(
            "/projects" + (businessId ? "?business_id=" + businessId : ""),
          ),
        );
      if (tab === "workflow") {
        setWorkflow(await api.json("/workflows"));
        setTools(await api.json("/tools"));
      }
    } catch (e) {
      fail(e);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    setError("");
    load();
  }, [tab, conversation?.id, businessId]);
  const titles = {
    tasks: "Your action plan",
    reports: "Reports & outcomes",
    automation: "Monitoring",
    workflow: "Inside the workflow",
    projects: "Business projects",
    account: "Account & team",
  };
  return (
    <div className="panel-shade">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="panel-title"
        className="platform-panel"
        data-view={tab}
      >
        <header>
          <div>
            <small>BUSINESS WORKSPACE</small>
            <h2 id="panel-title">{titles[tab]}</h2>
          </div>
          <button aria-label="Close workspace panel" onClick={onClose}>
            <X size={19} />
          </button>
        </header>
        <nav className="panel-tabs">
          {(
            [
              "tasks",
              "reports",
              "automation",
              "workflow",
              "projects",
              "account",
            ] as View[]
          ).map((v) => (
            <button
              className={tab === v ? "selected" : ""}
              key={v}
              onClick={() => setTab(v)}
            >
              {v === "automation"
                ? "Schedules"
                : v[0].toUpperCase() + v.slice(1)}
            </button>
          ))}
        </nav>
        <div className="panel-content">
          {loading && (
            <div className="loading">
              <LoaderCircle size={15} /> Loading saved workspace data…
            </div>
          )}
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          {tab === "account" && <AccountTeam api={api} />}
          {tab === "tasks" && (
            <>
              <p className="panel-intro">
                Approved recommendations become real internal tasks here. Status
                changes record your work; they do not claim business impact.
              </p>
              {!tasks.length && !loading && (
                <div className="panel-empty">
                  Approve a recommendation in a conversation to create your
                  first action plan.
                </div>
              )}
              {tasks.map((t) => (
                <form
                  className="task-item"
                  key={t.id}
                  onSubmit={async (e) => {
                    e.preventDefault();
                    setError("");
                    const d = new FormData(e.currentTarget);
                    try {
                      await api.json("/tasks/" + t.id, {
                        method: "PATCH",
                        body: JSON.stringify(Object.fromEntries(d)),
                      });
                      await load();
                    } catch (e) {
                      fail(e);
                    }
                  }}
                >
                  <div className="task-title">
                    <Check size={16} />
                    <strong>{t.title}</strong>
                  </div>
                  <label>
                    Status
                    <select
                      aria-label="Task status"
                      name="status"
                      defaultValue={t.status}
                    >
                      <option value="todo">To do</option>
                      <option value="in_progress">In progress</option>
                      <option value="done">Done</option>
                      <option value="cancelled">Cancelled</option>
                    </select>
                  </label>
                  <label>
                    Work notes
                    <textarea
                      aria-label="Task work notes"
                      name="notes"
                      defaultValue={t.notes}
                      placeholder="What did you do? What evidence did you collect?"
                      maxLength={4000}
                    />
                  </label>
                  <button className="primary">Save task</button>
                </form>
              ))}
            </>
          )}
          {tab === "reports" && (
            <>
              <p className="panel-intro">
                Approved briefs and their measured observations. Upload a
                follow-up CSV into the same conversation to compare it with the
                stored baseline.
              </p>
              {!reports.length && !loading && (
                <div className="panel-empty">
                  Your approved reports will appear here.
                </div>
              )}
              {reports.map((r) => (
                <article className="saved-report" key={r.id}>
                  <span className="eyebrow">APPROVED ACTION PLAN</span>
                  <p>{r.plan}</p>
                  <small>{r.outcome}</small>
                  {r.baseline && (
                    <p className="baseline">
                      Baseline: {r.baseline.conversion}% · {r.baseline.period}
                    </p>
                  )}
                  {r.commerce_baseline && (
                    <p className="baseline">
                      Saved sales baseline:{" "}
                      {r.commerce_baseline.net_revenue ?? "Not available"}{" "}
                      {r.commerce_baseline.currency || "currency unspecified"}{" "}
                      net revenue · {r.commerce_baseline.orders ?? "Unknown"}{" "}
                      orders · AOV{" "}
                      {r.commerce_baseline.average_order_value ??
                        "Not available"}
                    </p>
                  )}
                  {r.execution_result && (
                    <p>
                      Executed tool: {r.execution_result.tool} ·{" "}
                      {r.execution_result.verified_task_count} saved tasks
                      verified.
                    </p>
                  )}
                  {conversation &&
                    (r.baseline || r.commerce_baseline?.kind === "sales") && (
                      <form
                        onSubmit={async (e) => {
                          e.preventDefault();
                          setError("");
                          try {
                            await api.json("/artifacts/" + r.id + "/measure", {
                              method: "POST",
                              body: JSON.stringify(
                                Object.fromEntries(
                                  new FormData(e.currentTarget),
                                ),
                              ),
                            });
                            await load();
                          } catch (e) {
                            fail(e);
                          }
                        }}
                      >
                        {r.commerce_baseline && (
                          <p>
                            Choose a new sales export with dates strictly after
                            the baseline, in the same currency. A pre/post
                            change does not prove the task caused a sales
                            effect.
                          </p>
                        )}
                        <label>
                          Follow-up CSV
                          <select name="document_id" required defaultValue="">
                            <option value="" disabled>
                              Select uploaded measurement data
                            </option>
                            {conversation.files
                              .filter((f) =>
                                f.name.toLowerCase().endsWith(".csv"),
                              )
                              .map((f) => (
                                <option key={f.id} value={f.id}>
                                  {f.name}
                                </option>
                              ))}
                          </select>
                        </label>
                        <label>
                          Measurement notes
                          <textarea
                            name="notes"
                            placeholder="Observation window, limitations and other changes"
                            maxLength={2000}
                          />
                        </label>
                        <button className="primary">
                          Compare observations
                        </button>
                      </form>
                    )}
                  {measures[r.id]?.map((m) => (
                    <div className="measurement" key={m.id}>
                      {m.kind === "commerce" ? (
                        <>
                          <strong>Observed sales outcome</strong>
                          {Object.entries(m.changes || {}).map(([key, v]) => (
                            <p key={key}>
                              {key.replaceAll("_", " ")}: {v.before} → {v.after}{" "}
                              · change {v.absolute_change ?? "unavailable"} (
                              {v.percent_change === null
                                ? "no nonzero baseline"
                                : v.percent_change + "%"}
                              )
                            </p>
                          ))}
                          {!m.comparable_duration && (
                            <p>
                              Observed date spans differ; raw totals are not
                              directly comparable as growth rates.
                            </p>
                          )}
                        </>
                      ) : (
                        <>
                          <strong>
                            {m.baseline.conversion}% → {m.followup.conversion}%
                          </strong>
                          <span>
                            {m.change_percentage_points > 0 ? "+" : ""}
                            {m.change_percentage_points} percentage points
                          </span>
                        </>
                      )}
                      <p>{m.classification}</p>
                      {m.notes && <p>{m.notes}</p>}
                    </div>
                  ))}
                </article>
              ))}
            </>
          )}
          {tab === "automation" && (
            <>
              <section
                className="dashboard-stat-grid"
                aria-label="Monitoring summary"
              >
                {[
                  ["Schedules", schedules.length],
                  ["Enabled", schedules.filter((s) => s.enabled).length],
                  ["Paused", schedules.filter((s) => !s.enabled).length],
                  [
                    "Needs attention",
                    schedules.filter((s) => s.last_error).length,
                  ],
                ].map(([label, value]) => (
                  <article key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                  </article>
                ))}
              </section>
              <p className="panel-intro">
                Scheduled reviews. Actions need approval.
              </p>
              {conversation ? (
                <form
                  className="panel-form"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    setError("");
                    const f = e.currentTarget,
                      d = Object.fromEntries(new FormData(f));
                    try {
                      await api.json("/schedules", {
                        method: "POST",
                        body: JSON.stringify({
                          ...d,
                          conversation_id: conversation.id,
                          interval_minutes: Number(d.interval_minutes),
                          enabled: true,
                        }),
                      });
                      f.reset();
                      await load();
                    } catch (e) {
                      fail(e);
                    }
                  }}
                >
                  <label>
                    Analysis goal
                    <input
                      name="query"
                      required
                      minLength={3}
                      maxLength={2000}
                      placeholder="Monitor conversion and review customer feedback"
                    />
                  </label>
                  <div className="form-row">
                    <label>
                      Every (minutes)
                      <input
                        name="interval_minutes"
                        type="number"
                        min={1}
                        max={10080}
                        defaultValue={60}
                        required
                      />
                    </label>
                    <label>
                      Analysis mode
                      <select name="mode">
                        <option value="default">
                          Default agent model route
                        </option>
                      </select>
                    </label>
                  </div>
                  <button className="primary">Create recurring analysis</button>
                </form>
              ) : (
                <div className="panel-empty">
                  Open a conversation with uploaded data to schedule its
                  analysis.
                </div>
              )}
              {schedules.map((s) => (
                <article className="schedule-item" key={s.id}>
                  <strong>{s.query}</strong>
                  <p>
                    Every {s.interval_minutes} min ·{" "}
                    {s.enabled ? "Enabled" : "Paused"}
                  </p>
                  <small>
                    Next:{" "}
                    {new Date(s.next_run_at).toLocaleString(undefined, {
                      timeZone: "Asia/Calcutta",
                    })}
                  </small>
                  {s.last_error && <p className="error">{s.last_error}</p>}
                  {s.last_run && (
                    <small>Last run saved in execution history.</small>
                  )}
                  <div className="panel-actions">
                    <button
                      onClick={async () => {
                        try {
                          await api.json("/schedules/" + s.id, {
                            method: "PATCH",
                            body: JSON.stringify({ enabled: !s.enabled }),
                          });
                          await load();
                        } catch (e) {
                          fail(e);
                        }
                      }}
                    >
                      {s.enabled ? <Pause size={14} /> : <Play size={14} />}{" "}
                      {s.enabled ? "Pause" : "Enable"}
                    </button>
                    <button
                      onClick={async () => {
                        try {
                          await api.json("/schedules/" + s.id + "/run", {
                            method: "POST",
                          });
                          await load();
                          onRefresh?.();
                        } catch (e) {
                          fail(e);
                        }
                      }}
                    >
                      <Play size={14} /> Run now
                    </button>
                  </div>
                </article>
              ))}
            </>
          )}
          {tab === "projects" && (
            <>
              {businessId ? (
                <form
                  className="panel-form"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    const f = e.currentTarget;
                    try {
                      await api.json("/projects", {
                        method: "POST",
                        body: JSON.stringify({
                          ...Object.fromEntries(new FormData(f)),
                          business_id: businessId,
                        }),
                      });
                      f.reset();
                      await load();
                      onProject();
                    } catch (e) {
                      fail(e);
                    }
                  }}
                >
                  <label>
                    Project name
                    <input
                      name="name"
                      required
                      maxLength={100}
                      placeholder="Activation improvement"
                    />
                  </label>
                  <label>
                    Goal
                    <textarea
                      name="goal"
                      required
                      maxLength={1000}
                      placeholder="Increase activation while maintaining retention"
                    />
                  </label>
                  <label>
                    Data policy
                    <select name="data_policy">
                      <option value="local_only">Local processing only</option>
                      <option value="allow_selected_provider">
                        Allow explicitly selected remote providers
                      </option>
                    </select>
                  </label>
                  <button className="primary">Create project</button>
                </form>
              ) : (
                <div className="panel-empty">
                  Select a business in the sidebar before creating a project.
                </div>
              )}
              {projects.map((p) => (
                <article className="saved-report" key={p.id}>
                  <strong>{p.name}</strong>
                  <p>{p.goal}</p>
                </article>
              ))}
            </>
          )}
          {tab === "workflow" && workflow && (
            <>
              <p className="panel-intro">
                The actual execution path. Tool inputs, outputs and permissions
                are checked on the backend. External content cannot approve
                actions.
              </p>
              <WorkflowCanvas
                api={api}
                nodes={workflow.nodes}
                conversation={conversation}
                onRun={onRefresh}
              />
              <div className="limit-grid">
                {Object.entries(workflow.limits).map(([key, value]) => (
                  <div key={key}>
                    <strong>{value}</strong>
                    <small>{key.replaceAll("_", " ")}</small>
                  </div>
                ))}
              </div>
              <h3>Available tool registry</h3>
              {tools.map((t) => (
                <details key={t.name}>
                  <summary>{t.name}</summary>
                  <p>{t.description}</p>
                  <small>Risk: {t.risk}</small>
                </details>
              ))}
            </>
          )}
        </div>
      </section>
    </div>
  );
}
