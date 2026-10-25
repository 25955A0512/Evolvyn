import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  Activity,
  BarChart3,
  CheckCircle2,
  Clock3,
  Database,
  FileUp,
  Lightbulb,
  Plus,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Target,
  TrendingUp,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { client } from "../api";
import type { Convo } from "../types";
import { CommerceMetrics } from "./CommerceMetrics";
import { ExecutionView } from "./ExecutionView";
import { GrowthReview } from "./GrowthReview";
import { ToolAccess, parseCalls, type ManageConnections } from "./ToolAccess";
import { GrowthCampaign } from "./GrowthCampaign";
import "../growth-workspace.css";
type API = ReturnType<typeof client>;
type Tab = "overview" | "evidence" | "actions" | "monitoring";
const date = (value?: string) =>
  value ? new Date(value).toLocaleString() : "Not yet";
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
  const scope = projectId || businessId || "organization";
  const [tab, setTab] = useState<Tab>("overview"),
    [convos, setConvos] = useState<any[]>([]),
    [businesses, setBusinesses] = useState<any[]>([]),
    [business, setBusiness] = useState(businessId || ""),
    [products, setProducts] = useState<any[]>([]);
  const [initializedScope, setInitializedScope] = useState("");
  const [conversationId, setConversationId] = useState(""),
    [workspace, setWorkspace] = useState<any>(null),
    [report, setReport] = useState<any>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [query, setQuery] = useState(""),
    [contextJson, setContextJson] = useState("[]"),
    [run, setRun] = useState<any>(null),
    [profile, setProfile] = useState(false),
    [newBusiness, setNewBusiness] = useState(false),
    [campaign, setCampaign] = useState(false),
    [route, setRoute] = useState("default");
  const watch = useRef<AbortController | null>(null),
    generation = useRef(0),
    selected = useRef("");
  const scoped = (c: any) =>
    c.project_id === (projectId || null) &&
    (!business || c.business_id === business);
  const currentBusiness = businesses.find((b) => b.id === business),
    files = workspace?.conversation?.files || [],
    reports = workspace?.reports || [];
  const data = report?.report?.commerce?.primary;
  async function load(id: string) {
    const n = ++generation.current;
    setLoading(true);
    setWorkspace(null);
    setReport(null);
    setRun(null);
    watch.current?.abort();
    try {
      const w = await api.json(`/growth/conversations/${id}/workspace`);
      if (n !== generation.current) return;
      setWorkspace(w);
      setReport(w.reports[0] || null);
      setQuery(w.reports[0]?.query || "");
      const execution = w.executions.find(
        (r: any) =>
          !["graph", "assistant_chat", "langgraph_discussion"].includes(
            r.engine || "",
          ),
      );
      if (execution) follow(execution);
    } catch (e: any) {
      if (n === generation.current) setError(e.message);
    } finally {
      if (n === generation.current) setLoading(false);
    }
  }
  async function refresh(id = conversationId) {
    if (!id) return;
    const w = await api.json(`/growth/conversations/${id}/workspace`);
    if (selected.current !== id) return;
    setWorkspace(w);
    setReport(
      (r: any) =>
        w.reports.find((x: any) => x.id === r?.id) || w.reports[0] || null,
    );
  }
  function follow(r: any) {
    setRun(r);
    watch.current?.abort();
    const controller = new AbortController();
    watch.current = controller;
    if (["CREATED", "RUNNING"].includes(r.state))
      api
        .watch(
          r.id,
          (value) => {
            if (controller.signal.aborted) return;
            setRun(value);
            if (!["CREATED", "RUNNING"].includes(value.state))
              refresh().catch((e) => setError(e.message));
          },
          controller.signal,
        )
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        });
  }
  useEffect(() => {
    let disposed = false;
    Promise.all([
      api.json("/conversations"),
      api.json("/businesses"),
      api.json("/studio/products"),
    ])
      .then(([c, b, p]) => {
        if (disposed) return;
        setConvos(c);
        setBusinesses(b);
        setProducts(p);
        const remembered = sessionStorage.getItem("evolvyn-growth:" + scope);
        const match = c.find(
          (x: any) =>
            x.id === (remembered || conversation?.id) &&
            x.project_id === (projectId || null) &&
            (!businessId || x.business_id === businessId),
        );
        setBusiness(businessId || match?.business_id || "");
        setConversationId(match?.id || "");
        setInitializedScope(scope);
        setLoading(false);
      })
      .catch((e) => {
        if (!disposed) {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => {
      disposed = true;
      generation.current++;
      watch.current?.abort();
    };
  }, [scope]);
  useEffect(() => {
    if (initializedScope !== scope) return;
    selected.current = conversationId;
    if (conversationId) {
      sessionStorage.setItem("evolvyn-growth:" + scope, conversationId);
      load(conversationId);
    } else {
      generation.current++;
      watch.current?.abort();
      setWorkspace(null);
      setReport(null);
      setRun(null);
      setLoading(false);
      sessionStorage.removeItem("evolvyn-growth:" + scope);
    }
  }, [conversationId, scope, initializedScope]);
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function createConversation() {
    const c = await api.json("/conversations", {
      method: "POST",
      body: JSON.stringify({
        title: currentBusiness
          ? currentBusiness.name + " growth evidence"
          : "Growth evidence",
        goal:
          currentBusiness?.goal ||
          "Understand sales, customer needs and growth opportunities",
        business_id: business || null,
        project_id: projectId || null,
      }),
    });
    setConvos((v) => [c, ...v]);
    setConversationId(c.id);
    setTab("evidence");
  }
  async function upload(file: File) {
    const id = conversationId;
    const form = new FormData();
    form.append("file", file);
    await api.json(`/conversations/${id}/files`, {
      method: "POST",
      body: form,
    });
    await refresh(id);
    setNotice(
      "Evidence uploaded. Create a new snapshot to include this file; previous snapshots stay unchanged.",
    );
  }
  const hasEvidence = files.length > 0;
  return (
    <div className="growth-workspace" aria-label="Business growth workspace">
      <header className="growth-header">
        <div>
          <span className="eyebrow">YOUR BUSINESS, MOVING FORWARD</span>
          <h1>
            Grow your business<span>.</span>
          </h1>
          <p>
            Understand what changed. Decide what matters. Measure what works.
          </p>
        </div>
        <button
          className="growth-quiet"
          disabled={initializedScope !== scope || busy}
          onClick={() => {
            setNewBusiness(false);
            setProfile(!profile);
          }}
        >
          <Settings2 size={17} />
          Business profile
        </button>
      </header>
      <section
        className="growth-context"
        aria-label="Growth workspace selection"
      >
        <label>
          Business
          <select
            aria-label="Growth business"
            value={business}
            disabled={busy || !!projectId || initializedScope !== scope}
            onChange={(e) => {
              setBusiness(e.target.value);
              setConversationId("");
            }}
          >
            <option value="">All accessible businesses</option>
            {businesses.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Evidence workspace
          <select
            aria-label="Growth conversation"
            disabled={busy || initializedScope !== scope}
            value={conversationId}
            onChange={(e) => setConversationId(e.target.value)}
          >
            <option value="">Choose conversation</option>
            {convos.filter(scoped).map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </label>
        <button
          disabled={busy || initializedScope !== scope}
          onClick={() => act(createConversation)}
        >
          <Plus size={16} />
          Create evidence conversation
        </button>
        <ToolAccess
          api={api}
          onManage={onManage}
          inline
          calls={parseCalls(contextJson)}
          onChange={(v) => setContextJson(JSON.stringify(v))}
          conversationId={conversationId}
        />
      </section>
      {profile && (
        <form
          className="growth-panel growth-profile"
          key={(newBusiness ? "new" : business) || "none"}
          onSubmit={(e) => {
            e.preventDefault();
            const d = Object.fromEntries(new FormData(e.currentTarget));
            act(async () => {
              const b = await api.json(
                "/businesses" +
                  (!newBusiness && business ? "/" + business : ""),
                {
                  method: !newBusiness && business ? "PUT" : "POST",
                  body: JSON.stringify({ ...d, kind: "ecommerce" }),
                },
              );
              setBusinesses((v) => [b, ...v.filter((x) => x.id !== b.id)]);
              if (!projectId) {
                setBusiness(b.id);
                if (newBusiness) setConversationId("");
              }
              setProfile(false);
              setNotice(
                "Business profile saved. Provider authorization is separate; no account has been connected.",
              );
            });
          }}
        >
          <div className="growth-section-heading">
            <h2>
              {newBusiness || !business
                ? "Set up your business"
                : "Business profile"}
            </h2>
            <button type="button" onClick={() => setNewBusiness(true)}>
              Add another business
            </button>
          </div>
          <p>
            Describe your business. This does not authorize access to store, CRM
            or social accounts. Reporting currency does not convert imported
            amounts.
          </p>
          <div className="growth-form-grid">
            {[
              ["name", "Business name"],
              ["product", "Products / category"],
              ["business_model", "Business model"],
              ["goal", "Business goal"],
              ["website", "Website (HTTPS)"],
              ["timezone", "Reporting timezone"],
              ["reporting_currency", "Reporting currency"],
              ["reporting_objectives", "Reporting objectives"],
            ].map(([key, label]) => (
              <label key={key}>
                {label}
                <input
                  name={key}
                  required={["name", "goal", "timezone"].includes(key)}
                  maxLength={
                    key === "name"
                      ? 100
                      : key === "website"
                        ? 2000
                        : key === "timezone"
                          ? 80
                          : key === "reporting_currency"
                            ? 3
                            : key === "business_model"
                              ? 500
                              : 1000
                  }
                  defaultValue={
                    newBusiness
                      ? ""
                      : currentBusiness?.[key] ||
                        (key === "timezone" ? "UTC" : "")
                  }
                  placeholder={
                    key === "timezone"
                      ? "Asia/Kolkata"
                      : key === "reporting_currency"
                        ? "INR"
                        : ""
                  }
                />
              </label>
            ))}
          </div>
          <button className="studio-primary" disabled={busy}>
            Save business profile
          </button>
        </form>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="growth-notice" role="status">
          <CheckCircle2 size={17} />
          {notice}
        </p>
      )}
      <nav className="growth-tabs" aria-label="Growth sections">
        {(
          [
            ["overview", "Overview", TrendingUp],
            ["evidence", "Evidence", Database],
            ["actions", "Action plan", Target],
            ["monitoring", "Monitoring", Activity],
          ] as const
        ).map(([id, title, Icon]) => (
          <button
            key={id}
            aria-current={tab === id ? "page" : undefined}
            onClick={() => setTab(id)}
          >
            <Icon size={18} />
            {title}
            {id === "actions" && !!report?.actions?.length && (
              <span>{report.actions.length}</span>
            )}
          </button>
        ))}
      </nav>
      {loading ? (
        <div className="growth-panel" role="status">
          Loading your business evidence…
        </div>
      ) : (
        <>
          {tab === "overview" && (
            <>
              <section className="growth-hero">
                <div>
                  <span className="growth-badge">
                    <ShieldCheck size={15} />
                    {report
                      ? "Saved evidence snapshot"
                      : "START WITH YOUR BUSINESS DATA"}
                  </span>
                  <h2>
                    {report
                      ? report.query
                      : "Your next growth decision starts here."}
                  </h2>
                  <p>
                    {report
                      ? `Captured ${date(report.created_at)}. Observations from your data, with hypotheses kept separate.`
                      : "Bring your sales and customer feedback into one workspace. Get a clear baseline, review opportunities, and track the actions you choose."}
                  </p>
                  <button
                    className="studio-primary"
                    onClick={() => setTab("evidence")}
                  >
                    {report
                      ? "Explore the evidence"
                      : "Add your first evidence"}
                    <ArrowUpRight size={18} />
                  </button>
                </div>
                <div className="growth-loop" aria-label="Growth process">
                  <span>
                    <Database size={19} />
                    Observe
                  </span>
                  <i />
                  <span>
                    <Lightbulb size={19} />
                    Understand
                  </span>
                  <i />
                  <span>
                    <ShieldCheck size={19} />
                    Approve
                  </span>
                  <i />
                  <span>
                    <TrendingUp size={19} />
                    Measure
                  </span>
                </div>
              </section>
              <div className="growth-kpis" aria-label="Business performance">
                {(data?.kind === "sales"
                  ? [
                      [
                        data.net_revenue === null
                          ? "Gross sales"
                          : "Net revenue",
                        `${data.net_revenue ?? data.gross_sales} ${data.currency || "currency unspecified"}`,
                      ],
                      ["Distinct orders", data.orders],
                      [
                        data.net_revenue === null
                          ? "Gross average order value"
                          : "Average order value",
                        `${(data.net_revenue === null ? data.gross_average_order_value : data.average_order_value) ?? "Unavailable"} ${data.currency || ""}`,
                      ],
                      ["Ordered units", data.units_sold],
                    ]
                  : [
                      ["Revenue", "Needs sales data"],
                      ["Orders", "Needs sales data"],
                      ["Average order value", "Needs sales data"],
                      ["Evidence files", files.length],
                    ]
                ).map(([label, value]) => (
                  <article key={String(label)}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                    <small>
                      {data?.kind === "sales"
                        ? "Calculated from selected sales snapshot"
                        : "No values inferred"}
                    </small>
                  </article>
                ))}
              </div>
              <div className="growth-overview-grid">
                <section className="growth-panel">
                  <div className="growth-section-heading">
                    <h2>What deserves your attention</h2>
                    <Lightbulb size={20} />
                  </div>
                  {report ? (
                    report.actions.slice(0, 3).map((a: any) => (
                      <button
                        className="growth-opportunity"
                        key={a.id}
                        onClick={() => setTab("actions")}
                      >
                        <span className="growth-number">
                          {a.type === "measurement" ? (
                            <Database size={18} />
                          ) : (
                            <Target size={18} />
                          )}
                        </span>
                        <span>
                          <small>Hypothesis · {a.type}</small>
                          <strong>{a.title}</strong>
                          <span>
                            {a.evidence.length} supporting reference
                            {a.evidence.length === 1 ? "" : "s"} · validate
                            before acting
                          </span>
                        </span>
                        <ArrowUpRight size={18} />
                      </button>
                    ))
                  ) : (
                    <div className="growth-empty">
                      <BarChart3 size={32} />
                      <h3>A useful baseline comes first.</h3>
                      <p>
                        Upload a sales CSV or customer feedback, then analyze a
                        specific business question. Recommendations will appear
                        here.
                      </p>
                    </div>
                  )}
                </section>
                <section className="growth-panel">
                  <div className="growth-section-heading">
                    <h2>Evidence health</h2>
                    <Database size={20} />
                  </div>
                  <dl className="growth-health">
                    <div>
                      <dt>Attached evidence</dt>
                      <dd>
                        {files.length} file{files.length === 1 ? "" : "s"}
                      </dd>
                    </div>
                    <div>
                      <dt>Latest snapshot</dt>
                      <dd>{date(report?.created_at)}</dd>
                    </div>
                    <div>
                      <dt>Live account sync</dt>
                      <dd>Not configured here</dd>
                    </div>
                    <div>
                      <dt>Forecast</dt>
                      <dd>Not available</dd>
                    </div>
                  </dl>
                  <p>
                    {report?.forecast?.reason ||
                      "A forecast requires comparable, complete first-party history and a tested baseline. Nothing is projected from missing data."}
                  </p>
                  <button onClick={() => setTab("evidence")}>
                    Review sources <ArrowUpRight size={15} />
                  </button>
                </section>
              </div>
              {data?.kind === "sales" && (
                <section className="growth-panel">
                  <div className="growth-section-heading">
                    <h2>Product contribution</h2>
                    <span>
                      Observation · {data.currency || "currency unspecified"}
                    </span>
                  </div>
                  <p>
                    Snapshot sales contribution, not demand or profit. Up to 8
                    products shown; all validated rows contribute to the totals
                    above.
                  </p>
                  <div className="growth-product-bars">
                    {data.products.slice(0, 8).map((p: any) => {
                      const amount = Number(
                          data.net_revenue === null
                            ? p.gross_sales
                            : p.net_revenue,
                        ),
                        max = Math.max(
                          ...data.products.map((x: any) =>
                            Number(
                              data.net_revenue === null
                                ? x.gross_sales
                                : x.net_revenue,
                            ),
                          ),
                          1,
                        );
                      return (
                        <div key={p.product_id}>
                          <span>{p.product_name || p.product_id}</span>
                          <meter
                            min="0"
                            max={max}
                            value={amount}
                            aria-label={
                              (p.product_name || p.product_id) +
                              " sales contribution"
                            }
                          />
                          <strong>
                            {data.net_revenue === null
                              ? p.gross_sales
                              : p.net_revenue}
                          </strong>
                        </div>
                      );
                    })}
                  </div>
                  <small>
                    {data.citation} · {data.period?.start || "Dates missing"} –{" "}
                    {data.period?.end || "Dates missing"}. Observed dates do not
                    prove full coverage.
                  </small>
                </section>
              )}
            </>
          )}
          {tab === "evidence" && (
            <>
              <div className="growth-section-heading">
                <div>
                  <h2>Your evidence, in one place.</h2>
                  <p>
                    Upload first-party data. Add authorized read tools when
                    configured. Create an immutable snapshot.
                  </p>
                </div>
              </div>
              <div className="growth-evidence-grid">
                <section className="growth-panel">
                  <h3>Customer and performance uploads</h3>
                  <p>
                    Sales CSV, product catalog, funnel export or consented
                    feedback. Missing amounts remain unknown.
                  </p>
                  <label className="growth-upload">
                    <FileUp size={26} />
                    <strong>Add business evidence</strong>
                    <span>TXT, CSV, PDF or DOCX</span>
                    <input
                      aria-label="Growth evidence file"
                      type="file"
                      accept=".txt,.csv,.pdf,.docx"
                      disabled={!conversationId || busy}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) act(() => upload(f));
                        e.target.value = "";
                      }}
                    />
                  </label>
                  {!conversationId && (
                    <p>
                      Choose or create an evidence conversation above to enable
                      uploads.
                    </p>
                  )}
                  <ul className="growth-source-list">
                    {files.map((f: any) => (
                      <li key={f.id}>
                        <Database size={17} />
                        <span>
                          <strong>{f.name}</strong>
                          <small>
                            {f.import?.kind
                              ? "Parsed " + f.import.kind + " data"
                              : "Uploaded document"}{" "}
                            · first-party upload
                          </small>
                        </span>
                      </li>
                    ))}
                  </ul>
                  <details>
                    <summary>Accepted CSV columns</summary>
                    <p>
                      Sales: order_id, product_id (or sku), quantity,
                      unit_price. Add discount, refund, currency and order_date
                      for net revenue and dated outcomes. Catalog: product_id,
                      product_name, unit_price. Funnel: period, visits, paid.
                    </p>
                  </details>
                </section>
                <form
                  className="growth-panel growth-analysis-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const d = Object.fromEntries(new FormData(e.currentTarget));
                    act(async () => {
                      const row = await api.json("/growth/reports", {
                        method: "POST",
                        body: JSON.stringify({
                          conversation_id: conversationId,
                          product_id: d.product_id || null,
                          query,
                          window_days: Number(d.window_days),
                          public_research: d.public_research === "on",
                          context_tools: parseCalls(contextJson),
                        }),
                      });
                      await refresh();
                      setReport(row);
                      setNotice(
                        "Evidence snapshot saved. Calculations and rule-based hypotheses are ready; use Action plan for model review and execution.",
                      );
                    });
                  }}
                >
                  <h3>What would you like to understand?</h3>
                  <label>
                    Business question
                    <input
                      aria-label="Growth research query"
                      required
                      minLength={3}
                      maxLength={200}
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Which products should we focus on, and why?"
                    />
                  </label>
                  <div className="growth-form-grid">
                    <label>
                      Product plan (optional)
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
                      Public comparison window
                      <select name="window_days" defaultValue="30">
                        <option value="7">7 days vs previous 7 days</option>
                        <option value="30">30 days vs previous 30 days</option>
                        <option value="90">90 days vs previous 90 days</option>
                      </select>
                    </label>
                  </div>
                  <label className="checkbox">
                    <input name="public_research" type="checkbox" />
                    Include public discussion activity
                  </label>
                  <p className="growth-help">
                    Opt-in sends this question to Hacker News via Algolia. It is
                    public chatter, not connected social analytics or
                    representative market research.
                  </p>
                  <button
                    className="studio-primary"
                    disabled={busy || !conversationId}
                  >
                    {busy ? "Collecting evidence…" : "Analyze growth evidence"}
                    <ArrowUpRight size={17} />
                  </button>
                  <small>
                    Snapshot metrics and suggestions use deterministic evidence
                    rules. Model-backed review is available in Action plan.
                  </small>
                </form>
              </div>
              <section className="growth-panel">
                <label>
                  Saved growth snapshots
                  <select
                    aria-label="Saved growth report"
                    value={report?.id || ""}
                    onChange={(e) =>
                      setReport(
                        reports.find((r: any) => r.id === e.target.value) ||
                          null,
                      )
                    }
                  >
                    <option value="">Choose report</option>
                    {reports.map((r: any) => (
                      <option key={r.id} value={r.id}>
                        {r.query} · {date(r.created_at)}
                      </option>
                    ))}
                  </select>
                </label>
              </section>
              {report && (
                <section className="growth-panel growth-snapshot">
                  <span className="growth-badge">
                    Observation · immutable snapshot
                  </span>
                  <h2>{report.query}</h2>
                  <p>
                    {date(report.created_at)} ·{" "}
                    {report.analysis_method ||
                      "Evidence extraction and calculated metrics; suggestions require validation."}
                  </p>
                  {data && <CommerceMetrics data={data} />}
                  <h3>First-party observations</h3>
                  {report.report.facts?.map((f: any, i: number) => (
                    <p key={i}>
                      {f.period}: {f.conversion}% conversion ({f.paid} /{" "}
                      {f.visits}) · {f.source}
                    </p>
                  ))}
                  {report.first_party_change && (
                    <p>{report.first_party_change.classification}</p>
                  )}
                  {report.first_party_change?.status === "available" && (
                    <p>
                      Visits change:{" "}
                      {report.first_party_change.visits_change_percent}% · Paid
                      outcomes change:{" "}
                      {report.first_party_change.paid_outcomes_change_percent ??
                        "No nonzero baseline"}
                      {report.first_party_change
                        .paid_outcomes_change_percent !== null
                        ? "%"
                        : ""}{" "}
                      · Conversion change:{" "}
                      {
                        report.first_party_change
                          .conversion_change_percentage_points
                      }{" "}
                      percentage points.
                    </p>
                  )}
                  {report.report.themes?.map((t: any) => (
                    <article className="growth-finding" key={t.id}>
                      <span className="growth-badge">
                        Observation · keyword signal
                      </span>
                      <h4>{t.label}</h4>
                      <p>
                        {t.keyword_mentions} keyword mentions ·{" "}
                        {t.sources.join("; ")}
                      </p>
                      <p>{t.classification}</p>
                    </article>
                  ))}
                  <h3>Market discussion signal</h3>
                  <p>{report.market.classification}</p>
                  {report.market.status === "available" && (
                    <>
                      <p>
                        {report.market.previous.count} →{" "}
                        {report.market.current.count} matching discussions ·
                        change {report.market.absolute_change}. Two{" "}
                        {report.market.window_days}-day windows.
                      </p>
                      <p>
                        Observation window {report.market.previous.start} –{" "}
                        {report.market.current.end}; retrieved{" "}
                        {date(report.created_at)}.
                      </p>
                      {report.market.current.sources.map((s: any) => (
                        <p key={s.url}>
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {s.title}
                          </a>{" "}
                          · {s.citation} · {s.published_at}
                        </p>
                      ))}
                    </>
                  )}
                  {report.sources?.map((s: any) => (
                    <details className="growth-finding" key={s.document_id}>
                      <summary>{s.name} · provenance & quality</summary>
                      <dl className="growth-health">
                        {Object.entries(s).map(([k, v]) => (
                          <div key={k}>
                            <dt>{k.replaceAll("_", " ")}</dt>
                            <dd>
                              {typeof v === "object"
                                ? JSON.stringify(v)
                                : String(v ?? "Not supplied")}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    </details>
                  ))}
                  {report.connector_evidence?.map((s: any) => (
                    <details key={s.citation}>
                      <summary>
                        {s.citation} · connector observation, freshness
                        unverified
                      </summary>
                      <pre>{s.excerpt}</pre>
                    </details>
                  ))}
                  <button onClick={() => setTab("actions")}>
                    Review proposed actions <ArrowUpRight size={16} />
                  </button>
                </section>
              )}
            </>
          )}
          {tab === "actions" && (
            <>
              <div className="growth-section-heading">
                <div>
                  <h2>Turn insight into a measured action.</h2>
                  <p>
                    Hypotheses first. Human approval before execution. Real
                    receipts after it.
                  </p>
                </div>
              </div>
              {!report ? (
                <section className="growth-panel growth-empty">
                  <Target size={32} />
                  <h3>No snapshot selected yet.</h3>
                  <p>
                    Analyze your business evidence to create a source-linked
                    action plan.
                  </p>
                  <button onClick={() => setTab("evidence")}>
                    Go to evidence
                  </button>
                </section>
              ) : (
                <>
                  <div className="growth-action-grid">
                    {report.actions.map((a: any) => (
                      <article className="growth-panel" key={a.id}>
                        <span className="growth-badge">
                          Hypothesis · {a.type}
                        </span>
                        <h3>{a.title}</h3>
                        <p>{a.suggestion}</p>
                        <details>
                          <summary>Rationale, measurement & risks</summary>
                          <p>{a.confidence}</p>
                          <p>
                            <strong>Measure:</strong> {a.metric}
                          </p>
                          <p>
                            <strong>Evidence:</strong>{" "}
                            {a.evidence.join("; ") ||
                              "No direct supporting source; hypothesis only"}
                          </p>
                          <p>
                            <strong>Expected outcome:</strong> A testable
                            decision and measured baseline. Business lift is
                            unknown.
                          </p>
                          <p>
                            <strong>Risks:</strong> Incomplete exports, changing
                            product mix and nonrepresentative customer or public
                            samples. Alternative explanations need
                            investigation.
                          </p>
                        </details>
                        <button
                          disabled={busy}
                          onClick={() =>
                            act(async () => {
                              await api.json(
                                `/growth/reports/${report.id}/propose`,
                                {
                                  method: "POST",
                                  body: JSON.stringify({ action_id: a.id }),
                                },
                              );
                              setNotice(
                                "Proposed as draft decision memory. Nothing has been approved or executed.",
                              );
                            })
                          }
                        >
                          Propose for review <ArrowUpRight size={15} />
                        </button>
                      </article>
                    ))}
                  </div>
                  <section className="growth-panel">
                    <h2>Run an analysis & create an experiment brief</h2>
                    <p>
                      Use your workspace model route or explicitly choose
                      evidence rules. The workflow uses current attached
                      evidence; the saved snapshot above stays unchanged.
                      Approval creates internal tasks only.
                    </p>
                    <div className="growth-inline-form">
                      <label>
                        Analysis route
                        <select
                          aria-label="Growth analysis route"
                          value={route}
                          onChange={(e) => setRoute(e.target.value)}
                        >
                          <option value="default">
                            Workspace / agent model route
                          </option>
                          <option value="evidence">
                            Evidence rules · no model
                          </option>
                          <option value="local">Local AI</option>
                        </select>
                      </label>
                      <button
                        className="studio-primary"
                        disabled={
                          busy ||
                          !hasEvidence ||
                          ["CREATED", "RUNNING"].includes(run?.state)
                        }
                        onClick={() =>
                          act(async () => {
                            const r = await api.json(
                              `/conversations/${conversationId}/runs`,
                              {
                                method: "POST",
                                body: JSON.stringify({
                                  text: report.query,
                                  mode: route,
                                  allow_fallback: false,
                                  analysis_kind: "business",
                                  context_tools: parseCalls(contextJson),
                                }),
                              },
                            );
                            follow(r);
                          })
                        }
                      >
                        Start growth workflow <ArrowUpRight size={17} />
                      </button>
                    </div>
                    {run && (
                      <>
                        <ReactMarkdown>{run.output || ""}</ReactMarkdown>
                        <ExecutionView
                          key={run.id}
                          run={run}
                          busy={busy}
                          onCancel={(id) =>
                            act(async () => {
                              follow(
                                await api.json(`/executions/${id}/cancel`, {
                                  method: "POST",
                                }),
                              );
                              await refresh();
                            })
                          }
                          onDecide={(r, approve, plan, recommendationId) =>
                            act(async () => {
                              follow(
                                await api.json(`/executions/${r.id}/decision`, {
                                  method: "POST",
                                  body: JSON.stringify({
                                    approve,
                                    plan,
                                    recommendation_id: recommendationId,
                                  }),
                                }),
                              );
                              await refresh();
                            })
                          }
                          onArtifact={() =>
                            document
                              .getElementById("growth-outcomes")
                              ?.scrollIntoView({ behavior: "smooth" })
                          }
                        />
                      </>
                    )}
                  </section>
                  <GrowthReview
                    key={report.id}
                    api={api}
                    report={report}
                    initialRun={workspace?.executions.find(
                      (r: any) =>
                        r.engine === "langgraph_discussion" &&
                        r.discussion_input?.growth_report_id === report.id,
                    )}
                  />
                  <section className="growth-panel">
                    <div className="growth-section-heading">
                      <div>
                        <h2>Campaign planning</h2>
                        <p>
                          Save a complete plan for review. No verified social
                          publisher is configured.
                        </p>
                      </div>
                      <button onClick={() => setCampaign(!campaign)}>
                        <Plus size={17} />
                        Plan a campaign
                      </button>
                    </div>
                    {campaign && (
                      <GrowthCampaign
                        api={api}
                        report={report}
                        onSaved={async () => {
                          setCampaign(false);
                          await refresh();
                          setNotice(
                            "Campaign draft saved. No publication or spend occurred.",
                          );
                        }}
                      />
                    )}
                    {workspace?.campaigns.map((c: any) => (
                      <details className="growth-finding" key={c.id}>
                        <summary>
                          {c.plan.objective} · Draft · {date(c.created_at)}
                        </summary>
                        <dl className="growth-health">
                          {Object.entries(c.plan).map(([k, v]) => (
                            <div key={k}>
                              <dt>{k.replaceAll("_", " ")}</dt>
                              <dd>{String(v)}</dd>
                            </div>
                          ))}
                        </dl>
                        <p>{c.classification}</p>
                      </details>
                    ))}
                  </section>
                </>
              )}
              <section id="growth-outcomes" className="growth-panel">
                <h2>Execution & outcomes</h2>
                <p>
                  Execution receipts confirm internal tasks were saved. Sales
                  outcomes require a separate, comparable follow-up export; a
                  before/after change does not establish causality.
                </p>
                {!workspace?.artifacts?.length && (
                  <p>
                    No approved experiment has been executed in this workspace
                    yet.
                  </p>
                )}
                {workspace?.tasks.map((t: any) => (
                  <div className="growth-task" key={t.id}>
                    <span>
                      <strong>{t.title}</strong>
                      <small>{t.notes || "Internal experiment task"}</small>
                    </span>
                    <label>
                      Status
                      <select
                        aria-label={"Task status: " + t.title}
                        value={t.status}
                        disabled={busy}
                        onChange={(e) =>
                          act(async () => {
                            await api.json("/tasks/" + t.id, {
                              method: "PATCH",
                              body: JSON.stringify({
                                status: e.target.value,
                                notes: t.notes || "",
                              }),
                            });
                            await refresh();
                          })
                        }
                      >
                        {["todo", "in_progress", "done", "cancelled"].map(
                          (s) => (
                            <option key={s} value={s}>
                              {s.replaceAll("_", " ")}
                            </option>
                          ),
                        )}
                      </select>
                    </label>
                  </div>
                ))}
                {workspace?.artifacts.map((a: any) => (
                  <article className="growth-finding" key={a.id}>
                    <h3>{a.title || "Saved experiment brief"}</h3>
                    <p>
                      {a.execution_result?.verified_task_count ?? "Unknown"}{" "}
                      tracked tasks ·{" "}
                      {a.execution_result?.status || "Receipt unavailable"}
                    </p>
                    <ReactMarkdown>{a.plan || a.content || ""}</ReactMarkdown>
                    {(a.commerce_baseline || a.baseline) && (
                      <form
                        className="growth-inline-form"
                        onSubmit={(e) => {
                          e.preventDefault();
                          const d = Object.fromEntries(
                            new FormData(e.currentTarget),
                          );
                          act(async () => {
                            await api.json(`/artifacts/${a.id}/measure`, {
                              method: "POST",
                              body: JSON.stringify(d),
                            });
                            await refresh();
                            setNotice(
                              "Follow-up observation recorded. This comparison does not prove causation.",
                            );
                          });
                        }}
                      >
                        <label>
                          Follow-up CSV
                          <select
                            aria-label="Follow-up CSV"
                            name="document_id"
                            required
                            defaultValue=""
                          >
                            <option value="">Choose uploaded follow-up</option>
                            {files
                              .filter((f: any) =>
                                f.name.toLowerCase().endsWith(".csv"),
                              )
                              .map((f: any) => (
                                <option key={f.id} value={f.id}>
                                  {f.name}
                                </option>
                              ))}
                          </select>
                        </label>
                        <label>
                          Measurement notes
                          <input name="notes" maxLength={2000} />
                        </label>
                        <button disabled={busy}>Compare observations</button>
                      </form>
                    )}
                    {workspace.measurements
                      .filter((m: any) => m.artifact === a.id)
                      .map((m: any) => (
                        <div key={m.id}>
                          <span className="growth-badge">
                            Verified calculation · observed outcome
                          </span>
                          <p>
                            {date(m.measured_at)} · {m.classification}
                          </p>
                          {Object.entries(m.changes || {}).map(
                            ([k, v]: [string, any]) => (
                              <p key={k}>
                                {k.replaceAll("_", " ")}: {v.before} → {v.after}{" "}
                                · change {v.absolute_change ?? "Unavailable"} (
                                {v.percent_change === null
                                  ? "No nonzero baseline"
                                  : v.percent_change + "%"}
                                )
                              </p>
                            ),
                          )}
                          {m.change_percentage_points !== undefined && (
                            <p>
                              Conversion change: {m.change_percentage_points}{" "}
                              percentage points
                            </p>
                          )}
                          {m.comparable_duration === false && (
                            <p>
                              Observed date spans differ; raw totals are not
                              comparable as growth rates.
                            </p>
                          )}
                        </div>
                      ))}
                  </article>
                ))}
              </section>
            </>
          )}
          {tab === "monitoring" && (
            <>
              <section className="growth-panel">
                <span className="growth-badge">
                  <Clock3 size={15} />
                  Recurring evidence review
                </span>
                <h2>Keep checking what matters.</h2>
                <p>
                  Uses Evolvyn’s existing durable scheduler. Reviews the latest
                  attached evidence and queues proposed actions; it never
                  approves them. This does not sync external stores or social
                  accounts.
                </p>
                <form
                  className="growth-inline-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const d = Object.fromEntries(new FormData(e.currentTarget));
                    act(async () => {
                      await api.json("/schedules", {
                        method: "POST",
                        body: JSON.stringify({
                          conversation_id: conversationId,
                          query: d.query,
                          interval_minutes: Number(d.interval_minutes),
                          mode: "evidence",
                          allow_fallback: false,
                        }),
                      });
                      await refresh();
                      setNotice(
                        "Recurring evidence review saved. New proposals still require human approval.",
                      );
                    });
                  }}
                >
                  <label>
                    Review question
                    <input
                      name="query"
                      minLength={3}
                      maxLength={2000}
                      required
                      defaultValue={
                        report?.query ||
                        currentBusiness?.goal ||
                        "Review sales and customer evidence; identify changes and testable actions"
                      }
                    />
                  </label>
                  <label>
                    Review cadence
                    <select name="interval_minutes" defaultValue="1440">
                      <option value="1440">Every 24 hours</option>
                      <option value="10080">Every 7 days</option>
                    </select>
                  </label>
                  <button
                    className="studio-primary"
                    disabled={busy || !conversationId || !hasEvidence}
                  >
                    Schedule evidence review
                  </button>
                </form>
                <p className="growth-help">
                  Fixed elapsed cadence. Due times are displayed in your browser
                  timezone. Source polling, provider sync, threshold rules,
                  quiet hours and growth forecasting are not implemented by this
                  schedule.
                </p>
              </section>
              {!workspace?.schedules.length && (
                <section className="growth-panel growth-empty">
                  <Activity size={30} />
                  <h3>No recurring reviews yet.</h3>
                  <p>
                    Add evidence, then schedule a review. “Enabled” means
                    scheduled, not proof of a successful analysis.
                  </p>
                </section>
              )}
              {workspace?.schedules.map((s: any) => {
                const r = workspace.executions.find(
                  (r: any) => r.id === s.last_run,
                );
                return (
                  <section className="growth-panel" key={s.id}>
                    <span className="growth-badge">
                      {!s.enabled
                        ? "Paused"
                        : s.last_error
                          ? "Failed to start"
                          : !s.last_run
                            ? "Never run"
                            : r?.state === "FAILED"
                              ? "Last analysis failed"
                              : r?.state === "WAITING_FOR_APPROVAL"
                                ? "Awaiting human approval"
                                : r?.state || "State unavailable"}
                    </span>
                    <h3>{s.query}</h3>
                    <p>
                      Every {s.interval_minutes / 60} hours · Next due{" "}
                      {date(s.next_run_at)}
                    </p>
                    <p>
                      Last run: {s.last_run || "None"} ·{" "}
                      {s.last_error || "No launch error recorded"}
                    </p>
                    <div className="growth-inline-form">
                      <button
                        disabled={busy}
                        onClick={() =>
                          act(async () => {
                            await api.json("/schedules/" + s.id, {
                              method: "PATCH",
                              body: JSON.stringify({ enabled: !s.enabled }),
                            });
                            await refresh();
                          })
                        }
                      >
                        {s.enabled ? "Pause review" : "Resume review"}
                      </button>
                      <button
                        disabled={busy}
                        onClick={() =>
                          act(async () => {
                            const r = await api.json(
                              "/schedules/" + s.id + "/run",
                              { method: "POST" },
                            );
                            follow(r);
                            await refresh();
                            setTab("actions");
                          })
                        }
                      >
                        Run review now
                      </button>
                    </div>
                  </section>
                );
              })}
              <button
                onClick={() => act(() => refresh())}
                disabled={busy || !conversationId}
              >
                <RefreshCw size={16} />
                Refresh review status
              </button>
            </>
          )}
        </>
      )}
      <footer className="growth-footer">
        <ShieldCheck size={15} />
        Facts have sources. Hypotheses need validation. Actions need your
        approval.
      </footer>
    </div>
  );
}
