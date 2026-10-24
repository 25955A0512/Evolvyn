import { useEffect, useRef, useState } from "react";
import type { client } from "../api";
import type { Convo } from "../types";
type Node = { id: string; label: string; detail: string };
type Template = {
  id?: string;
  name: string;
  focus: string;
  mode: string;
  research: boolean;
  citations: number;
  recommendations: number;
  positions: Record<string, { x: number; y: number }>;
};
export function WorkflowCanvas({
  api,
  nodes,
  conversation,
  onRun,
}: {
  api: ReturnType<typeof client>;
  nodes: Node[];
  conversation: Convo | null;
  onRun?: () => void;
}) {
  const defaults = Object.fromEntries(
    nodes.map((n, i) => [
      n.id,
      { x: 40 + (i % 2) * 350, y: 30 + Math.floor(i / 2) * 145 },
    ]),
  );
  const blank: Template = {
    name: "Business improvement loop",
    focus:
      "Analyze the supplied evidence and prioritize a measurable improvement",
    mode: "local",
    research: false,
    citations: 5,
    recommendations: 3,
    positions: defaults,
  };
  const [template, setTemplate] = useState<Template>(blank);
  const [saved, setSaved] = useState<Template[]>([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const drag = useRef<{
    id: string;
    x: number;
    y: number;
    startX: number;
    startY: number;
  } | null>(null);
  const canvas = useRef<SVGSVGElement | null>(null);
  useEffect(() => {
    api
      .json("/workflow-templates")
      .then(setSaved)
      .catch((e) => setStatus(String(e)));
  }, []);
  const position = (id: string) => template.positions[id] || defaults[id];
  function move(e: React.PointerEvent<SVGSVGElement>) {
    if (!drag.current || !canvas.current) return;
    const box = canvas.current.getBoundingClientRect();
    const d = drag.current;
    setTemplate((prev) => ({
      ...prev,
      positions: {
        ...prev.positions,
        [d.id]: {
          x: Math.max(
            0,
            Math.min(680, d.x + ((e.clientX - d.startX) * 780) / box.width),
          ),
          y: Math.max(
            0,
            Math.min(600, d.y + ((e.clientY - d.startY) * 650) / box.height),
          ),
        },
      },
    }));
  }
  return (
    <>
      <label>
        Saved workflow
        <select
          value={template.id || ""}
          onChange={(e) =>
            setTemplate(saved.find((t) => t.id === e.target.value) || blank)
          }
        >
          <option value="">New workflow</option>
          {saved.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </label>
      <div className="canvas-shell">
        <svg
          ref={canvas}
          className="workflow-canvas"
          viewBox="0 0 780 650"
          role="img"
          aria-label="Editable business improvement workflow"
          onPointerMove={move}
          onPointerUp={() => (drag.current = null)}
          onPointerCancel={() => (drag.current = null)}
        >
          {nodes.slice(1).map((node, i) => {
            const from = position(nodes[i].id),
              to = position(node.id);
            return (
              <path
                key={node.id}
                d={`M ${from.x + 135} ${from.y + 80} C ${from.x + 135} ${from.y + 120}, ${to.x + 135} ${to.y - 30}, ${to.x + 135} ${to.y}`}
                fill="none"
                stroke="#b5c9aa"
                strokeWidth="2"
              />
            );
          })}
          {nodes.map((node, i) => {
            const p = position(node.id);
            return (
              <g
                key={node.id}
                transform={`translate(${p.x} ${p.y})`}
                onPointerDown={(e) => {
                  e.currentTarget.setPointerCapture(e.pointerId);
                  drag.current = {
                    id: node.id,
                    x: p.x,
                    y: p.y,
                    startX: e.clientX,
                    startY: e.clientY,
                  };
                }}
              >
                <rect
                  width="270"
                  height="80"
                  rx="12"
                  fill={node.id === "approval" ? "#fcf6e7" : "white"}
                  stroke={node.id === "approval" ? "#c5b478" : "#c3d5b7"}
                />
                <text x="17" y="29" fill="#95ab86" fontSize="12">
                  {String(i + 1).padStart(2, "0")}
                </text>
                <text
                  x="46"
                  y="30"
                  fill="#35522b"
                  fontSize="16"
                  fontWeight="600"
                >
                  {node.label}
                </text>
                <text x="17" y="57" fill="#85967a" fontSize="10">
                  {node.detail.slice(0, 43)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <small>
        Drag stages to arrange the canvas. Human approval remains mandatory.
      </small>
      <form
        className="panel-form workflow-settings"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            const result = await api.json(
              "/workflow-templates" + (template.id ? "/" + template.id : ""),
              {
                method: template.id ? "PUT" : "POST",
                body: JSON.stringify({
                  name: template.name,
                  focus: template.focus,
                  mode: template.mode,
                  research: template.research,
                  citations: template.citations,
                  recommendations: template.recommendations,
                  positions: template.positions,
                }),
              },
            );
            setTemplate(result);
            setSaved(await api.json("/workflow-templates"));
            setStatus("Workflow saved");
          } catch (e) {
            setStatus(String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Workflow name
          <input
            value={template.name}
            onChange={(e) => setTemplate({ ...template, name: e.target.value })}
            required
            maxLength={100}
          />
        </label>
        <label>
          Focus
          <textarea
            value={template.focus}
            onChange={(e) =>
              setTemplate({ ...template, focus: e.target.value })
            }
            required
            minLength={3}
            maxLength={1000}
          />
        </label>
        <label>
          Model
          <select
            aria-label="Workflow model" value={template.mode}
            onChange={(e) => setTemplate({ ...template, mode: e.target.value })}
          >
            <option value="local">Local AI · no API key</option>
            <option value="evidence">Evidence-only fallback</option>
            <option value="provider">OpenAI · optional key</option>
            <option value="groq">Groq · optional key</option>
            <option value="gemini">Gemini · optional key</option>
          </select>
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={template.research}
            onChange={(e) =>
              setTemplate({ ...template, research: e.target.checked })
            }
          />
          Include public discussion research
        </label>
        <div className="form-row">
          <label>
            Source passages
            <input
              type="number"
              min={1}
              max={5}
              value={template.citations}
              onChange={(e) =>
                setTemplate({ ...template, citations: Number(e.target.value) })
              }
            />
          </label>
          <label>
            Recommendations
            <input
              type="number"
              min={1}
              max={3}
              value={template.recommendations}
              onChange={(e) =>
                setTemplate({
                  ...template,
                  recommendations: Number(e.target.value),
                })
              }
            />
          </label>
        </div>
        <button className="primary" disabled={busy}>
          Save workflow
        </button>
        {template.id && conversation && (
          <button
            type="button"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api.json("/conversations/" + conversation.id + "/runs", {
                  method: "POST",
                  body: JSON.stringify({
                    text: template.focus,
                    workflow_id: template.id,
                    mode: template.mode,
                    allow_fallback: true,
                  }),
                });
                setStatus("Workflow started in your conversation");
                onRun?.();
              } catch (e) {
                setStatus(String(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            Run in this conversation →
          </button>
        )}
        <p role="status">{status}</p>
      </form>
    </>
  );
}
