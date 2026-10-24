import { Activity, Check, X, Square } from "lucide-react";
import { useState } from "react";
import type { Run } from "../types";
import { RecommendationCards } from "./RecommendationCards";
export function ExecutionView({
  run,
  busy,
  onDecide,
  onCancel,
  onArtifact,
}: {
  run: Run;
  busy: boolean;
  onDecide: (
    r: Run,
    approve: boolean,
    plan: string,
    recommendationId?: string,
  ) => void;
  onCancel: (id: string) => void;
  onArtifact: (id: string) => void;
}) {
  const [plan, setPlan] = useState<string | null>(null);
  const [recommendationId, setRecommendationId] = useState<string | null>(null);
  const active = ["CREATED", "RUNNING"].includes(run.state);
  return (
    <div className="execution">
      <details open={active}>
        <summary>
          <Activity size={14} /> Agent activity ·{" "}
          {run.state.replaceAll("_", " ").toLowerCase()}
        </summary>
        {run.events.map((e, i) => (
          <div className="event" key={i}>
            <Check size={13} />
            <span>
              <strong>{e.stage}</strong>
              {e.detail}
            </span>
          </div>
        ))}
        {active && (
          <button onClick={() => onCancel(run.id)}>
            <Square size={13} /> Stop analysis
          </button>
        )}
      </details>
      {!!run.report?.recommendations?.length && (
        <RecommendationCards
          items={run.report.recommendations}
          selected={recommendationId}
          onSelect={
            run.state === "WAITING_FOR_APPROVAL"
              ? (r) => {
                  setRecommendationId(r.id);
                  setPlan(r.title + "\n\n" + r.rationale);
                }
              : undefined
          }
        />
      )}
      {run.error && <p className="error">{run.error}</p>}
      {run.state === "WAITING_FOR_APPROVAL" && run.report && (
        <div className="approval">
          <h3>Review proposed action</h3>
          <p>
            Create an internal experiment brief. Business results will need
            separate measurement.
          </p>
          <textarea
            aria-label="Action plan"
            value={plan ?? run.report.plan}
            onChange={(e) => setPlan(e.target.value)}
          />
          <div>
            <button
              disabled={busy || !(plan ?? run.report.plan).trim()}
              className="primary"
              onClick={() =>
                onDecide(
                  run,
                  true,
                  plan ?? run.report!.plan,
                  recommendationId || undefined,
                )
              }
            >
              <Check size={15} /> Approve & create brief
            </button>
            <button
              disabled={busy}
              onClick={() =>
                onDecide(
                  run,
                  false,
                  plan ?? run.report!.plan,
                  recommendationId || undefined,
                )
              }
            >
              <X size={15} /> Reject
            </button>
          </div>
        </div>
      )}
      {run.artifact && (
        <button className="success" onClick={() => onArtifact(run.artifact!)}>
          ✓ Open saved experiment brief →
        </button>
      )}
      {run.state === "CANCELLED" && (
        <p className="muted">Cancelled. No action was executed.</p>
      )}
    </div>
  );
}
