import { useState } from "react";
import { UiIcon } from "./UiIcon";
export function SourceTree({
  files,
  selected,
  onSelect,
}: {
  files: Record<string, string>;
  selected: string;
  onSelect: (file: string) => void;
}) {
  const [query, setQuery] = useState("");
  const names = Object.keys(files)
    .filter((n) => n.toLowerCase().includes(query.toLowerCase()))
    .sort();
  function level(paths: string[], prefix = "", depth = 0): any[] {
    const groups = new Map<string, string[]>();
    for (const full of paths) {
      const part = full.slice(prefix.length).split("/")[0];
      groups.set(part, [...(groups.get(part) || []), full]);
    }
    return [...groups].map(([name, children]) => {
      const file = prefix + name;
      return children.length === 1 && children[0] === file ? (
        <button
          key={file}
          className={selected === file ? "selected" : ""}
          onClick={() => onSelect(file)}
          style={{ paddingLeft: 12 + depth * 12 }}
          title={file}
        >
          <UiIcon name="file-text" size={15} />
          {name}
        </button>
      ) : (
        <details
          key={file}
          open={query ? true : depth === 0 && name !== "evolvyn"}
        >
          <summary style={{ paddingLeft: 10 + depth * 12 }}>
            <UiIcon name="folder" size={16} />
            {name}
          </summary>
          {level(children, file + "/", depth + 1)}
        </details>
      );
    });
  }
  return (
    <nav className="product-source-tree" aria-label="Project file tree">
      <label>
        <UiIcon name="search" size={15} />
        <input
          aria-label="Search project files"
          placeholder="Find a file…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </label>
      <div>{level(names)}</div>
    </nav>
  );
}
export function ArchitectureDiagram({ diagram }: { diagram: any }) {
  if (!diagram?.nodes?.length)
    return <p>No architecture diagram has been produced for this run.</p>;
  const width = 760,
    height = Math.ceil(diagram.nodes.length / 3) * 150 + 45;
  const locations = new Map<string, { x: number; y: number }>(
    diagram.nodes.map((n: any, i: number) => [
      n.id,
      { x: 25 + (i % 3) * 250, y: 25 + Math.floor(i / 3) * 150 },
    ]),
  );
  return (
    <div className="architecture-diagram">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Agent-generated architecture flow diagram"
      >
        <defs>
          <marker
            id="product-arrow"
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="4"
            orient="auto"
          >
            <path d="M0 0L8 4L0 8" fill="#728e68" />
          </marker>
        </defs>
        {diagram.edges.map((e: any, i: number) => {
          const a = locations.get(e.source),
            b = locations.get(e.target);
          return a && b ? (
            <path
              key={i}
              d={`M${a.x + 108} ${a.y + 70} C${a.x + 108} ${a.y + 110},${b.x + 108} ${b.y - 15},${b.x + 108} ${b.y}`}
              fill="none"
              stroke="#9fb392"
              strokeWidth="1.6"
              markerEnd="url(#product-arrow)"
            />
          ) : null;
        })}
        {diagram.nodes.map((n: any) => {
          const p = locations.get(n.id)!;
          return (
            <g key={n.id} transform={`translate(${p.x},${p.y})`}>
              <rect
                width="216"
                height="70"
                rx="13"
                fill="var(--surface,#fff)"
                stroke="#cbd9c1"
              />
              <text x="16" y="27" fontSize="13" fill="#819474">
                {n.id}
              </text>
              <text x="16" y="49" fontSize="15" fill="var(--ink,#34432e)">
                {n.label.length > 29 ? n.label.slice(0, 27) + "…" : n.label}
              </text>
            </g>
          );
        })}
      </svg>
      <p>{diagram.notes}</p>
    </div>
  );
}
export function ProductFlow({ run }: { run: any }) {
  const nodes = run?.definition?.nodes || [];
  const checkpoint = run?.graph_checkpoint || {};
  const labels: Record<string, string> = {
    requirements: "Approved requirements",
    file_plan: "Project folder plan",
    interview: "Requirements analyst",
    proposal: "Validated proposal",
    prd: "PRD · Product manager",
    architecture: "Architecture agent",
    developer: "Interface developer",
    reviewer: "Quality reviewer",
    contracts: "Contract checks",
    review_gate: "Review gate",
    implementation: "Source implementation",
    changes_needed: "Changes requested",
  };
  return (
    <div className="product-agent-flow" aria-label="Product agent workflow">
      {nodes.map((n: any, i: number) => {
        const status =
          checkpoint.nodes?.[n.id]?.status ||
          (checkpoint.current?.id === n.id
            ? run.state === "WAITING_FOR_APPROVAL"
              ? "APPROVAL"
              : run.state === "CANCELLED"
                ? "CANCELLED"
                : run.state === "FAILED"
                  ? "FAILED"
                  : "RUNNING"
            : checkpoint.skipped?.includes(n.id)
              ? "SKIPPED"
              : "PENDING");
        return (
          <div key={n.id} className={"product-phase " + status.toLowerCase()}>
            <span className="phase-number">
              {status === "COMPLETED" ? (
                <UiIcon name="check" size={15} />
              ) : (
                i + 1
              )}
            </span>
            <div>
              <strong>{labels[n.id] || n.id}</strong>
              <small>{status.replaceAll("_", " ").toLowerCase()}</small>
            </div>
            {i < nodes.length - 1 && <UiIcon name="chevron-right" size={15} />}
          </div>
        );
      })}
    </div>
  );
}
