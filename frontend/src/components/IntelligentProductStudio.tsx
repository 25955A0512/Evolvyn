import { ProductDocument } from "./ProductDocument";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { client } from "../api";
import { ToolAccess, type ManageConnections } from "./ToolAccess";
import { UiIcon, WorkspaceArtwork } from "./UiIcon";
import { ProductPreview } from "./ProductPreview";
import {
  SourceTree,
  ArchitectureDiagram,
  ProductFlow,
} from "./ProductArtifacts";
type API = ReturnType<typeof client>;
const phases = [
  {
    id: "prd",
    name: "PRD agent",
    detail: "Product requirements and acceptance criteria",
  },
  {
    id: "architecture",
    name: "Architecture agent",
    detail: "Stack, components and data boundaries",
  },
  {
    id: "developer",
    name: "Interface developer",
    detail: "Model-designed product experience",
  },
  {
    id: "reviewer",
    name: "Quality reviewer",
    detail: "Review scope, privacy and unresolved work",
  },
];
function output(run: any, id: string) {
  return run?.graph_checkpoint?.nodes?.[id]?.output;
}
function interviewReply(run: any): string | undefined {
  if (output(run, "proposal")?.reply) return output(run, "proposal").reply;
  // Preserve a model's valid conversational reply even when its proposed
  // requirement values fail later validation. No unvalidated proposal is saved.
  try {
    const draft = JSON.parse(output(run, "interview")?.text || "");
    if (typeof draft.reply === "string") return draft.reply.slice(0, 3000);
  } catch {}
}
export function IntelligentProductStudio({
  api,
  projectId,
  onManage,
  onGuided,
}: {
  api: API;
  projectId: string;
  onManage: ManageConnections;
  onGuided: () => void;
}) {
  const [products, setProducts] = useState<any[]>([]),
    [product, setProduct] = useState<any>(null),
    [builds, setBuilds] = useState<any[]>([]),
    [run, setRun] = useState<any>(null),
    [interview, setInterview] = useState<any>(null),
    [history, setHistory] = useState<any[]>([]),
    [build, setBuild] = useState<any>(null),
    [text, setText] = useState(""),
    [mode, setMode] = useState("default"),
    [agents, setAgents] = useState(phases.map((a) => a.id)),
    [buildSource, setBuildSource] = useState(true),
    [tab, setTab] = useState("overview"),
    [file, setFile] = useState("frontend/src/main.jsx"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const watches = useRef<AbortController[]>([]),
    bottom = useRef<HTMLDivElement>(null);
  async function catalog() {
    const [p, b] = await Promise.all([
      api.json("/studio/products"),
      api.json("/studio/builds"),
    ]);
    setProducts(p);
    setBuilds(b);
    return b;
  }
  async function load(id: string) {
    const [p, h, b] = await Promise.all([
      api.json("/studio/products/" + id),
      api.json("/studio/products/" + id + "/agent-history"),
      catalog(),
    ]);
    setProduct(p);
    setHistory(h);
    setBuild(b.find((b: any) => b.spec_id === id) || null);
    const latest = h.find((r: any) =>
      r.definition?.nodes.some((n: any) => n.id === "contracts"),
    );
    setRun(latest || null);
    const chat = h.find((r: any) =>
      r.definition?.nodes.some((n: any) => n.id === "interview"),
    );
    setInterview(chat || null);
    for (const r of h.filter((r: any) =>
      ["CREATED", "RUNNING"].includes(r.state),
    ))
      follow(
        r,
        r.definition.nodes.some((n: any) => n.id === "interview"),
      );
  }
  useEffect(() => {
    catalog().catch((e) => setError(e.message));
    return () => watches.current.forEach((w) => w.abort());
  }, []);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [interview?.output]);
  function follow(initial: any, chat: boolean) {
    if (chat) setInterview(initial);
    else setRun(initial);
    const controller = new AbortController();
    watches.current.push(controller);
    api
      .watch(
        initial.id,
        (r) => {
          if (chat) setInterview(r);
          else setRun(r);
          if (!["CREATED", "RUNNING"].includes(r.state)) {
            if (chat)
              setHistory((prev) => [r, ...prev.filter((p) => p.id !== r.id)]);
            catalog()
              .then((b) => {
                const id = output(r, "implementation")?.id;
                if (id) setBuild(b.find((v: any) => v.id === id) || null);
                else if (!chat)
                  setBuild(
                    b.find((v: any) => v.spec_id === product?.id) || null,
                  );
              })
              .catch((e) => setError(e.message));
          }
        },
        controller.signal,
      )
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
  }
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
  const running =
    busy ||
    [run, interview].some((r) => r && ["CREATED", "RUNNING"].includes(r.state));
  const proposal = output(interview, "proposal");
  const contracts = output(run, "contracts");
  const pending = run?.graph_checkpoint?.pending;
  const blueprint = contracts || build?.blueprint;
  const transcript = [
    ...history.filter((r) =>
      r.definition?.nodes.some((n: any) => n.id === "interview"),
    ),
  ];
  if (interview && !transcript.some((r) => r.id === interview.id))
    transcript.unshift(interview);
  else if (interview) {
    const i = transcript.findIndex((r) => r.id === interview.id);
    if (i >= 0) transcript[i] = interview;
  }
  const status =
    build?.state === "FAILED"
      ? "Build failed"
      : run?.state === "FAILED"
        ? "Workflow stopped"
        : contracts?.can_build === false
          ? "Review requested changes"
          : pending
            ? "Approval needed"
            : running
              ? "Agents working"
              : build?.state === "READY"
                ? "Source ready · runtime not started"
                : run?.state === "COMPLETED"
                  ? "Blueprint ready"
                  : product
                    ? "Requirements discussion"
                    : "Start a product";
  return (
    <div className="intelligent-product-studio">
      <header className="product-workbench-header">
        <div>
          <span className="eyebrow">PRODUCT DEVELOPMENT WORKSPACE</span>
          <h1>{product?.name || "Build your next business product."}</h1>
          <p>
            A conversation, a specialist team, and one inspectable source tree.
          </p>
        </div>
        <button onClick={onGuided}>Guided form · no model</button>
      </header>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <div className="product-workbench-toolbar">
        <label>
          Project
          <select
            aria-label="Agent product"
            value={product?.id || ""}
            onChange={(e) => {
              watches.current.forEach((w) => w.abort());
              setText("");
              if (e.target.value) act(() => load(e.target.value));
              else {
                setProduct(null);
                setRun(null);
                setBuild(null);
                setInterview(null);
                setHistory([]);
              }
            }}
          >
            <option value="">New product</option>
            {products
              .filter((p) => p.project_id === (projectId || null))
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · r{p.revision}
                </option>
              ))}
          </select>
        </label>
        <span
          className={
            "product-state " +
            (run?.state === "FAILED" || build?.state === "FAILED"
              ? "failed"
              : "")
          }
        >
          {status}
        </span>
        <ToolAccess api={api} onManage={onManage} />
        {[interview, run].filter((r) => r && ["CREATED", "RUNNING"].includes(r.state)).map((active) => (
          <button key={active.id} disabled={busy} onClick={() => act(async () => {
            const stopped = await api.json("/executions/" + active.id + "/cancel", {method: "POST"});
            if (active.id === interview?.id) setInterview(stopped);
            else setRun(stopped);
          })}>Stop {active.id === interview?.id ? "reply" : "workflow"}</button>
        ))}
      </div>
      <div className="product-workbench-grid">
        <section
          className="product-conversation"
          aria-label="Product requirements conversation"
        >
          {!product ? (
            <form
              className="product-new-idea"
              onSubmit={(e) => {
                e.preventDefault();
                const d = Object.fromEntries(new FormData(e.currentTarget));
                act(async () => {
                  const p = await api.json("/studio/products", {
                    method: "POST",
                    body: JSON.stringify({
                      ...d,
                      project_id: projectId || null,
                    }),
                  });
                  setProduct(p);
                  setTab("overview");
                  const execution = await api.json(
                    "/studio/products/" + p.id + "/messages",
                    {
                      method: "POST",
                      body: JSON.stringify({
                        spec_id: p.id,
                        revision: p.revision,
                        text: p.goal,
                        mode,
                      }),
                    },
                  );
                  follow(execution, true);
                });
              }}
            >
              <WorkspaceArtwork kind="build" />
              <h2>Describe what you want to build.</h2>
              <p>
                Discuss the users, workflows, data, design, integrations and
                deployment needs. Confirm suggested requirements before
                implementation.
              </p>
              <label>
                Product name
                <input
                  name="name"
                  aria-label="AI product name"
                  required
                  minLength={2}
                  maxLength={100}
                  placeholder="Your product name"
                />
              </label>
              <label>
                Your idea
                <textarea
                  name="goal"
                  aria-label="AI product goal"
                  required
                  minLength={5}
                  maxLength={2000}
                  placeholder="Describe the product and the business problem it solves…"
                />
              </label>
              <button className="studio-primary" disabled={busy}>
                Discuss with the requirements agent{" "}
                <UiIcon name="arrow-up" size={17} />
              </button>
            </form>
          ) : (
            <>
              <div className="product-conversation-scroll">
                <article className="product-chat user">
                  <small>Your product goal</small>
                  <p>{product.goal}</p>
                </article>
                {transcript.reverse().map((r) => (
                  <div key={r.id}>
                    <article className="product-chat user">
                      <small>You</small>
                      <p>{r.question}</p>
                    </article>
                    <article className="product-chat assistant">
                      <small>
                        Requirements analyst ·{" "}
                        {r.state.toLowerCase().replaceAll("_", " ")}
                      </small>
                      {interviewReply(r) ? (
                        <ReactMarkdown>
                          {interviewReply(r)}
                        </ReactMarkdown>
                      ) : ["CREATED", "RUNNING"].includes(r.state) ? (
                        <>
                          <p>Requesting a model response…</p>
                          {r.output && <pre>{r.output}</pre>}
                        </>
                      ) : (
                        <p>
                          {r.error ||
                            "No validated model reply is available for this turn."}
                        </p>
                      )}
                      {r.state === "FAILED" && interviewReply(r) && (
                        <p className="error">Requirement proposals were not validated. No changes were saved. {r.error}</p>
                      )}
                    </article>
                  </div>
                ))}
                {proposal &&
                  Object.keys(proposal.proposed_requirements || {}).length >
                    0 &&
                  interview.state === "COMPLETED" && (
                    <section className="product-proposal">
                      <h3>Suggested requirements · review first</h3>
                      {Object.entries(proposal.proposed_requirements).map(
                        ([k, v]) => (
                          <div key={k}>
                            <strong>{k}</strong>
                            <pre>{String(v)}</pre>
                          </div>
                        ),
                      )}
                      <button
                        disabled={
                          busy ||
                          interview?.definition?.nodes?.find((n:any)=>n.id==='proposal')?.arguments?.revision !== product.revision ||
                          product.proposal_history?.some(
                            (h: any) => h.execution_id === interview.id,
                          )
                        }
                        onClick={() =>
                          act(async () => {
                            const p = await api.json(
                              "/studio/products/" +
                                product.id +
                                "/proposals/" +
                                interview.id +
                                "/accept",
                              {
                                method: "POST",
                                body: JSON.stringify({
                                  spec_id: product.id,
                                  revision: product.revision,
                                }),
                              },
                            );
                            setProduct(p);
                            setNotice(
                              "Your reviewed requirements were saved as revision " +
                                p.revision +
                                ".",
                            );
                            await catalog();
                          })
                        }
                      >
                        Confirm proposed requirements
                      </button>
                    </section>
                  )}
                <div ref={bottom} />
              </div>
              <form
                className="product-conversation-composer"
                onSubmit={(e) => {
                  e.preventDefault();
                  act(async () => {
                    const r = await api.json(
                      "/studio/products/" + product.id + "/messages",
                      {
                        method: "POST",
                        body: JSON.stringify({
                          spec_id: product.id,
                          revision: product.revision,
                          text,
                          mode,
                        }),
                      },
                    );
                    setText("");
                    follow(r, true);
                  });
                }}
              >
                <textarea
                  aria-label="Message product agents"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Ask a question or refine your product requirements…"
                  required
                  maxLength={2000}
                />
                <button
                  className="studio-primary"
                  disabled={running || !text.trim()}
                >
                  <UiIcon name="arrow-up" size={18} />
                  Send
                </button>
              </form>
            </>
          )}
          <label className="product-route">
            Agent model route
            <select
              aria-label="Product agent model route"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
            >
              <option value="default">Vault / per-agent routes</option>
              <option value="local">Local model</option>
              <option value="gemini">Gemini · vault credential</option>
              <option value="groq">Groq · vault credential</option>
              <option value="provider">OpenAI · vault credential</option>
            </select>
          </label>
          <small>
            Missing provider credentials produce a visible error. No generated
            conversation or document is substituted.
          </small>
        </section>
        <section className="product-deliverables">
          <nav className="product-deliverable-tabs">
            {[
              "overview",
              "prd",
              "architecture",
              "source",
              "preview",
              "validation",
            ].map((t) => (
              <button
                className={tab === t ? "selected" : ""}
                key={t}
                onClick={() => setTab(t)}
              >
                {
                  (
                    {
                      overview: "Overview & agents",
                      prd: "PRD",
                      architecture: "Architecture",
                      source: "Source tree",
                      preview: "Prototype",
                      validation: "Build results",
                    } as Record<string, string>
                  )[t]
                }
              </button>
            ))}
          </nav>
          {tab === "overview" && (
            <div className="product-workbench-pane">
              <h2>Your development team</h2>
              <p>
                Enable the specialist phases you want. All implementation writes
                still require your explicit approval.
              </p>
              <div className="product-team">
                {phases.map((a) => (
                  <label key={a.id}>
                    <UiIcon
                      name={
                        a.id === "architecture"
                          ? "git-branch"
                          : a.id === "developer"
                            ? "code"
                            : a.id === "reviewer"
                              ? "shield-check"
                              : "file-text"
                      }
                      size={22}
                    />
                    <span>
                      <strong>{a.name}</strong>
                      <small>{a.detail}</small>
                    </span>
                    <input
                      type="checkbox"
                      aria-label={"Enable " + a.name}
                      checked={agents.includes(a.id)}
                      disabled={running}
                      onChange={(e) =>
                        setAgents(
                          e.target.checked
                            ? [...agents, a.id]
                            : agents.filter((id) => id !== a.id),
                        )
                      }
                    />
                  </label>
                ))}
              </div>
              {product && (
                <>
                  <h3>Confirmed requirements · revision {product.revision}</h3>
                  <div className="product-requirements-list">
                    {Object.entries(product.requirements).map(([k, v]) => (
                      <details key={k}>
                        <summary>{k}</summary>
                        <pre>
                          {typeof v === "object"
                            ? JSON.stringify(v, null, 2)
                            : String(v)}
                        </pre>
                      </details>
                    ))}
                  </div>
                  <p>
                    {product.ready
                      ? "Required decisions are confirmed. Generate the drafts and review the resulting implementation approval."
                      : "Next missing decision: " +
                        product.next_question?.field +
                        ". Discuss it with the agent or use the guided form."}
                  </p>
                  <label className="product-build-toggle">
                    <input
                      type="checkbox"
                      checked={buildSource}
                      onChange={(e) => setBuildSource(e.target.checked)}
                    />
                    Prepare source implementation after blueprint review
                  </label>
                  <button
                    className="studio-primary"
                    disabled={!product.ready || running || !agents.length}
                    onClick={() =>
                      act(async () => {
                        const r = await api.json(
                          "/studio/products/" + product.id + "/agent-build",
                          {
                            method: "POST",
                            body: JSON.stringify({
                              spec_id: product.id,
                              revision: product.revision,
                              mode,
                              agents,
                              build_source: buildSource,
                            }),
                          },
                        );
                        setBuild(null);
                        follow(r, false);
                      })
                    }
                  >
                    Run product agents <UiIcon name="git-branch" size={17} />
                  </button>
                </>
              )}
              {run && (
                <>
                  <ProductFlow run={run} />
                  <button
                    onClick={() =>
                      act(async () => {
                        const r = await api.json("/executions/" + run.id);
                        setRun(r);
                        const b = await catalog();
                        setBuild(
                          b.find((v: any) => v.spec_id === product?.id) || null,
                        );
                      })
                    }
                  >
                    Refresh actual status
                  </button>
                </>
              )}
            </div>
          )}
          {tab === "prd" && (
            <div className="product-workbench-pane markdown">
              <ProductDocument key={product?.id} api={api} specId={product?.id} generatedText={blueprint?.prd || output(run, "prd")?.text || ""} />
            </div>
          )}
          {tab === "architecture" && (
            <div className="product-workbench-pane">
              <h2>Architecture & boundaries</h2>
              <ArchitectureDiagram diagram={blueprint?.architecture} />
              {!blueprint?.architecture &&
                output(run, "architecture")?.text && (
                  <pre>{output(run, "architecture").text}</pre>
                )}
            </div>
          )}
          {tab === "source" &&
            (build?.files ? (
              <div className="product-source-workspace">
                <SourceTree
                  files={build.files}
                  selected={file}
                  onSelect={setFile}
                />
                <div className="product-source-code">
                  <header>
                    <strong>{file}</strong>
                    <button
                      onClick={() =>
                        api
                          .download(
                            "/studio/builds/" + build.id + "/download",
                            product.name.replace(/[^a-z0-9_-]/gi, "-") + ".zip",
                          )
                          .catch((e) => setError(e.message))
                      }
                    >
                      Download source
                    </button>
                  </header>
                  <small>
                    Immutable source snapshot ·{" "}
                    {Object.keys(build.files).length} files
                  </small>
                  <pre tabIndex={0}>
                    {build.files[file] ||
                      "Select a file from the project tree."}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="product-workbench-pane">
                <h2>Your project files will appear here.</h2>
                <p>
                  Source is generated only after approved requirements,
                  successful agent contracts, and your implementation approval.
                </p>
              </div>
            ))}
          {tab === "preview" && (
            <div className="product-workbench-pane">
              {build?.state === "READY" ? (
                <ProductPreview api={api} build={build} />
              ) : (
                <>
                  <h2>No ready prototype</h2>
                  <p>
                    A failed build never appears as a successful application.
                    Inspect Build results or finish the approved source
                    workflow.
                  </p>
                </>
              )}
            </div>
          )}
          {tab === "validation" && (
            <div className="product-workbench-pane">
              <h2>Actual build & validation results</h2>
              {build ? (
                <>
                  <strong className={build.state === "FAILED" ? "error" : ""}>
                    {build.state === "READY"
                      ? "Source validation passed"
                      : build.state}
                  </strong>
                  <p>{build.error}</p>
                  <p>
                    Frontend compiler:{" "}
                    {build.frontend_build?.status || "not requested"}
                  </p>
                  <p>{build.validation_scope}</p>
                  {build.checks?.map((c: string) => (
                    <p key={c}>
                      <UiIcon name="check" size={14} />
                      {c}
                    </p>
                  ))}
                  <h3>Domain requirements still needing implementation</h3>
                  {build.pending_requirements?.map((c: string) => (
                    <p key={c}>{c}</p>
                  ))}
                  <p>{build.integration_status}</p>
                  <h3>Model reviewer</h3>
                  <pre>
                    {JSON.stringify(build.blueprint?.review || {}, null, 2)}
                  </pre>
                  <strong>
                    Application runtime: not started. Cloud deployment: not
                    performed.
                  </strong>
                </>
              ) : (
                <p>No source build has run yet.</p>
              )}
            </div>
          )}
          {pending && run?.state === "WAITING_FOR_APPROVAL" && (
            <div className="product-implementation-approval">
              <h3>Approve this source implementation?</h3>
              <p>
                These exact product requirements and blueprint will generate a
                versioned source artifact. This does not deploy, publish or
                spend.
              </p>
              <details>
                <summary>Exact approved arguments</summary>
                <pre>{JSON.stringify(pending.arguments, null, 2)}</pre>
              </details>
              <button
                className="studio-primary"
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    const r = await api.json(
                      "/harness/executions/" + run.id + "/decision",
                      {
                        method: "POST",
                        body: JSON.stringify({
                          approve: true,
                          binding: pending.binding,
                        }),
                      },
                    );
                    follow(r, false);
                  })
                }
              >
                Approve source implementation
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    setRun(
                      await api.json(
                        "/harness/executions/" + run.id + "/decision",
                        {
                          method: "POST",
                          body: JSON.stringify({
                            approve: false,
                            binding: pending.binding,
                          }),
                        },
                      ),
                    );
                  })
                }
              >
                Reject
              </button>
            </div>
          )}
          {run?.state === "FAILED" && (
            <div className="error" role="alert">
              {run.error} Completed drafts are retained for inspection.
            </div>
          )}
          {contracts?.can_build === false && (
            <div role="alert" className="product-review-warning">
              The reviewer requested changes. No source implementation was
              started.<pre>{JSON.stringify(contracts.review, null, 2)}</pre>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
