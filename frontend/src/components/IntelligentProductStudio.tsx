import { TrashDialog } from "./TrashDialog";
import { Trash2 } from "lucide-react";
import { ProductDocument } from "./ProductDocument";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { client } from "../api";
import { ToolAccess, type ManageConnections } from "./ToolAccess";
import { UiIcon } from "./UiIcon";
import { ProductPreview } from "./ProductPreview";
import {
  SourceTree,
  ArchitectureDiagram,
  ProductFlow,
} from "./ProductArtifacts";
import { useNavigate, useSearchParams } from "react-router-dom";
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
function belongsToRun(build: any, run: any) {
  return (
    !run ||
    build.execution_id === run.id ||
    build.blueprint?.execution_id === run.id ||
    output(run, "implementation")?.id === build.id
  );
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
  const [trashOpen, setTrashOpen] = useState(false);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const storageKey =
    "evolvyn-product:" +
    (sessionStorage.getItem("evolvyn-organization") || "session") +
    ":" +
    (projectId || "workspace");
  const [artifactsOpen, setArtifactsOpen] = useState(false),
    [restoring, setRestoring] = useState(true);
  const revealedRun = useRef<string | null>(null);
  const mounted = useRef(true),
    stickToBottom = useRef(true);
  const selected = useRef<string | null>(null),
    generation = useRef(0);
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
    [notice, setNotice] = useState(""),
    [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const submitLock = useRef(false);
  const watches = useRef<AbortController[]>([]),
    bottom = useRef<HTMLDivElement>(null);
  async function catalog() {
    const [p, b] = await Promise.all([
      api.json("/studio/products"),
      api.json("/studio/builds"),
    ]);
    setProducts(p);
    setBuilds(b);
    return { products: p, builds: b };
  }
  function remember(id: string) {
    sessionStorage.setItem(storageKey, id || "new");
    if (!mounted.current || window.location.pathname !== "/product-studio")
      return;
    // Module transitions can mount this view before the router context catches
    // up. An absolute destination prevents a late restore writing to /growth.
    const next = new URLSearchParams(window.location.search);
    if (id) next.set("product", id);
    else next.delete("product");
    navigate("/product-studio" + (next.size ? "?" + next.toString() : ""), {
      replace: true,
    });
  }
  function detach() {
    watches.current.forEach((w) => w.abort());
    watches.current = [];
    generation.current++;
  }
  function newProduct() {
    detach();
    selected.current = null;
    remember("");
    setProduct(null);
    setRun(null);
    setBuild(null);
    setInterview(null);
    setHistory([]);
    setText("");
    setError("");
    setNotice("");
    setArtifactsOpen(false);
  }
  async function load(id: string, knownBuilds?: any[]) {
    detach();
    const current = generation.current;
    selected.current = id;
    setProduct(null);
    setRun(null);
    setInterview(null);
    setBuild(null);
    setHistory([]);
    const [p, h, b] = await Promise.all([
      api.json("/studio/products/" + id),
      api.json("/studio/products/" + id + "/agent-history"),
      knownBuilds ? Promise.resolve(knownBuilds) : api.json("/studio/builds"),
    ]);
    if (current !== generation.current) return;
    remember(id);
    setProduct(p);
    setBuilds(b);
    setHistory(h);

    const latest = h.find((r: any) =>
      r.definition?.nodes.some((n: any) => n.id === "contracts"),
    );
    setRun(latest || null);
    setBuild(
      b.find((row: any) => row.spec_id === id && belongsToRun(row, latest)) ||
        null,
    );
    if (latest) {
      setAgents(
        phases
          .filter((phase) =>
            latest.definition.nodes.some((node: any) => node.id === phase.id),
          )
          .map((phase) => phase.id),
      );
      setBuildSource(
        latest.definition.nodes.some(
          (node: any) => node.id === "implementation",
        ),
      );
    }
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
    let active = true;
    mounted.current = true;
    setRestoring(true);
    catalog()
      .then(async ({ products: p, builds: b }) => {
        if (!active) return;
        const available = p.filter(
          (row: any) => row.project_id === (projectId || null),
        );
        const requested =
          searchParams.get("product") || sessionStorage.getItem(storageKey);
        const id =
          requested === "new"
            ? null
            : available.find((row: any) => row.id === requested)?.id ||
              (requested ? null : available[0]?.id);
        if (id) await load(id, b);
        else {
          selected.current = null;
          setProduct(null);
          setRun(null);
          setInterview(null);
          setHistory([]);
          setBuild(null);
        }
        if (requested && requested !== "new" && !id)
          setError(
            "This product is unavailable in the current workspace. Choose another saved product or start a new one.",
          );
      })
      .catch((e) => active && setError(e.message))
      .finally(() => active && setRestoring(false));
    return () => {
      active = false;
      mounted.current = false;
      detach();
    };
  }, [storageKey]);
  useEffect(() => {
    const id = searchParams.get("product");
    if (!restoring && id && id !== selected.current) act(() => load(id));
  }, [searchParams.get("product")]);
  useEffect(() => {
    if (
      run?.state !== "RUNNING" ||
      run?.graph_checkpoint?.current?.id !== "implementation"
    )
      return;
    let active = true;
    const timer = setInterval(
      () =>
        api
          .json("/studio/builds")
          .then((rows) => {
            if (active)
              setBuild(
                rows.find(
                  (row: any) =>
                    row.spec_id === selected.current && belongsToRun(row, run),
                ) || null,
              );
          })
          .catch(() => {}),
      3000,
    );
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [run?.id, run?.state, run?.graph_checkpoint?.current?.id]);
  useEffect(() => {
    if (stickToBottom.current)
      bottom.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [
    pendingMessage,
    interview?.output,
    interview?.state,
    run?.state,
    run?.graph_checkpoint?.current?.id,
  ]);
  function follow(initial: any, chat: boolean) {
    if (!mounted.current) return;
    if (chat) setInterview(initial);
    else setRun(initial);
    const current = generation.current;
    const controller = new AbortController();
    watches.current.push(controller);
    api
      .watch(
        initial.id,
        (r) => {
          if (current !== generation.current) return;
          if (chat) setInterview(r);
          else setRun(r);
          if (!["CREATED", "RUNNING"].includes(r.state)) {
            if (chat)
              setHistory((prev) => [r, ...prev.filter((p) => p.id !== r.id)]);
            catalog()
              .then(({ builds: b }) => {
                if (current !== generation.current) return;
                const id = output(r, "implementation")?.id;
                if (id) setBuild(b.find((v: any) => v.id === id) || null);
                else if (!chat)
                  setBuild(
                    b.find(
                      (v: any) =>
                        v.spec_id === selected.current && belongsToRun(v, r),
                    ) || null,
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
  useEffect(() => {
    if (
      run?.id &&
      build?.files &&
      Object.keys(build.files).length &&
      revealedRun.current !== run.id
    ) {
      revealedRun.current = run.id;
      setArtifactsOpen(true);
      setTab("source");
    }
  }, [run?.id, build?.files]);
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
  async function startBuild(p: any) {
    const r = await api.json("/studio/products/" + p.id + "/agent-build", {
      method: "POST",
      body: JSON.stringify({
        spec_id: p.id,
        revision: p.revision,
        mode,
        agents,
        build_source: buildSource,
      }),
    });
    setBuild(null);
    follow(r, false);
  }
  async function send() {
    let p = product;
    const message = text.trim();
    if (!message || submitLock.current) return;
    submitLock.current = true;
    setPendingMessage(message);
    setText("");
    try {
      if (!p) {
        p = await api.json("/studio/products", {
          method: "POST",
          body: JSON.stringify({
            name:
              message.replace(/\s+/g, " ").split(/[.!?]/)[0].slice(0, 70) ||
              message.slice(0, 70),
            goal: message,
            project_id: projectId || null,
          }),
        });
        selected.current = p.id;
        remember(p.id);
        setProduct(p);
        setHistory([]);
        setTab("overview");
        setProducts((rows) => [p, ...rows.filter((row) => row.id !== p.id)]);
      }
      const r = await api.json("/studio/products/" + p.id + "/messages", {
        method: "POST",
        body: JSON.stringify({
          spec_id: p.id,
          revision: p.revision,
          text: message,
          mode,
          intent: p.ready ? "chat" : "plan",
        }),
      });
      follow(r, true);
    } catch (e) {
      if (mounted.current) setText((draft) => draft || message);
      throw e;
    } finally {
      submitLock.current = false;
      if (mounted.current) setPendingMessage(null);
    }
  }
  async function confirmPlan() {
    const result = await api.json(
      "/studio/products/" +
        product.id +
        "/proposals/" +
        interview.id +
        "/confirm-and-build",
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
    setProduct(result.product);
    await catalog();
    if (result.execution) {
      setBuild(null);
      follow(result.execution, false);
      setNotice(
        "Setup confirmed. The development workflow has started; you can leave this module and return.",
      );
    } else setError(result.launch_error);
  }
  const running =
    busy ||
    !!pendingMessage ||
    [run, interview].some((r) => r && ["CREATED", "RUNNING"].includes(r.state));
  const proposal = output(interview, "proposal");
  const contracts = output(run, "contracts");
  const pending = run?.graph_checkpoint?.pending;
  const blueprint = contracts || build?.blueprint;
  const sourceFiles: Record<string, string> = build?.files || {};
  const completeProposal =
    product &&
    proposal &&
    product.next_question &&
    Object.keys({ ...product.requirements, ...proposal.proposed_requirements })
      .length === 11;
  const proposalAccepted = product?.proposal_history?.some(
    (h: any) => h.execution_id === interview?.id,
  );
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
      : run?.state === "CANCELLED"
        ? "Workflow cancelled"
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
      {trashOpen && (
        <TrashDialog
          api={api}
          onClose={() => setTrashOpen(false)}
          onRestore={() => {
            catalog().catch((e) => setError(e.message));
          }}
        />
      )}
      <header className="product-workbench-header">
        <div>
          <span className="eyebrow">PRODUCT DEVELOPMENT WORKSPACE</span>
          <h1>{product?.name || "New product conversation"}</h1>
          <p>Describe your idea. Build it with your development team.</p>
        </div>
        <div className="product-header-actions">
          <button onClick={newProduct} disabled={busy || restoring}>
            <UiIcon name="plus" size={16} /> New product
          </button>
          <button
            onClick={() => setArtifactsOpen(!artifactsOpen)}
            aria-expanded={artifactsOpen}
          >
            {artifactsOpen ? "Hide workspace" : "Open workspace"}
          </button>
          <details>
            <summary>Options</summary>
            <div
              className="product-options-menu"
              onClick={(e) => {
                if ((e.target as HTMLElement).closest("button")) {
                  const details = e.currentTarget.closest("details");
                  if (details) details.open = false;
                }
              }}
            >
              {" "}
              {product && (
                <button
                  aria-label="Move product conversation to trash"
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      await api.json("/studio/products/" + product.id, {
                        method: "DELETE",
                      });
                      newProduct();
                      await catalog();
                      setNotice("Moved to trash. Restore it within 15 days.");
                    })
                  }
                >
                  <Trash2 size={16} /> Move conversation to trash
                </button>
              )}
              <button
                aria-label="Open product trash"
                onClick={() => setTrashOpen(true)}
              >
                <Trash2 size={16} /> Trash
              </button>
            </div>
          </details>
        </div>
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
            disabled={busy || restoring}
            onChange={(e) =>
              e.target.value ? act(() => load(e.target.value)) : newProduct()
            }
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
        {[interview, run]
          .filter((r) => r && ["CREATED", "RUNNING"].includes(r.state))
          .map((active) => (
            <button
              key={active.id}
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const stopped = await api.json(
                    "/executions/" + active.id + "/cancel",
                    { method: "POST" },
                  );
                  if (active.id === interview?.id) setInterview(stopped);
                  else setRun(stopped);
                })
              }
            >
              Stop {active.id === interview?.id ? "reply" : "workflow"}
            </button>
          ))}
      </div>
      <div
        className={
          "product-workbench-grid " +
          (artifactsOpen ? "with-artifacts" : "chat-only")
        }
      >
        <section
          className="product-conversation"
          aria-label="Product requirements conversation"
        >
          <div className="product-conversation-scroll" aria-live="polite">
            {restoring ? (
              <p role="status">Restoring your product workspace…</p>
            ) : !product ? (
              <>
                {pendingMessage ? (
                  <article className="product-chat user" role="status">
                    <small>You · sending</small>
                    <p>{pendingMessage}</p>
                    <span>Saving your message and starting the agent…</span>
                  </article>
                ) : (
                  <div className="product-chat-welcome">
                    <span className="product-welcome-symbol">
                      <UiIcon name="code" size={32} />
                    </span>
                    <h2>What would you like to build?</h2>
                    <p>
                      Start with your idea. Your agents will propose a setup,
                      ask questions here, and turn your confirmed plan into
                      project files.
                    </p>
                    <div className="product-idea-examples">
                      {[
                        "Build an e-commerce product catalog",
                        "Create a customer support workspace",
                        "Build an inventory management app",
                      ].map((idea) => (
                        <button key={idea} onClick={() => setText(idea)}>
                          {idea}
                          <UiIcon name="arrow-up" size={14} />
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <>
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
                        <ReactMarkdown>{interviewReply(r)}</ReactMarkdown>
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
                      {r.state === "FAILED" && (
                        <a href="/keyvault">
                          Check the effective agent model in Key vault
                        </a>
                      )}
                      {r.state === "FAILED" && interviewReply(r) && (
                        <p className="error">
                          Requirement proposals were not validated. No changes
                          were saved. {r.error}
                        </p>
                      )}
                    </article>
                  </div>
                ))}

                {pendingMessage && (
                  <article className="product-chat user" role="status">
                    <small>You · sending</small>
                    <p>{pendingMessage}</p>
                    <span>Saving your message and starting the agent…</span>
                  </article>
                )}
                {!transcript.length && !pendingMessage && product && (
                  <article className="product-chat user">
                    <small>You</small>
                    <p>{product.goal}</p>
                  </article>
                )}
                {proposal &&
                  Object.keys(proposal.proposed_requirements || {}).length >
                    0 &&
                  interview.state === "COMPLETED" &&
                  !proposalAccepted && (
                    <section className="product-proposal">
                      <h3>Proposed starting setup</h3>
                      <p>
                        Review these suggestions. You can change any choice by
                        replying in this chat.
                      </p>
                      <details>
                        <summary>
                          Review{" "}
                          {Object.keys(proposal.proposed_requirements).length}{" "}
                          proposed decisions
                        </summary>
                        {Object.entries(proposal.proposed_requirements).map(
                          ([k, v]) => (
                            <div key={k}>
                              <strong>{k}</strong>
                              <pre>{String(v)}</pre>
                            </div>
                          ),
                        )}
                      </details>
                      <button
                        className="studio-primary"
                        disabled={
                          running ||
                          interview?.definition?.nodes?.find(
                            (n: any) => n.id === "proposal",
                          )?.arguments?.revision !== product.revision
                        }
                        onClick={() =>
                          act(async () => {
                            if (completeProposal || product.ready)
                              await confirmPlan();
                            else {
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
                              await catalog();
                              setNotice(
                                "Decisions saved. Continue in chat to finish the proposed setup.",
                              );
                            }
                          })
                        }
                      >
                        {completeProposal || product.ready
                          ? "Confirm setup & start building"
                          : "Confirm proposed requirements"}
                      </button>
                    </section>
                  )}
                {product.ready && !run && !running && (
                  <article className="product-chat assistant">
                    <p>
                      Your setup is confirmed. Start the development agents to
                      produce the folder plan, PRD, architecture and source
                      proposal.
                    </p>
                    <button
                      className="studio-primary"
                      onClick={() => act(() => startBuild(product))}
                    >
                      Start building
                    </button>
                  </article>
                )}
                {run && (
                  <section
                    className="product-run-feed"
                    aria-label="Build activity"
                  >
                    <h3>
                      <UiIcon name="git-branch" size={18} /> {status}
                    </h3>
                    <ProductFlow run={run} />
                    {(run.events || [])
                      .slice(-4)
                      .map((event: any, i: number) => (
                        <p key={i}>
                          <small>{event.stage}</small> {event.detail}
                        </p>
                      ))}
                    {build?.generation === "model" && (
                      <div className="source-creation-progress" role="status">
                        <strong>
                          {Object.keys(build.files || {}).length} files saved
                          {build.manifest ? " of " + build.manifest.length : ""}
                        </strong>
                        {build.events
                          ?.slice(-3)
                          .map((event: any, i: number) => (
                            <p key={i}>{event.detail}</p>
                          ))}
                        {build.error && <p className="error">{build.error}</p>}
                      </div>
                    )}
                    {run.state === "RUNNING" && run.output && (
                      <details>
                        <summary>Current agent output</summary>
                        <pre>{run.output}</pre>
                      </details>
                    )}
                    {run.state === "FAILED" && (
                      <p className="error" role="alert">
                        {run.error}
                      </p>
                    )}
                    {contracts?.can_build === false && (
                      <div role="alert">
                        <p>
                          The reviewer requested changes:{" "}
                          {contracts.review?.summary}. Revise the scope in chat
                          before rebuilding.
                        </p>
                        <ul>
                          {contracts.review?.issues?.map(
                            (issue: string, i: number) => (
                              <li key={i}>{issue}</li>
                            ),
                          )}
                        </ul>
                      </div>
                    )}
                    {!!Object.keys(sourceFiles).length && (
                      <button
                        onClick={() => {
                          setArtifactsOpen(true);
                          setTab("source");
                        }}
                      >
                        Open{" "}
                        {build?.files
                          ? "generated files"
                          : "planned folder structure"}{" "}
                        · {Object.keys(sourceFiles).length} paths
                      </button>
                    )}
                    {build?.state === "READY" && (
                      <button
                        onClick={() => {
                          setArtifactsOpen(true);
                          setTab("preview");
                        }}
                      >
                        {build.generation === "model"
                          ? "Open data sandbox"
                          : "Open working data prototype"}
                      </button>
                    )}
                    {["FAILED", "CANCELLED", "COMPLETED"].includes(run.state) &&
                      product.ready &&
                      !running && (
                        <button onClick={() => act(() => startBuild(product))}>
                          Run product agents again
                        </button>
                      )}
                  </section>
                )}
                {pending && run?.state === "WAITING_FOR_APPROVAL" && (
                  <div className="product-implementation-approval">
                    <h3>Approve this source implementation?</h3>
                    <p>
                      This creates source files using your selected model and
                      the output limits below. Provider usage may incur charges.
                      It does not deploy or publish the application.
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
              </>
            )}
            <div ref={bottom} />
          </div>
          <form
            className="product-conversation-composer"
            onSubmit={(e) => {
              e.preventDefault();
              if (!running && !restoring) act(send);
            }}
          >
            <textarea
              aria-label="Message product agents"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  if (!e.repeat && !running && !restoring)
                    e.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder={
                product
                  ? "Ask a question or refine your product…"
                  : "Describe the product you want to build…"
              }
              required
              minLength={product ? 1 : 5}
              maxLength={2000}
            />
            <div className="product-composer-bottom">
              <ToolAccess api={api} onManage={onManage} />
              <label className="product-route">
                <span className="sr-only">Agent model route</span>
                <select
                  aria-label="Product agent model route"
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                >
                  <option value="default">Workspace model</option>
                </select>
              </label>
              <button
                className="studio-primary"
                aria-label="Send to product agents"
                disabled={
                  running || restoring || text.trim().length < (product ? 1 : 5)
                }
              >
                <UiIcon name="arrow-up" size={19} />
                <span className="product-send-label">Send</span>
              </button>
            </div>
          </form>
          <small>
            Enter to send · Shift+Enter for a new line. Progress and drafts are
            saved. Source writes require approval; provider failures are shown
            here.
          </small>
        </section>
        <section className="product-deliverables" hidden={!artifactsOpen}>
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
                      preview:
                        build?.generation === "model"
                          ? "Data sandbox"
                          : "Prototype",
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
                    onClick={() => act(() => startBuild(product))}
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
                        const { builds: b } = await catalog();
                        setBuild(
                          b.find(
                            (v: any) =>
                              v.spec_id === selected.current &&
                              belongsToRun(v, r),
                          ) || null,
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
              <ProductDocument
                key={product?.id}
                api={api}
                specId={product?.id}
                generatedText={blueprint?.prd || output(run, "prd")?.text || ""}
              />
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
            (Object.keys(sourceFiles).length ? (
              <div className="product-source-workspace">
                <SourceTree
                  files={sourceFiles}
                  selected={file}
                  onSelect={setFile}
                />
                <div className="product-source-code">
                  <header>
                    <strong>{file}</strong>
                    <button
                      disabled={build?.state !== "READY"}
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
                    {build?.files
                      ? "Source snapshot"
                      : "Planned paths · contents pending approval"}{" "}
                    · revision {build?.revision} ·{" "}
                    {Object.keys(sourceFiles).length} files
                  </small>
                  <pre tabIndex={0}>
                    {sourceFiles[file] ||
                      (build?.files
                        ? "Select a file from the project tree."
                        : "Planned file. Source contents will be created after blueprint review and implementation approval.")}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="product-workbench-pane">
                <h2>Your project files will appear here.</h2>
                <p>
                  No files have been created yet. After your source approval,
                  the model creates and saves each file individually. The tree
                  shows saved files only.
                </p>
              </div>
            ))}
          {tab === "preview" && (
            <div className="product-workbench-pane">
              {build?.state === "READY" ? (
                <>
                  {build.generation === "model" && (
                    <p>
                      This is a data sandbox using the confirmed entities. The
                      generated application has not been executed.
                    </p>
                  )}
                  <ProductPreview api={api} build={build} />
                </>
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
              {build?.generation === "model" && (
                <p>
                  Model-authored source; saved file by file. Backend runtime and
                  security acceptance are not inferred from frontend
                  compilation.
                </p>
              )}
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
                  <h3>
                    {build.generation === "model"
                      ? "Domain requirements awaiting runtime verification"
                      : "Domain requirements still needing implementation"}
                  </h3>
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
