import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import type { client } from "../api";
export function GrowthReview({
  api,
  report,
  initialRun,
}: {
  api: ReturnType<typeof client>;
  report: any;
  initialRun?: any;
}) {
  const [run, setRun] = useState<any>(null),
    [plan, setPlan] = useState(""),
    [ack, setAck] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const watch = useRef<AbortController | null>(null);
  useEffect(() => () => watch.current?.abort(), []);
  useEffect(() => {
    if (!initialRun) return;
    setRun(initialRun);
    setPlan(initialRun.discussion_result?.outputs?.product_manager?.text || "");
    if (["CREATED", "RUNNING"].includes(initialRun.state)) {
      watch.current?.abort();
      watch.current = new AbortController();
      api
        .watch(
          initialRun.id,
          (r) => {
            setRun(r);
            if (r.state === "WAITING_FOR_APPROVAL")
              setPlan(
                r.discussion_result?.outputs?.product_manager?.text || "",
              );
          },
          watch.current.signal,
        )
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        });
    }
  }, [initialRun?.id]);
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
    <>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
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
                        r.discussion_result?.outputs?.product_manager?.text ||
                          "",
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
              <option value="default">Organization / agent model routes</option>
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
                      I have reviewed and acknowledge these unresolved issues.
                    </label>
                  </>
                )}
                <button
                  disabled={busy || !plan.trim()}
                  onClick={() =>
                    act(async () => {
                      setRun(
                        await api.json("/discussions/" + run.id + "/decision", {
                          method: "POST",
                          body: JSON.stringify({
                            approve: true,
                            plan,
                            acknowledge_issues: ack,
                          }),
                        }),
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
                        await api.json("/discussions/" + run.id + "/decision", {
                          method: "POST",
                          body: JSON.stringify({
                            approve: false,
                            plan: plan || "Rejected after review",
                          }),
                        }),
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
  );
}
