import { ToolAccess, parseCalls, type ManageConnections } from "./ToolAccess";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  Paperclip,
  Play,
  Shield,
  Users,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { client } from "../api";
import type { Convo } from "../types";
export function DiscussionRoom({
  api,
  conversation,
  projectId,
  businessId,
  onRefresh,
  onManage,
}: {
  api: ReturnType<typeof client>;
  conversation: Convo | null;
  projectId: string;
  businessId: string;
  onRefresh: () => void;
  onManage: ManageConnections;
}) {
  const [convos, setConvos] = useState<any[]>([]),
    [conv, setConv] = useState<any>(conversation),
    [goal, setGoal] = useState(
      "Review our customer evidence and challenge our product and marketing plan.",
    ),
    [mode, setMode] = useState("default"),
    [fallback, setFallback] = useState(true),
    [tools, setTools] = useState("[]"),
    [rounds, setRounds] = useState(2),
    [runs, setRuns] = useState<any[]>([]),
    [active, setActive] = useState<any>(null),
    [plan, setPlan] = useState(""),
    [ack, setAck] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  async function load() {
    const [a, b] = await Promise.all([
      api.json("/conversations"),
      api.json("/discussions"),
    ]);
    setConvos(a);
    setRuns(b);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
    return () => controller.current?.abort();
  }, []);
  function follow(id: string) {
    controller.current?.abort();
    const signal = new AbortController();
    controller.current = signal;
    api
      .watch(
        id,
        (run: any) => {
          setActive(run);
          if (run.state === "WAITING_FOR_APPROVAL")
            setPlan(
              run.discussion_result?.outputs?.product_manager?.text || "",
            );
          if (!["CREATED", "RUNNING"].includes(run.state)) {
            load().catch((e) => setError(e.message));
            onRefresh();
          }
        },
        signal.signal,
      )
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
  }
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
  const outputs =
    active?.discussion_result?.outputs ||
    Object.fromEntries(
      Object.entries(active?.discussion_checkpoint?.outputs || {}).map(
        ([key, value]) => [key.split(":")[0], value],
      ),
    );
  return (
    <div className="studio-page">
      <div className="studio-page-title">
        <span className="eyebrow">DISCUSSION ROOM / LANGGRAPH</span>
        <h1>Better decisions start with a discussion.</h1>
        <p>
          A business analyst, marketing analyst, product manager and reviewer
          share evidence, challenge claims and hand off a proposal for your
          decision.
        </p>
      </div>
      {error && (
        <div role="alert" className="error">
          {error}
        </div>
      )}
      <ToolAccess
        api={api}
        onManage={onManage}
        inline
        calls={parseCalls(tools)}
        onChange={(v) => setTools(JSON.stringify(v))}
        conversationId={conv?.id}
      />
      <div className="discussion-layout">
        <section>
          <form
            className="studio-card studio-form"
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                if (!conv)
                  throw Error(
                    "Create or choose an evidence conversation first",
                  );
                const run = await api.json("/discussions", {
                  method: "POST",
                  body: JSON.stringify({
                    conversation_id: conv.id,
                    goal,
                    mode,
                    allow_fallback: fallback,
                    max_rounds: rounds,
                    max_seconds: 300,
                    max_output_tokens: 6144,
                    context_tools: JSON.parse(tools),
                  }),
                });
                setActive(run);
                setPlan("");
                follow(run.id);
              });
            }}
          >
            <h3>
              <Users size={18} />
              Set the discussion goal
            </h3>
            <label>
              Evidence conversation
              <select
                aria-label="Discussion conversation"
                value={conv?.id || ""}
                onChange={(e) =>
                  setConv(convos.find((c) => c.id === e.target.value))
                }
              >
                <option value="">Choose a conversation</option>
                {convos
                  .filter((c) => !projectId || c.project_id === projectId)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                    </option>
                  ))}
              </select>
            </label>
            {!conv && (
              <button
                type="button"
                onClick={() =>
                  act(async () => {
                    const c = await api.json("/conversations", {
                      method: "POST",
                      body: JSON.stringify({
                        title: "Business and product discussion",
                        business_id: businessId || null,
                        project_id: projectId || null,
                      }),
                    });
                    setConv(c);
                    await load();
                    onRefresh();
                  })
                }
              >
                Create discussion workspace
              </button>
            )}
            {conv && (
              <>
                <label className="discussion-upload">
                  <Paperclip size={14} />
                  Add CRM export or customer feedback
                  <input
                    aria-label="Discussion evidence file"
                    type="file"
                    accept=".txt,.csv,.pdf,.docx"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file)
                        act(async () => {
                          const data = new FormData();
                          data.append("file", file);
                          await api.json(
                            "/conversations/" + conv.id + "/files",
                            { method: "POST", body: data },
                          );
                          setConv(await api.json("/conversations/" + conv.id));
                        });
                    }}
                  />
                </label>
                <div className="discussion-files">
                  {conv.files?.map((f: any) => (
                    <span key={f.id}>{f.name}</span>
                  ))}
                </div>
              </>
            )}
            <label>
              Decision or business goal
              <textarea
                required
                minLength={5}
                aria-label="Decision or business goal"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
              />
            </label>
            <label>
              Model routing
              <select
                aria-label="Discussion model routing"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
              >
                <option value="default">
                  Default key / per-agent overrides
                </option>
                <option value="local">Local AI · no external key</option>
                <option value="evidence">Deterministic role analysis</option>
              </select>
            </label>
            <label className="studio-checkbox">
              <input
                type="checkbox"
                checked={fallback}
                onChange={(e) => setFallback(e.target.checked)}
              />
              Allow a labeled evidence fallback when a provider fails
            </label>
            <details>
              <summary>Loop and MCP context settings</summary>
              <label>
                Maximum review rounds
                <input
                  type="number"
                  min={1}
                  max={3}
                  value={rounds}
                  onChange={(e) => setRounds(Number(e.target.value))}
                />
              </label>
              <label>
                Read-only registered tool calls
                <textarea
                  aria-label="Discussion context tools"
                  className="code-editor"
                  value={tools}
                  onChange={(e) => setTools(e.target.value)}
                />
              </label>
              <small>
                Use a list of objects with name and arguments. Tools must be
                registered, authorized, read-only and compatible with the
                project data policy.
              </small>
            </details>
            <button className="studio-primary" disabled={busy || !conv}>
              <Play size={14} />
              Start specialist discussion
            </button>
          </form>
          <h3 className="studio-subtitle">Saved discussions</h3>
          {runs.map((run) => (
            <button
              className="studio-history"
              key={run.id}
              onClick={() => {
                setActive(run);
                setPlan(
                  run.discussion_result?.outputs?.product_manager?.text || "",
                );
                if (["CREATED", "RUNNING"].includes(run.state)) follow(run.id);
              }}
            >
              <Users size={15} />
              <span>
                {run.question}
                <small>{run.state}</small>
              </span>
              <ArrowRight size={14} />
            </button>
          ))}
        </section>
        <section>
          {!active ? (
            <div className="studio-preview-empty">
              <Users size={40} />
              <h2>Your specialists, one shared goal.</h2>
              <p>
                Upload a CRM export, customer feedback or a research document.
                MCP tools can add authorized context. No live market feed is
                assumed.
              </p>
              <div>
                <span>Evidence</span>
                <span>Handoffs</span>
                <span>Human decision</span>
              </div>
            </div>
          ) : (
            <>
              <div className="discussion-status">
                <span className="status-pill">
                  {active.state.replaceAll("_", " ")}
                </span>
                <span>
                  {active.discussion_checkpoint?.reserved_output_tokens || 0}{" "}
                  tokens reserved · {active.discussion_result?.round || 0}/
                  {active.discussion_input?.max_rounds || rounds} rounds
                </span>
                {["CREATED", "RUNNING"].includes(active.state) && (
                  <button
                    onClick={() =>
                      act(async () => {
                        setActive(
                          await api.json(
                            "/executions/" + active.id + "/cancel",
                            { method: "POST" },
                          ),
                        );
                      })
                    }
                  >
                    Cancel
                  </button>
                )}
              </div>
              <div
                className="agent-graph"
                role="img"
                aria-label="Business analyst to marketing analyst to product manager to reviewer with a bounded review loop"
              >
                {[
                  "business_analyst",
                  "marketing_analyst",
                  "product_manager",
                  "reviewer",
                ].map((agent, i) => (
                  <div
                    className={
                      "agent-graph-node " + (outputs[agent] ? "complete" : "")
                    }
                    key={agent}
                  >
                    <span>
                      {outputs[agent] ? (
                        <Check size={16} />
                      ) : (
                        String(i + 1).padStart(2, "0")
                      )}
                    </span>
                    <strong>{agent.replaceAll("_", " ")}</strong>
                    {i < 3 && <ArrowRight size={13} />}
                  </div>
                ))}
                <small>
                  Reviewer → Product manager · bounded revision loop
                </small>
              </div>
              {Object.entries(outputs).map(([agent, result]: [string, any]) => (
                <article className="studio-card specialist-output" key={agent}>
                  <div className="studio-card-heading">
                    <h3>{agent.replaceAll("_", " ")}</h3>
                    <span className="status-pill">{result.mode}</span>
                  </div>
                  <small>{result.classification}</small>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {result.text}
                  </ReactMarkdown>
                  {!!result.memory_ids?.length && (
                    <small>
                      {result.memory_ids.length} reviewed memories recalled
                    </small>
                  )}
                </article>
              ))}
              {!!active.discussion_result?.issues?.length && (
                <div className="studio-card review-issues">
                  <h3>
                    <Shield size={16} />
                    Unresolved review issues
                  </h3>
                  {active.discussion_result.issues.map((issue: string) => (
                    <p key={issue}>{issue}</p>
                  ))}
                </div>
              )}
              {active.error && <p className="error">{active.error}</p>}
              {active.state === "WAITING_FOR_APPROVAL" && (
                <form
                  className="studio-card studio-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    act(async () => {
                      setActive(
                        await api.json(
                          "/discussions/" + active.id + "/decision",
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
                      await load();
                    });
                  }}
                >
                  <h3>Review the decision before it becomes memory.</h3>
                  <label>
                    Approved plan
                    <textarea
                      aria-label="Reviewed discussion plan"
                      value={plan}
                      onChange={(e) => setPlan(e.target.value)}
                      maxLength={4000}
                      minLength={3}
                      required
                    />
                  </label>
                  {!!active.discussion_result?.issues?.length && (
                    <label className="studio-checkbox">
                      <input
                        type="checkbox"
                        checked={ack}
                        onChange={(e) => setAck(e.target.checked)}
                      />
                      I reviewed and reconciled the unresolved issues in my
                      edited plan
                    </label>
                  )}
                  <div className="studio-actions">
                    <button className="studio-primary" disabled={busy}>
                      Approve & remember decision
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        act(async () => {
                          setActive(
                            await api.json(
                              "/discussions/" + active.id + "/decision",
                              {
                                method: "POST",
                                body: JSON.stringify({
                                  approve: false,
                                  plan: plan || "Rejected proposal",
                                }),
                              },
                            ),
                          );
                          await load();
                        })
                      }
                    >
                      Reject
                    </button>
                  </div>
                </form>
              )}
              {active.memory_id && (
                <div className="studio-success">
                  <Check size={16} />
                  Approved decision saved to scoped agent memory.
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
