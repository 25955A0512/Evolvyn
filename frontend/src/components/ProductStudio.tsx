import { useEffect, useState } from "react";
import {
  ArrowUp,
  Code2,
  Download,
  Eye,
  FileCode2,
  Check,
  Play,
  Plus,
} from "lucide-react";
import type { client } from "../api";
type API = ReturnType<typeof client>;
function ProductPreview({ api, build }: { api: API; build: any }) {
  const [entity, setEntity] = useState(build.spec.entities[0]?.name || ""),
    [rows, setRows] = useState<any[]>([]),
    [error, setError] = useState("");
  const schema = build.spec.entities.find((e: any) => e.name === entity);
  async function load() {
    setRows(
      await api.json("/studio/builds/" + build.id + "/preview/" + entity),
    );
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [entity, build.id]);
  return (
    <section
      className={"product-preview " + build.spec.theme}
      style={{ "--product-accent": build.spec.accent } as any}
    >
      <div className="prototype-label">
        <span className="live-dot" />
        Interactive prototype · saved workspace data
      </div>
      <div className="product-preview-header">
        <div>
          <small>{build.spec.audience}</small>
          <h2>{build.spec.name}</h2>
          <p>{build.spec.goal}</p>
        </div>
        <span className="prototype-avatar">{build.spec.name[0]}</span>
      </div>
      <nav>
        {build.spec.entities.map((e: any) => (
          <button
            key={e.name}
            className={entity === e.name ? "selected" : ""}
            onClick={() => setEntity(e.name)}
          >
            {e.label}
          </button>
        ))}
      </nav>
      {error && (
        <div role="alert" className="error">
          {error}
        </div>
      )}
      <div className="prototype-stat">
        <strong>{rows.length}</strong>
        <span>{schema?.label} in this prototype</span>
      </div>
      {schema && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const values: any = Object.fromEntries(new FormData(form));
            for (const f of schema.fields)
              if (f.type === "number") values[f.name] = Number(values[f.name]);
            try {
              await api.json(
                "/studio/builds/" + build.id + "/preview/" + entity,
                { method: "POST", body: JSON.stringify(values) },
              );
              form.reset();
              await load();
            } catch (e: any) {
              setError(e.message);
            }
          }}
        >
          {schema.fields.map((f: any) => (
            <label key={f.name}>
              {f.label}
              <input
                name={f.name}
                type={
                  f.type === "number"
                    ? "number"
                    : f.type === "date"
                      ? "date"
                      : f.type === "email"
                        ? "email"
                        : "text"
                }
                required
                maxLength={2000}
              />
            </label>
          ))}
          <button className="primary">Add {schema.label}</button>
        </form>
      )}
      <div className="prototype-records">
        {!rows.length && <p>Your product is ready for its first record.</p>}
        {rows.map((row) => (
          <article key={row.id}>
            <div>
              {Object.entries(row.data).map(([key, value]) => (
                <span key={key}>
                  <small>
                    {schema.fields.find((f: any) => f.name === key)?.label ||
                      key}
                  </small>
                  <strong>{String(value)}</strong>
                </span>
              ))}
            </div>
            <button
              onClick={async () => {
                try {
                  await api.json(
                    "/studio/builds/" +
                      build.id +
                      "/preview/" +
                      entity +
                      "/" +
                      row.id,
                    { method: "DELETE" },
                  );
                  await load();
                } catch (e: any) {
                  setError(e.message);
                }
              }}
            >
              Delete
            </button>
          </article>
        ))}
      </div>
      <small className="prototype-footnote">
        This prototype uses Evolvyn workspace storage. The generated app
        includes its own accounts and database; it has not been deployed.
      </small>
    </section>
  );
}
export function ProductStudio({
  api,
  projectId,
}: {
  api: API;
  projectId: string;
}) {
  const [decisions, setDecisions] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]),
    [product, setProduct] = useState<any>(null),
    [builds, setBuilds] = useState<any[]>([]),
    [build, setBuild] = useState<any>(null),
    [answer, setAnswer] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [view, setView] = useState("preview"),
    [file, setFile] = useState("frontend/src/main.jsx");
  async function load() {
    const [p, b, m] = await Promise.all([
      api.json("/studio/products"),
      api.json("/studio/builds"),
      api.json("/memory"),
    ]);
    setProducts(p);
    setBuilds(b);
    setDecisions(
      m.filter((m: any) => m.state === "ACCEPTED" && m.category === "decision"),
    );
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    setAnswer(product?.next_question?.suggested_answer || "");
  }, [product?.id, product?.revision]);
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
  return (
    <div className="studio-page">
      <div className="studio-page-title">
        <span className="eyebrow">PRODUCT STUDIO</span>
        <h1>From an idea to something real.</h1>
        <p>
          Define the experience, choose your stack, and build a versioned
          application starter with a working prototype.
        </p>
      </div>
      {error && (
        <div role="alert" className="error">
          {error}
        </div>
      )}
      <div className="product-studio-grid">
        <section className="studio-interview">
          <div className="studio-card">
            <div className="studio-card-heading">
              <h3>Your products</h3>
              <button
                aria-label="New product"
                onClick={() => {
                  setProduct(null);
                  setBuild(null);
                }}
              >
                <Plus size={16} />
              </button>
            </div>
            <select
              aria-label="Saved product"
              value={product?.id || ""}
              onChange={(e) => {
                const p = products.find((p) => p.id === e.target.value);
                setProduct(p);
                setBuild(builds.find((b) => b.spec_id === p?.id) || null);
              }}
            >
              <option value="">Start a new product</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · revision {p.revision}
                </option>
              ))}
            </select>
          </div>
          {!product ? (
            <form
              className="studio-card studio-form"
              onSubmit={(e) => {
                e.preventDefault();
                const d = Object.fromEntries(new FormData(e.currentTarget));
                act(async () =>
                  setProduct(
                    await api.json("/studio/products", {
                      method: "POST",
                      body: JSON.stringify({
                        ...d,
                        project_id: projectId || null,
                      }),
                    }),
                  ),
                );
              }}
            >
              <span className="studio-icon">
                <Code2 size={22} />
              </span>
              <h2>What would you like to build?</h2>
              <label>
                Product name
                <input
                  name="name"
                  required
                  minLength={2}
                  maxLength={100}
                  placeholder="Customer insight workspace"
                />
              </label>
              <label>
                Product goal
                <textarea
                  name="goal"
                  required
                  minLength={5}
                  maxLength={2000}
                  placeholder="Describe the product, the problem, and what success looks like…"
                />
              </label>
              <button className="studio-primary" disabled={busy}>
                Start requirements discussion <ArrowUp size={16} />
              </button>
            </form>
          ) : (
            <>
              <div className="interview-messages">
                {product.messages.map((m: any, i: number) => (
                  <div className={"interview-message " + m.role} key={i}>
                    <small>
                      {m.role === "assistant"
                        ? "Evolvyn · Requirements analyst"
                        : "You"}
                    </small>
                    <p>{m.text}</p>
                  </div>
                ))}
              </div>
              {product.next_question ? (
                <form
                  className="studio-card studio-form interview-answer"
                  onSubmit={(e) => {
                    e.preventDefault();
                    act(async () =>
                      setProduct(
                        await api.json(
                          "/studio/products/" + product.id + "/answers",
                          {
                            method: "POST",
                            body: JSON.stringify({
                              field: product.next_question.field,
                              text: answer,
                              revision: product.revision,
                            }),
                          },
                        ),
                      ),
                    );
                  }}
                >
                  <label>
                    {product.next_question.question}
                    {product.next_question.field === "stack" ? (
                      <>
                        <select
                          aria-label="Product stack"
                          value={
                            ["react_fastapi", "react_express"].includes(answer)
                              ? answer
                              : "custom"
                          }
                          onChange={(e) => setAnswer(e.target.value)}
                        >
                          <option value="react_fastapi">
                            React + FastAPI + PostgreSQL
                          </option>
                          <option value="react_express">
                            React + Express + PostgreSQL
                          </option>
                          <option value="custom">
                            Custom stack · requirements only
                          </option>
                        </select>
                        {!["react_fastapi", "react_express"].includes(
                          answer,
                        ) && (
                          <input
                            aria-label="Custom technology stack"
                            value={answer === "custom" ? "" : answer}
                            onChange={(e) => setAnswer(e.target.value)}
                            placeholder="e.g. Vue + Django + PostgreSQL"
                            maxLength={150}
                          />
                        )}
                      </>
                    ) : product.next_question.field === "theme" ? (
                      <select
                        aria-label="Product theme"
                        value={answer}
                        onChange={(e) => setAnswer(e.target.value)}
                      >
                        <option value="light">Light</option>
                        <option value="dark">Dark</option>
                      </select>
                    ) : (
                      <textarea
                        aria-label="Requirement answer"
                        value={answer}
                        onChange={(e) => setAnswer(e.target.value)}
                        required
                        maxLength={8000}
                      />
                    )}
                  </label>
                  <small>Suggested answer — edit it before confirming.</small>
                  <button className="studio-primary" disabled={busy}>
                    Confirm requirement <ArrowUp size={14} />
                  </button>
                </form>
              ) : (
                <div className="studio-card">
                  <span className="studio-complete">
                    <Check size={16} />
                    Requirements captured
                  </span>
                  <p>
                    Review the specification before generating a new source
                    version.
                  </p>
                  <button
                    className="studio-primary"
                    disabled={busy}
                    onClick={() =>
                      act(async () => {
                        const b = await api.json(
                          "/studio/products/" + product.id + "/build",
                          {
                            method: "POST",
                            body: JSON.stringify({
                              revision: product.revision,
                            }),
                          },
                        );
                        setBuild(b);
                        setView("preview");
                      })
                    }
                  >
                    <Play size={15} />
                    {busy ? "Building…" : "Build product starter"}
                  </button>
                </div>
              )}
            </>
          )}
        </section>
        <section className="studio-output">
          {build ? (
            <>
              <div className="studio-output-toolbar">
                <div className="studio-segments">
                  {[
                    { id: "preview", label: "Preview", icon: Eye },
                    { id: "code", label: "Code", icon: FileCode2 },
                    { id: "checks", label: "Build checks", icon: Check },
                  ].map((v) => (
                    <button
                      key={v.id}
                      className={view === v.id ? "selected" : ""}
                      onClick={() => setView(v.id)}
                    >
                      <v.icon size={14} />
                      {v.label}
                    </button>
                  ))}
                </div>
                <button
                  disabled={build.state !== "READY"}
                  onClick={() =>
                    api
                      .download(
                        "/studio/builds/" + build.id + "/download",
                        "evolvyn-product.zip",
                      )
                      .catch((e) => setError(e.message))
                  }
                >
                  <Download size={14} />
                  Download source
                </button>
              </div>
              <div className="build-caption">
                Revision {build.revision} · {build.state} · {build.engine}
              </div>
              {build.error && <p className="error">{build.error}</p>}
              {view === "preview" && build.state === "READY" && (
                <ProductPreview key={build.id} api={api} build={build} />
              )}{" "}
              {view === "code" && (
                <div className="source-browser">
                  <select
                    aria-label="Source file"
                    value={file}
                    onChange={(e) => setFile(e.target.value)}
                  >
                    {Object.keys(build.files).map((f) => (
                      <option key={f}>{f}</option>
                    ))}
                  </select>
                  <pre>{build.files[file]}</pre>
                </div>
              )}
              {view === "checks" && (
                <div className="studio-card">
                  <h3>What actually ran</h3>
                  {build.events.map((e: any, i: number) => (
                    <div className="build-event" key={i}>
                      <Check size={15} />
                      <div>
                        <strong>{e.stage}</strong>
                        <p>{e.detail}</p>
                      </div>
                    </div>
                  ))}
                  {build.checks.map((c: string) => (
                    <p key={c}>
                      <Check size={12} /> {c}
                    </p>
                  ))}
                  <h3>Implemented by this adapter</h3>
                  {build.implemented_capabilities?.map((c: string) => (
                    <p key={c}>{c}</p>
                  ))}
                  {!!build.pending_requirements?.length && (
                    <>
                      <h3>Requirements needing custom implementation</h3>
                      {build.pending_requirements.map((r: string) => (
                        <p key={r}>{r}</p>
                      ))}
                    </>
                  )}
                  <p>{build.integration_status}</p>
                  <p className="muted">{build.validation_scope}</p>
                </div>
              )}
            </>
          ) : (
            <div className="studio-preview-empty">
              <div className="blueprint-art">
                <Code2 size={45} />
                <i />
                <i />
                <i />
              </div>
              <h2>Your next product starts here.</h2>
              <p>
                The requirements analyst will ask about your users, stack,
                visual theme, data model, privacy and acceptance criteria before
                building.
              </p>
              <div>
                <span>01 · Define</span>
                <span>02 · Build</span>
                <span>03 · Review</span>
              </div>
            </div>
          )}
          {product && (
            <details className="studio-card">
              <summary>Requirements · version {product.revision}</summary>
              <pre>{JSON.stringify(product.requirements, null, 2)}</pre>
              <label>
                Revisit a requirement
                <select
                  aria-label="Edit captured requirement"
                  value=""
                  onChange={(e) => {
                    const field = e.target.value;
                    if (!field) return;
                    const value = product.requirements[field];
                    const text =
                      field === "entities"
                        ? JSON.stringify(value, null, 2)
                        : Array.isArray(value)
                          ? value.join(", ")
                          : String(value);
                    setProduct({
                      ...product,
                      next_question: {
                        field,
                        question: "Review and update " + field,
                        suggested_answer: text,
                      },
                    });
                    setAnswer(text);
                  }}
                >
                  <option value="">Choose a requirement to revise</option>
                  {Object.keys(product.requirements).map((field) => (
                    <option key={field} value={field}>
                      {field}
                    </option>
                  ))}
                </select>
              </label>
            </details>
          )}
          {product && (
            <form
              className="studio-card studio-form"
              onSubmit={(e) => {
                e.preventDefault();
                const d = Object.fromEntries(new FormData(e.currentTarget));
                act(async () =>
                  setProduct(
                    await api.json(
                      "/studio/products/" + product.id + "/decisions",
                      {
                        method: "POST",
                        body: JSON.stringify({
                          memory_id: d.memory_id,
                          revision: product.revision,
                          changes: JSON.parse(String(d.changes)),
                        }),
                      },
                    ),
                  ),
                );
              }}
            >
              <h3>Apply a reviewed business decision</h3>
              <p>
                Translate an approved discussion into explicit requirement
                changes. Existing builds stay immutable.
              </p>
              <label>
                Reviewed decision
                <select
                  required
                  name="memory_id"
                  aria-label="Reviewed product decision"
                >
                  <option value="">Choose an accepted decision</option>
                  {decisions
                    .filter(
                      (m) =>
                        (m.project_id || null) === (product.project_id || null),
                    )
                    .map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.text.slice(0, 120)}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Requirement changes (JSON)
                <textarea
                  aria-label="Decision requirement changes"
                  name="changes"
                  defaultValue={'{"theme":"dark"}'}
                  required
                />
              </label>
              <button className="studio-primary" disabled={busy}>
                Apply reviewed decision
              </button>
            </form>
          )}
          {builds.filter((b) => b.spec_id === product?.id).length > 1 && (
            <label>
              Build history
              <select
                onChange={(e) =>
                  setBuild(builds.find((b) => b.id === e.target.value))
                }
                value={build?.id || ""}
              >
                {builds
                  .filter((b) => b.spec_id === product?.id)
                  .map((b) => (
                    <option key={b.id} value={b.id}>
                      Revision {b.revision} ·{" "}
                      {new Date(b.created_at).toLocaleString(undefined, {
                        timeZone: "Asia/Calcutta",
                      })}
                    </option>
                  ))}
              </select>
            </label>
          )}
        </section>
      </div>
    </div>
  );
}
