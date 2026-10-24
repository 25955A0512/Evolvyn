import type { Recommendation } from "../types";
export function RecommendationCards({
  items,
  selected,
  onSelect,
}: {
  items: Recommendation[];
  selected?: string | null;
  onSelect?: (r: Recommendation) => void;
}) {
  return (
    <section className="recommendations" aria-label="Business recommendations">
      <div className="report-heading">
        RECOMMENDED NEXT MOVES <span>Planning estimates · review required</span>
      </div>
      {items.map((r, index) => (
        <article
          className={"recommendation " + (selected === r.id ? "chosen" : "")}
          key={r.id}
        >
          <div className="rec-title">
            <span className="rec-number">0{index + 1}</span>
            <h3>{r.title}</h3>
            <span className="score">{r.priority_score.toFixed(2)}</span>
          </div>
          <p>{r.rationale}</p>
          <div className="rec-tags">
            <span>Effort {r.effort}/5</span>
            <span>
              Confidence {Math.round(r.confidence * 100)}% · heuristic
            </span>
            <span>{r.measurement_period_days}-day measurement</span>
          </div>
          <details>
            <summary>Evidence, assumptions & safeguards</summary>
            <ul>
              {r.evidence.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
            <p>
              <strong>Expected benefit:</strong> {r.expected_benefit}
            </p>
            <p>
              <strong>Risks:</strong> {r.risks.join("; ")}
            </p>
            <p>
              <strong>Rollback:</strong> {r.rollback}
            </p>
            <p>
              <strong>Proposed tasks:</strong>
            </p>
            <ul>
              {r.tasks.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          </details>
          {onSelect && (
            <button
              onClick={() => onSelect(r)}
              className={selected === r.id ? "primary" : ""}
            >
              {selected === r.id
                ? "Selected for review"
                : "Review this action →"}
            </button>
          )}
        </article>
      ))}
    </section>
  );
}
