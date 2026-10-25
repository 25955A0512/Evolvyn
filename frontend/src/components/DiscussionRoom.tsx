import { WorkspaceDialog } from "./WorkspaceDialog";
import { useEffect, useRef, useState } from "react";
import {
  Users,
  Plus,
  Paperclip,
  ArrowUp,
  Check,
  Settings2,
  Square,
  ChevronRight,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ToolAccess, parseCalls, type ManageConnections } from "./ToolAccess";
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
    [goal, setGoal] = useState(""),
    [mode, setMode] = useState("default"),
    [tools, setTools] = useState("[]"),
    [rounds, setRounds] = useState(2),
    [runs, setRuns] = useState<any[]>([]),
    [active, setActive] = useState<any>(null),
    [plan, setPlan] = useState(""),
    [ack, setAck] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [settings, setSettings] = useState(false);
  const controller = useRef<AbortController | null>(null),
    thread = useRef<HTMLDivElement>(null),
    firstReply = useRef<HTMLElement>(null),
    review = useRef<HTMLFormElement>(null),
    shownReply = useRef("");
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
    controller.current = new AbortController();
    api
      .watch(
        id,
        (r) => {
          setActive(r);
          if (r.state === "WAITING_FOR_APPROVAL")
            setPlan(r.discussion_result?.outputs?.product_manager?.text || "");
          if (!["CREATED", "RUNNING"].includes(r.state)) {
            load().catch((e) => setError(e.message));
            onRefresh();
          }
        },
        controller.current.signal,
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
        ([k, v]) => [k.split(":")[0], v],
      ),
    );
  const outputCount = Object.keys(outputs).length;
  function showInThread(element: HTMLElement | null) {
    const container = thread.current;
    if (container && element)
      container.scrollTo({
        top:
          container.scrollTop +
          element.getBoundingClientRect().top -
          container.getBoundingClientRect().top -
          12,
        behavior: "instant",
      });
  }
  useEffect(() => {
    // Open the first actual answer once; do not jump past replies to the
    // approval form, or move the reader on every streamed progress event.
    if (outputCount && active?.id !== shownReply.current) {
      showInThread(firstReply.current);
      shownReply.current = active.id;
    } else if (!outputCount) shownReply.current = "";
  }, [active?.id, outputCount]);
  const running = ["CREATED", "RUNNING"].includes(active?.state);
  async function createConversation() {
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
    return c;
  }
  return (
    <div className="discussion-chat studio-page">
      <div className="discussion-chat-heading">
        <span className="studio-icon">
          <Users size={22} />
        </span>
        <div>
          <h1>Discussion room</h1>
          <p>Business, marketing and product. One conversation.</p>
        </div>
        <button
          aria-label="Discussion settings"
          onClick={() => setSettings(!settings)}
        >
          <Settings2 size={20} />
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="discussion-chat-context">
        <label>
          Workspace
          <select
            aria-label="Discussion conversation"
            value={conv?.id || ""}
            onChange={(e) => {
              setConv(convos.find((c) => c.id === e.target.value));
              setActive(null);
            }}
          >
            <option value="">Choose a conversation</option>
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
          onClick={() =>
            act(async () => {
              await createConversation();
              setActive(null);
            })
          }
        >
          <Plus size={16} />
          {conv ? "New discussion" : "Create workspace"}
        </button>
        <label className="discussion-attach">
          <Paperclip size={18} />
          <span>Add evidence</span>
          <input
            aria-label="Discussion evidence file"
            type="file"
            accept=".txt,.csv,.pdf,.docx"
            disabled={busy || running}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file)
                act(async () => {
                  const c = conv || (await createConversation());
                  const data = new FormData();
                  data.append("file", file);
                  await api.json("/conversations/" + c.id + "/files", {
                    method: "POST",
                    body: data,
                  });
                  setConv(await api.json("/conversations/" + c.id));
                });
              e.target.value = "";
            }}
          />
        </label>
      </div>
      {conv?.files?.length > 0 && (
        <div className="discussion-files">
          {conv.files.map((f: any) => (
            <span key={f.id}>
              <Paperclip size={13} />
              {f.name}
            </span>
          ))}
        </div>
      )}
      {settings && (
        <WorkspaceDialog
          title="Discussion settings"
          onClose={() => setSettings(false)}
        >
          <section className="discussion-settings">
            <label>
              Model routing
              <select
                aria-label="Discussion model route"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
              >
                <option value="default">Workspace models</option>
              </select>
            </label>
            <label>
              Review rounds
              <input
                type="number"
                min={1}
                max={3}
                value={rounds}
                onChange={(e) => setRounds(Number(e.target.value))}
              />
            </label>
            <ToolAccess
              api={api}
              onManage={onManage}
              inline
              calls={parseCalls(tools)}
              onChange={(v) => setTools(JSON.stringify(v))}
              conversationId={conv?.id}
            />
            <details>
              <summary>Advanced tool arguments</summary>
              <textarea
                aria-label="Discussion context tools"
                value={tools}
                onChange={(e) => setTools(e.target.value)}
              />
            </details>
          </section>
        </WorkspaceDialog>
      )}
      {runs.length > 0 && (
        <details className="discussion-history">
          <summary>
            Previous discussions ·{" "}
            {runs.filter((r) => !conv || r.conversation === conv.id).length}
          </summary>
          {runs
            .filter((r) => !conv || r.conversation === conv.id)
            .map((r) => (
              <button
                key={r.id}
                onClick={() => {
                  setActive(r);
                  setPlan(
                    r.discussion_result?.outputs?.product_manager?.text || "",
                  );
                  if (["CREATED", "RUNNING"].includes(r.state)) follow(r.id);
                }}
              >
                {r.question}
                <span>{r.state.replaceAll("_", " ").toLowerCase()}</span>
                <ChevronRight size={15} />
              </button>
            ))}
        </details>
      )}
      {active && (
        <div className="discussion-reader-controls">
          <span>
            {outputCount
              ? `${outputCount} specialist responses`
              : running
                ? "Your team is working…"
                : "Discussion status"}
          </span>
          <button
            type="button"
            disabled={!outputCount}
            onClick={() => showInThread(firstReply.current)}
          >
            View responses
          </button>
          {active.state === "WAITING_FOR_APPROVAL" && (
            <button type="button" onClick={() => showInThread(review.current)}>
              Review decision
            </button>
          )}
        </div>
      )}
      <div
        ref={thread}
        className="discussion-thread"
        role="region"
        aria-label="Specialist responses"
        aria-live="polite"
        tabIndex={0}
      >
        {!active ? (
          <div className="discussion-intro">
            <div className="discussion-orb" aria-hidden="true">
              e
            </div>
            <div className="discussion-avatars">
              {["BA", "MA", "PM", "QA"].map((v) => (
                <span key={v}>{v}</span>
              ))}
            </div>
            <h2>What’s your next move?</h2>
            <p>
              Ask a question or add evidence. Your team will take it from here.
            </p>
            <div className="discussion-starters">
              {[
                "Review our growth strategy",
                "Understand customer feedback",
                "Prioritize product improvements",
              ].map((question) => (
                <button key={question} onClick={() => setGoal(question)}>
                  {question}
                  <ArrowUp size={15} />
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <div className="discussion-question">
              <span>You asked</span>
              <p>{active.question}</p>
            </div>
            <div className="discussion-progress" role="status">
              <span
                className={"run-dot " + (running ? "running" : "completed")}
              />
              <strong>
                {active.state === "WAITING_FOR_APPROVAL"
                  ? "Ready for your decision"
                  : active.state.replaceAll("_", " ").toLowerCase()}
              </strong>
              <span>{active.events?.at(-1)?.detail}</span>
              {running && (
                <button
                  onClick={() =>
                    act(async () => {
                      setActive(
                        await api.json("/executions/" + active.id + "/cancel", {
                          method: "POST",
                        }),
                      );
                    })
                  }
                >
                  <Square size={14} />
                  Stop
                </button>
              )}
            </div>
            <details className="discussion-handoffs">
              <summary>Team progress</summary>
              <div
                className="agent-graph compact-agent-graph"
                aria-label="Specialist handoffs"
              >
                {[
                  "business_analyst",
                  "marketing_analyst",
                  "product_manager",
                  "reviewer",
                ].map((a, i) => (
                  <span className={outputs[a] ? "complete" : ""} key={a}>
                    {outputs[a] ? <Check size={14} /> : i + 1}
                    {a.replaceAll("_", " ")}
                  </span>
                ))}
              </div>
            </details>
            {Object.entries(outputs)
              .sort(
                ([a], [b]) =>
                  [
                    "business_analyst",
                    "marketing_analyst",
                    "product_manager",
                    "reviewer",
                  ].indexOf(a) -
                  [
                    "business_analyst",
                    "marketing_analyst",
                    "product_manager",
                    "reviewer",
                  ].indexOf(b),
              )
              .map(([agent, result]: [string, any], index) => (
                <article
                  ref={index === 0 ? firstReply : undefined}
                  className="specialist-output discussion-bubble"
                  key={agent}
                >
                  <div className="specialist-avatar">
                    {agent
                      .split("_")
                      .map((p) => p[0])
                      .join("")
                      .toUpperCase()}
                  </div>
                  <div>
                    <h3>{agent.replaceAll("_", " ")}</h3>
                    <small>
                      {result.classification} · {result.mode}
                    </small>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {result.text}
                    </ReactMarkdown>
                  </div>
                </article>
              ))}
            {active.error && (
              <p className="error" role="alert">
                {active.error}
              </p>
            )}
            {active.state === "WAITING_FOR_APPROVAL" && (
              <form
                ref={review}
                className="discussion-decision"
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
                <h3>Review decision</h3>
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
                {active.discussion_result?.issues?.length > 0 && (
                  <>
                    <p>{active.discussion_result.issues.join("; ")}</p>
                    <label>
                      <input
                        type="checkbox"
                        checked={ack}
                        onChange={(e) => setAck(e.target.checked)}
                      />
                      I reviewed and reconciled the unresolved issues in my
                      edited plan
                    </label>
                  </>
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
                                plan: plan || "Rejected after review",
                              }),
                            },
                          ),
                        );
                        await load();
                      })
                    }
                  >
                    Reject decision
                  </button>
                </div>
              </form>
            )}
            {active.memory_id && (
              <p className="studio-success" role="status">
                Approved decision saved to scoped agent memory.
              </p>
            )}
          </>
        )}
      </div>
      <form
        className="discussion-composer"
        onSubmit={(e) => {
          e.preventDefault();
          if (busy || running) return;
          act(async () => {
            const c = conv || (await createConversation());
            const r = await api.json("/discussions", {
              method: "POST",
              body: JSON.stringify({
                conversation_id: c.id,
                goal,
                mode,
                allow_fallback: false,
                max_rounds: rounds,
                max_seconds: 300,
                max_output_tokens: 6144,
                context_tools: parseCalls(tools),
              }),
            });
            setActive(r);
            setPlan("");
            setGoal("");
            follow(r.id);
          });
        }}
      >
        <label className="sr-label" htmlFor="discussion-goal">
          Decision or business goal
        </label>
        <textarea
          id="discussion-goal"
          aria-label="Decision or business goal"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault();
              if (!e.repeat && !busy && !running)
                e.currentTarget.form?.requestSubmit();
            }
          }}
          placeholder="Ask your team a business or product question…"
          required
          minLength={1}
          maxLength={2000}
          rows={2}
        />
        <div>
          <button type="button" onClick={() => setSettings(!settings)}>
            <Settings2 size={16} />
            {mode === "default" ? "Workspace models" : mode}
          </button>
          <small>Decisions need your approval.</small>
          <button
            className="studio-primary"
            aria-label="Start specialist discussion"
            disabled={busy || running || goal.trim().length < 1}
          >
            <ArrowUp size={19} />
            <span>Send</span>
          </button>
        </div>
      </form>
    </div>
  );
}
