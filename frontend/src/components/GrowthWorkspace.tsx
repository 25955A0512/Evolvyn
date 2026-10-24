import { CommerceMetrics } from "./CommerceMetrics";
import { ToolAccess, parseCalls, type ManageConnections } from "./ToolAccess";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import type { client } from "../api";
import type { Convo } from "../types";
type API = ReturnType<typeof client>;
export function GrowthWorkspace({
  api,
  conversation,
  projectId,
  businessId,
  onManage,
}: {
  api: API;
  conversation: Convo | null;
  projectId: string;
  businessId: string;
  onManage: ManageConnections;
}) {
  const [reports, setReports] = useState<any[]>([]),
    [report, setReport] = useState<any>(null),
    [products, setProducts] = useState<any[]>([]),
    [convos, setConvos] = useState<any[]>([]),
    [conversationId, setConversationId] = useState(conversation?.id || ""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [run, setRun] = useState<any>(null),
    [plan, setPlan] = useState(""),
    [ack, setAck] = useState(false),
    [files, setFiles] = useState<any[]>([]),
    [contextTools, setContextTools] = useState<any[]>([]);
  const [contextJson, setContextJson] = useState("[]");
  const watch = useRef<AbortController | null>(null);
  useEffect(() => {
    Promise.all([
      api.json("/growth/reports"),
      api.json("/studio/products"),
      api.json("/conversations"),
      api.json("/tool-registry"),
    ])
      .then(([a, b, c, d]) => {
        setReports(a);
        setProducts(b);
        setConvos(c);
        setContextTools(
          d.filter((t: any) => t.adapter === "mcp" && t.risk === "read"),
        );
      })
      .catch((e) => setError(e.message));
    return () => watch.current?.abort();
  }, []);
  useEffect(() => {
    if (conversationId)
      api
        .json("/conversations/" + conversationId)
        .then((c) => setFiles(c.files || []))
        .catch((e) => setError(e.message));
  }, [conversationId]);
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="studio-page">
      <div className="studio-page-title">
        <span className="eyebrow">CONTINUOUS PRODUCT EVOLUTION</span>
        <h1>Listen. Measure. Improve.</h1>
        <p>
          Connect customer feedback, first-party performance and public
          discussion signals to a reviewed product decision. Compare evidence
          before deciding what to promote or build next.
        </p>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="studio-success">
          {notice}
        </p>
      )}
      <ToolAccess
        api={api}
        onManage={onManage}
        inline
        calls={parseCalls(contextJson)}
        onChange={(v) => setContextJson(JSON.stringify(v))}
        conversationId={conversationId}
      />
      <div className="studio-two-columns">
        <form
          className="studio-card studio-form"
          onSubmit={(e) => {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(e.currentTarget));
            act(async () => {
              if (!conversationId)
                throw Error("Create or choose an evidence conversation first");
              let calls = [];
              try {
                calls = JSON.parse(String(data.context_tools || "[]"));
              } catch {
                throw Error("Connector calls must be a JSON array");
              }
              const row = await api.json("/growth/reports", {
                method: "POST",
                body: JSON.stringify({
                  conversation_id: conversationId,
                  product_id: data.product_id || null,
                  query: data.query,
                  public_research: data.public_research === "on",
                  window_days: Number(data.window_days),
                  context_tools: calls,
                }),
              });
              setReport(row);
              setReports(await api.json("/growth/reports"));
              setRun(null);
              setNotice(
                "Evidence snapshot saved. Suggestions remain hypotheses until reviewed.",
              );
            });
          }}
        >
          <h3>Growth evidence</h3>
          <label>
            Evidence conversation
            <select
              aria-label="Growth conversation"
              value={conversationId}
              onChange={(e) => setConversationId(e.target.value)}
            >
              <option value="">Choose conversation</option>
              {convos
                .filter((c) => c.project_id === (projectId || null))
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              act(async () => {
                const c = await api.json("/conversations", {
                  method: "POST",
                  body: JSON.stringify({
                    title: "Product growth evidence",
                    goal: "Understand customer needs and product growth",
                    business_id: businessId || null,
                    project_id: projectId || null,
                  }),
                });
                setConvos([c, ...convos]);
                setConversationId(c.id);
              })
            }
          >
            Create evidence conversation
          </button>
          <label>
            Product
            <select name="product_id">
              <option value="">Business analysis only</option>
              {products
                .filter((p) => p.project_id === (projectId || null))
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Product, category or research query
            <input
              aria-label="Growth research query"
              name="query"
              minLength={3}
              maxLength={200}
              required
              placeholder="e.g. privacy tools for small agencies"
            />
          </label>
          <label>
            Comparison window
            <select name="window_days" defaultValue="30">
              <option value="7">7 days vs previous 7 days</option>
              <option value="30">30 days vs previous 30 days</option>
              <option value="90">90 days vs previous 90 days</option>
            </select>
          </label>
          <label className="checkbox">
            <input name="public_research" type="checkbox" />
            Fetch live public discussion activity (sends this query to Algolia)
          </label>
          <details>
            <summary>Authorized MCP context</summary>
            <p>
              {contextTools.length
                ? contextTools.map((t) => t.name).join(", ")
                : "No read-only MCP tools registered. Configure them in Integrations."}
            </p>
            <label>
              Read-only calls JSON
              <textarea
                name="context_tools"
                value={contextJson}
                onChange={(e) => setContextJson(e.target.value)}
                placeholder='[{"name":"crm_feedback","arguments":{}}]'
              />
            </label>
          </details>
          <button className="studio-primary" disabled={busy || !conversationId}>
            {busy ? "Collecting evidence…" : "Analyze growth evidence"}
          </button>
        </form>
        <div className="studio-card">
          <h3>Customer and performance uploads</h3>
          <p>
            Upload dated funnel exports and consented feedback. Data stays
            within the selected conversation and project access rules.
          </p>
          <label>
            Upload TXT, CSV, PDF or DOCX
            <input
              aria-label="Growth evidence file"
              type="file"
              accept=".txt,.csv,.pdf,.docx"
              disabled={!conversationId || busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file)
                  act(async () => {
                    const data = new FormData();
                    data.append("file", file);
                    await api.json(
                      "/conversations/" + conversationId + "/files",
                      { method: "POST", body: data },
                    );
                    const c = await api.json(
                      "/conversations/" + conversationId,
                    );
                    setFiles(c.files);
                    setNotice("Evidence uploaded");
                  });
                e.target.value = "";
              }}
            />
          </label>
          {files.map((f) => (
            <p key={f.id}>{f.name}</p>
          ))}
          <h3>Saved growth snapshots</h3>
          <select
            aria-label="Saved growth report"
            value={report?.id || ""}
            onChange={(e) => {
              setReport(reports.find((r) => r.id === e.target.value));
              setRun(null);
            }}
          >
            <option value="">Choose report</option>
            {reports
              .filter((r) => r.project_id === (projectId || null))
              .map((r) => (
                <option key={r.id} value={r.id}>
                  {r.query} · {new Date(r.created_at).toLocaleDateString()}
                </option>
              ))}
          </select>
          <p>
            Public discussions are a nonrepresentative sample. They cannot
            establish market size, product revenue or customer growth.
          </p>
        </div>
      </div>
      {report && (
        <>
          <div className="studio-card growth-snapshot">
            <span className="eyebrow">
              EVIDENCE SNAPSHOT · {new Date(report.created_at).toLocaleString()}
            </span>
            <h2>{report.query}</h2>
            <p>{report.classification}</p>
            <h3>Market discussion signal</h3>
            {report.market.status === "available" ? (
              <>
                <div className="growth-metrics">
                  <div>
                    <strong>{report.market.previous.count}</strong>
                    <span>Previous {report.market.window_days} days</span>
                  </div>
                  <div>
                    <strong>{report.market.current.count}</strong>
                    <span>Current {report.market.window_days} days</span>
                  </div>
                  <div>
                    <strong>
                      {report.market.absolute_change > 0 ? "+" : ""}
                      {report.market.absolute_change}
                    </strong>
                    <span>Change in matching discussions</span>
                  </div>
                </div>
                <p>{report.market.classification}</p>
                {report.market.current.sources.map((s: any) => (
                  <p key={s.url}>
                    <a href={s.url} target="_blank" rel="noopener noreferrer">
                      {s.title}
                    </a>{" "}
                    · {s.citation} · {s.published_at}
                  </p>
                ))}
              </>
            ) : (
              <p>{report.market.classification}</p>
            )}
            <h3>First-party observations</h3>
            {report.report.commerce && (
              <CommerceMetrics data={report.report.commerce.primary} />
            )}
            {!report.report.commerce &&
              report.first_party_change?.status === "available" && (
                <div className="growth-metrics">
                  <div>
                    <strong>
                      {report.first_party_change.visits_change_percent}%
                    </strong>
                    <span>Visits change</span>
                  </div>
                  <div>
                    <strong>
                      {report.first_party_change
                        .paid_outcomes_change_percent === null
                        ? "No baseline"
                        : report.first_party_change
                            .paid_outcomes_change_percent + "%"}
                    </strong>
                    <span>Paid outcomes change</span>
                  </div>
                  <div>
                    <strong>
                      {
                        report.first_party_change
                          .conversion_change_percentage_points
                      }{" "}
                      pp
                    </strong>
                    <span>Conversion change</span>
                  </div>
                </div>
              )}
            {!report.report.commerce && report.first_party_change && (
              <p>{report.first_party_change.classification}</p>
            )}
            {!report.report.commerce &&
              !report.report.facts?.length &&
              !report.report.themes?.length && (
                <p>
                  No measurable first-party baseline found. Upload evidence
                  before inferring product growth.
                </p>
              )}
            {report.report.facts?.slice(0, 10).map((f: any, i: number) => (
              <p key={i}>
                {f.source}: {f.conversion}% conversion ({f.paid} / {f.visits})
              </p>
            ))}
            {report.report.themes?.map((t: any) => (
              <div key={t.id}>
                <strong>
                  {t.label} · {t.keyword_mentions} keyword mentions
                </strong>
                <p>{t.sources.join("; ")}</p>
                <p>{t.classification}</p>
              </div>
            ))}
            {report.connector_evidence?.map((s: any) => (
              <details key={s.citation}>
                <summary>{s.citation}</summary>
                <pre>{s.excerpt}</pre>
              </details>
            ))}
          </div>
          <div className="studio-two-columns">
            {report.actions.map((a: any) => (
              <article key={a.id} className="studio-card">
                <span className="eyebrow">{a.type}</span>
                <h3>{a.title}</h3>
                <p>{a.suggestion}</p>
                <p>
                  <strong>Measure:</strong> {a.metric}
                </p>
                <small>{a.confidence}</small>
                <p>
                  {a.evidence.join("; ") ||
                    "No direct supporting source; hypothesis only"}
                </p>
                <button
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      await api.json(
                        "/growth/reports/" + report.id + "/propose",
                        {
                          method: "POST",
                          body: JSON.stringify({ action_id: a.id }),
                        },
                      );
                      setNotice(
                        "Proposed as draft decision memory. Review it in Agent memory before applying product changes.",
                      );
                    })
                  }
                >
                  Propose for review
                </button>
              </article>
            ))}
          </div>
          <section className="studio-card">
            <h3>Discuss with business, marketing and product specialists</h3>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const d = Object.fromEntries(new FormData(e.currentTarget));
                act(async () => {
                  const execution = await api.json("/discussions", {
                    method: "POST",
                    body: JSON.stringify({
                      conversation_id: report.conversation,
                      growth_report_id: report.id,
                      goal:
                        "Review growth snapshot " +
                        report.query +
                        ". Distinguish measurements from hypotheses; suggest promotion experiments and prioritized product changes with citations, owner, baseline and rollback.",
                      mode: d.mode,
                      allow_fallback: false,
                      max_rounds: 2,
                    }),
                  });
                  setRun(execution);
                  setPlan("");
                  watch.current?.abort();
                  watch.current = new AbortController();
                  api
                    .watch(
                      execution.id,
                      (r) => {
                        setRun(r);
                        if (r.state === "WAITING_FOR_APPROVAL")
                          setPlan(
                            r.discussion_result?.outputs?.product_manager
                              ?.text || "",
                          );
                      },
                      watch.current.signal,
                    )
                    .catch((e) => {
                      if (e.name !== "AbortError") setError(e.message);
                    });
                });
              }}
            >
              <label>
                Model route
                <select name="mode" defaultValue="default">
                  <option value="evidence">Evidence rules · no API key</option>
                  <option value="default">
                    Organization / agent model routes
                  </option>
                  <option value="local">Local AI</option>
                </select>
              </label>
              <button
                disabled={busy || ["CREATED", "RUNNING"].includes(run?.state)}
                className="studio-primary"
              >
                Run specialist review
              </button>
            </form>
            {run && (
              <>
                <p role="status">{run.state.replaceAll("_", " ")}</p>
                {run.error && <p role="alert">{run.error}</p>}
                <ReactMarkdown>{run.output || ""}</ReactMarkdown>
                {run.state === "WAITING_FOR_APPROVAL" && (
                  <>
                    <label>
                      Reviewed decision
                      <textarea
                        aria-label="Growth decision"
                        maxLength={4000}
                        value={plan}
                        onChange={(e) => setPlan(e.target.value)}
                      />
                    </label>
                    {run.discussion_result?.issues?.length > 0 && (
                      <>
                        <p>{run.discussion_result.issues.join("; ")}</p>
                        <label>
                          <input
                            type="checkbox"
                            checked={ack}
                            onChange={(e) => setAck(e.target.checked)}
                          />
                          I have reviewed and acknowledge these unresolved
                          issues.
                        </label>
                      </>
                    )}
                    <button
                      disabled={busy || !plan.trim()}
                      onClick={() =>
                        act(async () => {
                          setRun(
                            await api.json(
                              "/discussions/" + run.id + "/decision",
                              {
                                method: "POST",
                                body: JSON.stringify({
                                  approve: true,
                                  plan,
                                  acknowledge_issues: ack,
                                }),
                              },
                            ),
                          );
                          setNotice(
                            "Reviewed decision saved. Open Build a product to apply specific requirement changes and rebuild.",
                          );
                        })
                      }
                    >
                      Approve decision to memory
                    </button>
                    <button
                      disabled={busy}
                      onClick={() =>
                        act(async () => {
                          setRun(
                            await api.json(
                              "/discussions/" + run.id + "/decision",
                              {
                                method: "POST",
                                body: JSON.stringify({
                                  approve: false,
                                  plan: plan || "Rejected after review",
                                }),
                              },
                            ),
                          );
                        })
                      }
                    >
                      Reject decision
                    </button>
                  </>
                )}
              </>
            )}
          </section>
        </>
      )}
    </div>
  );
}
