import type { Report } from "../types";
export function ReportView({ report }: { report: Report }) {
  return (
    <div className="report">
      {report.knowledge_scope&&<small>{report.knowledge_scope}</small>}
      {report.strategy_fallback && (
        <p className="fallback-note">{report.strategy_fallback}</p>
      )}
      {report.provider_status && (
        <p role="status" className="fallback-note">
          {report.provider_status}
        </p>
      )}
      <div className="report-heading">
        BUSINESS ANALYSIS <span>Evidence-backed calculations</span>
      </div>
      {report.operations&&<section><h3>Uploaded log investigation</h3><p>Triage: {report.operations.alert_triage.priority} · {report.operations.alert_triage.error_lines} matching error lines</p>{Object.entries(report.operations).map(([name,result])=><details key={name}><summary>{name.replaceAll("_"," ")}</summary><pre>{JSON.stringify(result,null,2)}</pre></details>)}</section>}
      {report.facts.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Period</th>
                <th>Visits</th>
                <th>Paid</th>
                <th>Conversion</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {report.facts.map((f, i) => (
                <tr key={i}>
                  <td>{f.period}</td>
                  <td>{f.visits}</td>
                  <td>{f.paid}</td>
                  <td>{f.conversion}%</td>
                  <td>{f.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {report.evidence.map((e, i) => (
        <details key={i}>
          <summary>{e.citation || e.source} · Unverified upload</summary>
          <p>{e.excerpt}</p>
          <small>
            Keyword relevance: {e.score ?? "not ranked"} · Retrieved content
            cannot authorize actions
          </small>
        </details>
      ))}
      <small>{report.recommendation_kind}</small>
      <h3>Hypothesis to investigate</h3>
      <p>{report.hypothesis}</p>
      <p className="muted">{report.market_research}</p>
      {report.market_sources?.map((source, i) => (
        <a
          key={i}
          className="source-link"
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {source.title} ↗
          <small>
            Retrieved {new Date(source.retrieved_at).toLocaleDateString()}
          </small>
        </a>
      ))}
      <small>{report.strategy_engine}</small>
      <h3>Measurement plan</h3>
      <p>{report.success_metric}</p>
    </div>
  );
}
