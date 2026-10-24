import { useEffect, useRef, useState } from "react";
import type { client } from "../api";
import type { Convo } from "../types";
import ReactMarkdown from "react-markdown";
type API = ReturnType<typeof client>;
type Block = {
  id: string;
  kind: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
};
const emptyGraph = {
  name: "Growth feedback loop",
  goal: "Review evidence and return a measurable product hypothesis",
  entry: "review",
  nodes: [
    {
      id: "review",
      type: "agent",
      agent_id: "product_manager",
      mode: "evidence",
      prompt:
        "Review the available evidence and identify a measurable next step",
      arguments: {},
      max_visits: 2,
    },
  ],
  edges: [],
  max_steps: 12,
  max_tool_calls: 8,
  max_output_tokens: 2048,
  max_seconds: 180,
};
export function DesignCanvas({
  api,
  projectId,
  conversation,
}: {
  api: API;
  projectId: string;
  conversation: Convo | null;
}) {
  const [mode, setMode] = useState("page"),
    [saved, setSaved] = useState<any[]>([]),
    [drawing, setDrawing] = useState<any>({
      name: "Product experience",
      project_id: projectId || null,
      theme: "light",
      accent: "#336b58",
      elements: [],
      strokes: [],
      graph: emptyGraph,
      positions: { review: { x: 70, y: 90 } },
    }),
    [selected, setSelected] = useState(""),
    [tool, setTool] = useState("select"),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [products, setProducts] = useState<any[]>([]),
    [productId, setProductId] = useState(""),
    [run, setRun] = useState<any>(null),
    [tools, setTools] = useState<any[]>([]),
    [agents, setAgents] = useState<any[]>([]),
    [json, setJson] = useState(""),
    [conversations, setConversations] = useState<any[]>([]),
    [executionConversation, setExecutionConversation] = useState(
      conversation?.id || "",
    );
  const svg = useRef<SVGSVGElement>(null),
    drag = useRef<any>(null),
    watch = useRef<AbortController | null>(null);
  useEffect(() => {
    Promise.all([
      api.json("/canvas"),
      api.json("/studio/products"),
      api.json("/runtime/ontology"),
      api.json("/agents"),
      api.json("/conversations"),
    ])
      .then(([a, b, c, d, e]) => {
        setSaved(a);
        setProducts(b);
        setTools(c.tools);
        setAgents(d);
        setConversations(e);
      })
      .catch((e) => setError(e.message));
    return () => watch.current?.abort();
  }, []);
  function observe(row: any) {
    setRun(row);
    watch.current?.abort();
    watch.current = new AbortController();
    api.watch(row.id, setRun, watch.current.signal).catch((e) => {
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
  function point(e: React.PointerEvent) {
    const box = svg.current!.getBoundingClientRect();
    return {
      x: Math.max(
        0,
        Math.min(1200, ((e.clientX - box.left) * 1200) / box.width),
      ),
      y: Math.max(0, Math.min(900, ((e.clientY - box.top) * 900) / box.height)),
    };
  }
  function begin(e: React.PointerEvent, id?: string) {
    if (!svg.current) return;
    svg.current.setPointerCapture(e.pointerId);
    const p = point(e);
    if (mode === "page" && tool === "pen") {
      setDrawing((d: any) => ({ ...d, strokes: [...d.strokes, [p]] }));
      drag.current = { pen: true };
      return;
    }
    if (!id) return;
    setSelected(id);
    const item =
      mode === "page"
        ? drawing.elements.find((b: Block) => b.id === id)
        : drawing.positions[id] || { x: 50, y: 50 };
    drag.current = { id, start: p, x: item.x, y: item.y };
  }
  function move(e: React.PointerEvent) {
    if (!drag.current) return;
    const p = point(e),
      d = drag.current;
    if (d.pen) {
      setDrawing((prev: any) => {
        const strokes = [...prev.strokes];
        if (strokes[strokes.length - 1].length < 400)
          strokes[strokes.length - 1] = [...strokes[strokes.length - 1], p];
        return { ...prev, strokes };
      });
      return;
    }
    const pos = {
      x: Math.max(0, Math.min(1000, d.x + p.x - d.start.x)),
      y: Math.max(0, Math.min(800, d.y + p.y - d.start.y)),
    };
    setDrawing((prev: any) =>
      mode === "page"
        ? {
            ...prev,
            elements: prev.elements.map((b: Block) =>
              b.id === d.id ? { ...b, ...pos } : b,
            ),
          }
        : { ...prev, positions: { ...prev.positions, [d.id]: pos } },
    );
  }
  function editBlock(changes: Partial<Block>) {
    setDrawing((d: any) => ({
      ...d,
      elements: d.elements.map((b: Block) =>
        b.id === selected ? { ...b, ...changes } : b,
      ),
    }));
  }
  function editNode(changes: any) {
    setDrawing((d: any) => ({
      ...d,
      graph: {
        ...d.graph,
        nodes: d.graph.nodes.map((n: any) =>
          n.id === selected ? { ...n, ...changes } : n,
        ),
      },
    }));
  }
  const block = drawing.elements.find((b: Block) => b.id === selected),
    node = drawing.graph.nodes.find((n: any) => n.id === selected);
  async function save() {
    const { id, revision, prompt, ...payload } = drawing;
    const row = await api.json("/canvas" + (id ? "/" + id : ""), {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(id ? { revision, drawing: payload } : payload),
    });
    setDrawing(row);
    setSaved(await api.json("/canvas"));
    setNotice("Canvas saved as revision " + row.revision);
    return row;
  }
  return (
    <div className="studio-page design-workspace">
      <div className="studio-page-title">
        <span className="eyebrow">CANVAS · SHARED AGENT RUNTIME</span>
        <h1>Draw the experience. Connect the work.</h1>
        <p>
          Page sketches become versioned requirements. Workflow nodes execute
          through the same tool registry, model gateway and approval controls as
          every other Evolvyn agent.
        </p>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="studio-success">
          {notice}
        </p>
      )}
      <div className="canvas-toolbar">
        <button
          className={mode === "page" ? "selected" : ""}
          onClick={() => {
            setMode("page");
            setSelected("");
          }}
        >
          Page design
        </button>
        <button
          className={mode === "workflow" ? "selected" : ""}
          onClick={() => {
            setMode("workflow");
            setSelected("");
          }}
        >
          Node workflow
        </button>
        <input
          aria-label="Canvas name"
          value={drawing.name}
          onChange={(e) => setDrawing({ ...drawing, name: e.target.value })}
        />
        <select
          aria-label="Saved canvas"
          value={drawing.id || ""}
          onChange={(e) => {
            const row = saved.find((c) => c.id === e.target.value);
            if (row) {
              setDrawing(row);
              setSelected("");
            }
          }}
        >
          <option value="">New canvas</option>
          {saved
            .filter((c) => c.project_id === (projectId || null))
            .map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} · v{c.revision}
              </option>
            ))}
        </select>
        <button
          disabled={busy}
          className="studio-primary"
          onClick={() =>
            act(async () => {
              await save();
            })
          }
        >
          Save canvas
        </button>
        <button
          onClick={() => {
            setDrawing({
              ...drawing,
              id: undefined,
              revision: undefined,
              name: drawing.name + " copy",
            });
            setNotice("Save to create a separate canvas");
          }}
        >
          Duplicate
        </button>
      </div>
      {mode === "workflow" && (
        <label>
          Evidence conversation
          <select
            aria-label="Workflow conversation"
            value={executionConversation}
            onChange={(e) => setExecutionConversation(e.target.value)}
          >
            <option value="">Choose conversation</option>
            {conversations
              .filter((c) => c.project_id === (projectId || null))
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
          </select>
        </label>
      )}
      <div className="canvas-layout">
        <section className="canvas-board">
          <div className="canvas-toolbar">
            {mode === "page" ? (
              <>
                <button
                  className={tool === "select" ? "selected" : ""}
                  onClick={() => setTool("select")}
                >
                  Select & move
                </button>
                <button
                  className={tool === "pen" ? "selected" : ""}
                  onClick={() => setTool("pen")}
                >
                  Freehand
                </button>
                <select
                  aria-label="Add page element"
                  value=""
                  onChange={(e) => {
                    const id = "block_" + Date.now();
                    setDrawing({
                      ...drawing,
                      elements: [
                        ...drawing.elements,
                        {
                          id,
                          kind: e.target.value,
                          label:
                            e.target.value === "heading"
                              ? "Your product headline"
                              : "Describe this " + e.target.value,
                          x: 50 + (drawing.elements.length % 3) * 330,
                          y: 60 + Math.floor(drawing.elements.length / 3) * 180,
                          width: 290,
                          height: 130,
                        },
                      ],
                    });
                    setSelected(id);
                    setTool("select");
                  }}
                >
                  <option value="">+ Add labeled block</option>
                  {[
                    "heading",
                    "text",
                    "button",
                    "card",
                    "image",
                    "navigation",
                  ].map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
                <button
                  onClick={() =>
                    setDrawing({
                      ...drawing,
                      strokes: drawing.strokes.slice(0, -1),
                    })
                  }
                >
                  Undo stroke
                </button>
              </>
            ) : (
              <>
                <select
                  aria-label="Add workflow node"
                  value=""
                  onChange={(e) => {
                    const id = "node_" + Date.now();
                    const type = e.target.value;
                    setDrawing({
                      ...drawing,
                      graph: {
                        ...drawing.graph,
                        nodes: [
                          ...drawing.graph.nodes,
                          {
                            id,
                            type,
                            agent_id: "supervisor",
                            mode: "evidence",
                            prompt: "Review evidence",
                            arguments: {},
                            ...(type === "tool"
                              ? { tool: tools[0]?.name }
                              : {}),
                            ...(type === "condition"
                              ? {
                                  condition: {
                                    path: "nodes.review.output.text",
                                    op: "exists",
                                  },
                                }
                              : {}),
                          },
                        ],
                      },
                      positions: {
                        ...drawing.positions,
                        [id]: {
                          x: 70 + (drawing.graph.nodes.length % 3) * 340,
                          y:
                            90 +
                            Math.floor(drawing.graph.nodes.length / 3) * 190,
                        },
                      },
                    });
                    setSelected(id);
                  }}
                >
                  <option value="">+ Add node</option>
                  {["agent", "tool", "condition", "approval", "result"].map(
                    (t) => (
                      <option key={t}>{t}</option>
                    ),
                  )}
                </select>
                <button
                  disabled={busy || !executionConversation}
                  onClick={() =>
                    act(async () => {
                      const row = await save();
                      const graph = await api.json(
                        "/canvas/" + row.id + "/publish-graph",
                        { method: "POST" },
                      );
                      const execution = await api.json(
                        "/harness/graphs/" + graph.id + "/run",
                        {
                          method: "POST",
                          body: JSON.stringify({
                            conversation_id: executionConversation,
                          }),
                        },
                      );
                      setRun(execution);
                      watch.current?.abort();
                      watch.current = new AbortController();
                      api
                        .watch(execution.id, setRun, watch.current.signal)
                        .catch((e) => {
                          if (e.name !== "AbortError") setError(e.message);
                        });
                    })
                  }
                >
                  Save & run workflow
                </button>
              </>
            )}
          </div>
          <svg
            ref={svg}
            viewBox="0 0 1200 900"
            className={"design-board " + drawing.theme}
            aria-label={
              mode === "page"
                ? "Page design canvas"
                : "Executable workflow canvas"
            }
            onPointerDown={(e) => begin(e)}
            onPointerMove={move}
            onPointerUp={() => (drag.current = null)}
            onPointerCancel={() => (drag.current = null)}
          >
            <defs>
              <pattern
                id="canvas-grid"
                width="30"
                height="30"
                patternUnits="userSpaceOnUse"
              >
                <circle cx="1" cy="1" r="1" fill="#c3cdc5" />
              </pattern>
              <marker
                id="arrow-canvas"
                markerWidth="10"
                markerHeight="8"
                refX="9"
                refY="4"
                orient="auto"
              >
                <path d="M0,0 L10,4 L0,8" fill="#789485" />
              </marker>
            </defs>
            <rect width="1200" height="900" fill="url(#canvas-grid)" />
            {mode === "page" ? (
              <>
                {drawing.strokes.map((s: any[], i: number) => (
                  <polyline
                    key={i}
                    points={s.map((p) => p.x + "," + p.y).join(" ")}
                    fill="none"
                    stroke={drawing.accent}
                    strokeWidth="3"
                  />
                ))}
                {drawing.elements.map((b: Block) => (
                  <g
                    key={b.id}
                    transform={`translate(${b.x},${b.y})`}
                    onPointerDown={(e) => {
                      e.stopPropagation();
                      begin(e, b.id);
                    }}
                    className="canvas-node"
                  >
                    <rect
                      width={b.width}
                      height={b.height}
                      rx="10"
                      fill={drawing.theme === "dark" ? "#26342b" : "white"}
                      stroke={selected === b.id ? drawing.accent : "#b4c7b9"}
                      strokeWidth={selected === b.id ? 3 : 1}
                    />
                    <text x="15" y="28" fill={drawing.accent} fontSize="15">
                      {b.kind.toUpperCase()}
                    </text>
                    <foreignObject
                      x="15"
                      y="40"
                      width={Math.max(10, b.width - 30)}
                      height={Math.max(10, b.height - 45)}
                    >
                      <div
                        style={{
                          fontSize: b.kind === "heading" ? 24 : 18,
                          color:
                            drawing.theme === "dark" ? "#eef4ef" : "#26352f",
                          overflowWrap: "anywhere",
                        }}
                      >
                        {b.label}
                      </div>
                    </foreignObject>
                  </g>
                ))}
              </>
            ) : (
              <>
                {drawing.graph.edges.map((e: any, i: number) => {
                  const a = drawing.positions[e.source] || { x: 50, y: 50 },
                    b = drawing.positions[e.target] || { x: 50, y: 50 };
                  return (
                    <g key={i}>
                      <path
                        d={`M${a.x + 130},${a.y + 90} C${a.x + 130},${a.y + 140} ${b.x + 130},${b.y - 40} ${b.x + 130},${b.y}`}
                        fill="none"
                        stroke="#789485"
                        strokeWidth="3"
                        markerEnd="url(#arrow-canvas)"
                      />
                      <text
                        x={(a.x + b.x) / 2 + 140}
                        y={(a.y + b.y) / 2 + 40}
                        fontSize="16"
                      >
                        {e.when || "always"}
                      </text>
                    </g>
                  );
                })}
                {drawing.graph.nodes.map((n: any) => {
                  const p = drawing.positions[n.id] || { x: 50, y: 50 };
                  return (
                    <g
                      key={n.id}
                      transform={`translate(${p.x},${p.y})`}
                      onPointerDown={(e) => {
                        e.stopPropagation();
                        begin(e, n.id);
                      }}
                      className="canvas-node"
                    >
                      <rect
                        width="270"
                        height="90"
                        rx="14"
                        fill="white"
                        stroke={selected === n.id ? "#336b58" : "#b4c7b9"}
                        strokeWidth="2"
                      />
                      <text x="18" y="28" fontSize="16" fill="#336b58">
                        {n.type} ·{" "}
                        {n.id === drawing.graph.entry ? "entry" : n.agent_id}
                      </text>
                      <text x="18" y="60" fontSize="17">
                        {(n.tool || n.prompt || n.id).slice(0, 26)}
                      </text>
                    </g>
                  );
                })}
              </>
            )}
          </svg>
        </section>
        <aside className="studio-card canvas-inspector">
          {mode === "page" ? (
            <>
              <h3>Page properties</h3>
              <label>
                Theme
                <select
                  value={drawing.theme}
                  onChange={(e) =>
                    setDrawing({ ...drawing, theme: e.target.value })
                  }
                >
                  <option>light</option>
                  <option>dark</option>
                </select>
              </label>
              <label>
                Brand color
                <input
                  aria-label="Canvas accent"
                  type="color"
                  value={drawing.accent}
                  onChange={(e) =>
                    setDrawing({ ...drawing, accent: e.target.value })
                  }
                />
              </label>
              {block && (
                <>
                  <label>
                    Block label
                    <textarea
                      aria-label="Block label"
                      value={block.label}
                      maxLength={300}
                      onChange={(e) => editBlock({ label: e.target.value })}
                    />
                  </label>
                  <label>
                    Width
                    <input
                      type="number"
                      min={40}
                      max={1200}
                      value={block.width}
                      onChange={(e) =>
                        editBlock({ width: Number(e.target.value) })
                      }
                    />
                  </label>
                  <label>
                    Height
                    <input
                      type="number"
                      min={30}
                      max={900}
                      value={block.height}
                      onChange={(e) =>
                        editBlock({ height: Number(e.target.value) })
                      }
                    />
                  </label>
                  <button
                    onClick={() => {
                      setDrawing({
                        ...drawing,
                        elements: drawing.elements.filter(
                          (b: Block) => b.id !== selected,
                        ),
                      });
                      setSelected("");
                    }}
                  >
                    Delete block
                  </button>
                </>
              )}
              <p>
                Drag blocks to arrange the page. Label sketches so the agent has
                precise intent. Freehand strokes are preserved; OCR is not
                assumed.
              </p>
              <label>
                Apply to product
                <select
                  aria-label="Canvas product"
                  value={productId}
                  onChange={(e) => setProductId(e.target.value)}
                >
                  <option value="">Choose product</option>
                  {products
                    .filter((p) => p.project_id === (projectId || null))
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} · v{p.revision}
                      </option>
                    ))}
                </select>
              </label>
              <button
                disabled={!productId || busy}
                onClick={() =>
                  act(async () => {
                    const row = await save(),
                      product = await api.json("/studio/products/" + productId);
                    await api.json("/canvas/" + row.id + "/apply", {
                      method: "POST",
                      body: JSON.stringify({
                        product_id: productId,
                        revision: product.revision,
                        canvas_revision: row.revision,
                      }),
                    });
                    setProducts(await api.json("/studio/products"));
                    setNotice(
                      "Applied design to a new requirements revision. Open Build a product and rebuild.",
                    );
                  })
                }
              >
                Save & apply design
              </button>
              {drawing.prompt && (
                <details>
                  <summary>Generated design prompt</summary>
                  <pre>{drawing.prompt}</pre>
                </details>
              )}
            </>
          ) : (
            <>
              <h3>Executable workflow</h3>
              <label>
                Goal
                <textarea
                  value={drawing.graph.goal}
                  onChange={(e) =>
                    setDrawing({
                      ...drawing,
                      graph: {
                        ...drawing.graph,
                        goal: e.target.value,
                        name: drawing.name,
                      },
                    })
                  }
                />
              </label>
              <label>
                Entry node
                <select
                  value={drawing.graph.entry}
                  onChange={(e) =>
                    setDrawing({
                      ...drawing,
                      graph: { ...drawing.graph, entry: e.target.value },
                    })
                  }
                >
                  {drawing.graph.nodes.map((n: any) => (
                    <option key={n.id}>{n.id}</option>
                  ))}
                </select>
              </label>
              {node && (
                <>
                  <strong>{node.id}</strong>
                  <label>
                    Agent contract
                    <select
                      value={node.agent_id}
                      onChange={(e) => editNode({ agent_id: e.target.value })}
                    >
                      {agents.map((a) => (
                        <option key={a.agent} value={a.agent}>
                          {a.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  {node.type === "tool" && (
                    <label>
                      Registered tool
                      <select
                        value={node.tool}
                        onChange={(e) => editNode({ tool: e.target.value })}
                      >
                        {tools.map((t) => (
                          <option key={t.name}>{t.name}</option>
                        ))}
                      </select>
                    </label>
                  )}
                  {node.type === "agent" && (
                    <>
                      <label>
                        Prompt
                        <textarea
                          value={node.prompt}
                          onChange={(e) => editNode({ prompt: e.target.value })}
                        />
                      </label>
                      <label>
                        Model route
                        <select
                          value={node.mode}
                          onChange={(e) => editNode({ mode: e.target.value })}
                        >
                          {[
                            "default",
                            "evidence",
                            "local",
                            "provider",
                            "groq",
                            "gemini",
                            "openrouter",
                          ].map((v) => (
                            <option key={v}>{v}</option>
                          ))}
                        </select>
                      </label>
                    </>
                  )}
                  <label>
                    Maximum visits
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={node.max_visits || 10}
                      onChange={(e) =>
                        editNode({ max_visits: Number(e.target.value) })
                      }
                    />
                  </label>
                  <label>
                    Arguments JSON
                    <textarea
                      key={node.id + ":arguments"}
                      defaultValue={JSON.stringify(
                        node.arguments || {},
                        null,
                        2,
                      )}
                      onBlur={(e) => {
                        try {
                          editNode({ arguments: JSON.parse(e.target.value) });
                          setError("");
                        } catch {
                          setError("Arguments must be valid JSON");
                        }
                      }}
                    />
                  </label>
                  {node.type === "condition" && (
                    <label>
                      Condition JSON
                      <textarea
                        key={node.id + ":condition"}
                        defaultValue={JSON.stringify(node.condition, null, 2)}
                        onBlur={(e) => {
                          try {
                            editNode({ condition: JSON.parse(e.target.value) });
                            setError("");
                          } catch {
                            setError("Condition must be valid JSON");
                          }
                        }}
                      />
                    </label>
                  )}
                  <button
                    onClick={() => {
                      if (drawing.graph.nodes.length === 1) return;
                      const positions = { ...drawing.positions };
                      delete positions[selected];
                      const nodes = drawing.graph.nodes.filter(
                        (n: any) => n.id !== selected,
                      );
                      setDrawing({
                        ...drawing,
                        positions,
                        graph: {
                          ...drawing.graph,
                          nodes,
                          entry:
                            drawing.graph.entry === selected
                              ? nodes[0].id
                              : drawing.graph.entry,
                          edges: drawing.graph.edges.filter(
                            (e: any) =>
                              e.source !== selected && e.target !== selected,
                          ),
                        },
                      });
                      setSelected("");
                    }}
                  >
                    Delete node
                  </button>
                </>
              )}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const d = Object.fromEntries(new FormData(e.currentTarget));
                  setDrawing({
                    ...drawing,
                    graph: {
                      ...drawing.graph,
                      edges: [...drawing.graph.edges, d],
                    },
                  });
                }}
              >
                <h4>Connect nodes</h4>
                <label>
                  From
                  <select name="source">
                    {drawing.graph.nodes.map((n: any) => (
                      <option key={n.id}>{n.id}</option>
                    ))}
                  </select>
                </label>
                <label>
                  To
                  <select name="target">
                    {drawing.graph.nodes.map((n: any) => (
                      <option key={n.id}>{n.id}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Branch
                  <select name="when">
                    {["always", "true", "false", "approved", "rejected"].map(
                      (v) => (
                        <option key={v}>{v}</option>
                      ),
                    )}
                  </select>
                </label>
                <button>Add connection</button>
              </form>
              {drawing.graph.edges.map((e: any, i: number) => (
                <button
                  key={i}
                  onClick={() =>
                    setDrawing({
                      ...drawing,
                      graph: {
                        ...drawing.graph,
                        edges: drawing.graph.edges.filter(
                          (_: any, j: number) => j !== i,
                        ),
                      },
                    })
                  }
                >
                  {e.source} → {e.target} ({e.when || "always"}) ×
                </button>
              ))}
              <details>
                <summary
                  onClick={() =>
                    setJson(JSON.stringify(drawing.graph, null, 2))
                  }
                >
                  Advanced graph and loop budgets
                </summary>
                <textarea
                  aria-label="Graph JSON"
                  value={json}
                  onChange={(e) => setJson(e.target.value)}
                />
                <button
                  onClick={() => {
                    try {
                      const graph = JSON.parse(json);
                      if (
                        !graph ||
                        typeof graph.name !== "string" ||
                        typeof graph.goal !== "string" ||
                        typeof graph.entry !== "string" ||
                        !Array.isArray(graph.nodes) ||
                        !Array.isArray(graph.edges) ||
                        graph.nodes.length < 1 ||
                        graph.nodes.length > 32 ||
                        graph.edges.length > 64 ||
                        !graph.nodes.every(
                          (n: any) =>
                            n &&
                            typeof n.id === "string" &&
                            [
                              "agent",
                              "tool",
                              "condition",
                              "approval",
                              "result",
                            ].includes(n.type) &&
                            [n.prompt, n.tool, n.agent_id].every(
                              (v) => v === undefined || typeof v === "string",
                            ),
                        ) ||
                        !graph.edges.every(
                          (e: any) =>
                            e &&
                            typeof e.source === "string" &&
                            typeof e.target === "string" &&
                            (e.when === undefined ||
                              typeof e.when === "string"),
                        )
                      )
                        throw Error("Invalid graph shape");
                      setDrawing({ ...drawing, graph });
                      setError("");
                    } catch {
                      setError(
                        "Use a graph object with a name, goal, entry, valid nodes and edges. Server validation checks execution rules when saving.",
                      );
                    }
                  }}
                >
                  Apply graph JSON
                </button>
              </details>
              <p>
                All nodes must be reachable. Conditions, approvals, cycles,
                retries and execution budgets are validated by the server.
                Writes require the existing approval flow.
              </p>
            </>
          )}
        </aside>
      </div>
      {run && (
        <div className="studio-card">
          <h3>Workflow execution · {run.state}</h3>
          <p>{run.error}</p>
          {run.events?.map((e: any, i: number) => (
            <p key={i}>
              <strong>{e.stage}</strong> · {e.detail}
            </p>
          ))}
          <ReactMarkdown>{run.output || ""}</ReactMarkdown>
          {["CREATED", "RUNNING"].includes(run.state) && (
            <button
              onClick={() =>
                act(async () => {
                  setRun(
                    await api.json("/executions/" + run.id + "/cancel", {
                      method: "POST",
                    }),
                  );
                })
              }
            >
              Stop workflow
            </button>
          )}
          {run.state === "WAITING_FOR_APPROVAL" &&
            run.graph_checkpoint?.pending && (
              <>
                <pre>
                  {JSON.stringify(run.graph_checkpoint.pending, null, 2)}
                </pre>
                <button
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      observe(
                        await api.json(
                          "/harness/executions/" + run.id + "/decision",
                          {
                            method: "POST",
                            body: JSON.stringify({
                              approve: true,
                              binding: run.graph_checkpoint.pending.binding,
                            }),
                          },
                        ),
                      );
                    })
                  }
                >
                  Approve exact pending action
                </button>
                <button
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      observe(
                        await api.json(
                          "/harness/executions/" + run.id + "/decision",
                          {
                            method: "POST",
                            body: JSON.stringify({
                              approve: false,
                              binding: run.graph_checkpoint.pending.binding,
                            }),
                          },
                        ),
                      );
                    })
                  }
                >
                  Reject pending action
                </button>
              </>
            )}
        </div>
      )}
    </div>
  );
}
