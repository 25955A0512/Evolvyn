import { useEffect, useRef, useState } from "react";
import type { client } from "../api";
import type { Convo } from "../types";
import { UiIcon } from "./UiIcon";
export function ComposerActions({
  onUpload,
  onConnections,
  onCanvas,
  onReports,
  onBuild,
  disabled,
  api,
  conversations,
  onOpenConversation,
  onAgents,
}: {
  onUpload: () => void;
  onConnections: () => void;
  onCanvas: () => void;
  onReports: () => void;
  onBuild: () => void;
  disabled: boolean;
  api: ReturnType<typeof client>;
  conversations: Convo[];
  onOpenConversation: (id: string) => void;
  onAgents: (id?: string) => void;
}) {
  const ref = useRef<HTMLDetailsElement>(null);
  const [pane, setPane] = useState("main"),
    [query, setQuery] = useState(""),
    [skills, setSkills] = useState<any[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  useEffect(() => {
    if (pane !== "skills") return;
    let live = true;
    setLoading(true);
    api
      .json("/agents")
      .then((rows) => {
        if (live) setSkills(rows);
      })
      .catch((e) => {
        if (live) setError(e.message);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [pane]);
  const finish = (fn: () => void) => {
    if (ref.current) ref.current.open = false;
    fn();
  };
  const title =
    pane === "recent"
      ? "Recent conversations"
      : pane === "files"
        ? "Uploaded evidence"
        : "Agent skills";
  const rows =
    pane === "recent"
      ? conversations.map((c) => ({
          id: c.id,
          title: c.title,
          caption: c.goal,
          icon: "message-circle",
          run: () => onOpenConversation(c.id),
        }))
      : pane === "files"
        ? conversations.flatMap((c) =>
            c.files.map((f) => ({
              id: f.id,
              title: f.name,
              caption: "Open source conversation · " + c.title,
              icon: "file-text",
              run: () => onOpenConversation(c.id),
            })),
          )
        : skills.map((a) => ({
            id: a.agent,
            title: a.name,
            caption: a.goal,
            icon: "brain",
            run: () => onAgents(a.agent),
          }));
  const matching = rows
    .filter((r) =>
      (r.title + " " + r.caption).toLowerCase().includes(query.toLowerCase()),
    )
    .slice(0, 30);
  useEffect(() => {
    const pointer = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node))
        ref.current.open = false;
    };
    const keyboard = (e: KeyboardEvent) => {
      if (e.key === "Escape" && ref.current?.open) {
        ref.current.open = false;
        ref.current.querySelector("summary")?.focus();
      }
    };
    document.addEventListener("pointerdown", pointer);
    document.addEventListener("keydown", keyboard);
    return () => {
      document.removeEventListener("pointerdown", pointer);
      document.removeEventListener("keydown", keyboard);
    };
  }, []);
  const actions = [
    {
      icon: "paperclip",
      title: "Upload a local file",
      caption: "Sales, catalog, documents or feedback",
      action: onUpload,
      disabled,
    },
    {
      icon: "plug-connected",
      title: "Connect an MCP server",
      caption: "Configure and verify authorized tools",
      action: onConnections,
    },
    {
      icon: "file-text",
      title: "Saved reports & outcomes",
      caption: "Review previous decisions and results",
      action: onReports,
    },
    {
      icon: "code",
      title: "Build a product",
      caption: "Open your development workspace",
      action: onBuild,
    },
    {
      icon: "automation",
      title: "Open Canvas",
      caption: "Design pages, workflows and automations",
      action: onCanvas,
    },
  ];
  return (
    <details
      className="composer-add"
      ref={ref}
      onToggle={() => {
        if (!ref.current?.open) {
          setPane("main");
          setQuery("");
          setError("");
        }
      }}
    >
      <summary aria-label="Add files and tools" title="Add files and tools">
        <UiIcon name="plus" size={23} />
      </summary>
      <div
        className="composer-add-menu"
        role="group"
        aria-label="Files and workspace actions"
      >
        {pane === "main" ? (
          <>
            <small>ADD TO YOUR WORK</small>
            {[
              { id: "skills", name: "Use agent skills", icon: "brain" },
              {
                id: "recent",
                name: "Recent conversations",
                icon: "message-circle",
              },
              { id: "files", name: "Uploaded evidence", icon: "file-text" },
            ].map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setPane(p.id);
                  setQuery("");
                }}
              >
                <UiIcon name={p.icon} size={21} />
                <span>
                  <strong>{p.name}</strong>
                </span>
                <UiIcon name="chevron-right" size={16} />
              </button>
            ))}
            <div className="composer-menu-divider" />
            {actions.map((a) => (
              <button
                key={a.title}
                disabled={a.disabled}
                onClick={() => {
                  if (ref.current) ref.current.open = false;
                  a.action();
                }}
              >
                <UiIcon name={a.icon} size={21} />
                <span>
                  <strong>{a.title}</strong>
                  <small>{a.caption}</small>
                </span>
                <UiIcon name="chevron-right" size={16} />
              </button>
            ))}
          </>
        ) : (
          <>
            <button
              className="submenu-back"
              onClick={() => {
                setPane("main");
                setQuery("");
              }}
            >
              <UiIcon name="chevron-right" size={16} />
              {title}
            </button>
            <input
              aria-label={"Search " + title.toLowerCase()}
              placeholder={"Search " + title.toLowerCase()}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="composer-submenu-results">
              {loading && <p role="status">Loading capabilities…</p>}
              {error && <p role="alert">{error}</p>}
              {!loading && !matching.length && (
                <p>No matching {title.toLowerCase()}.</p>
              )}
              {matching.map((r) => (
                <button key={r.id} onClick={() => finish(r.run)}>
                  <UiIcon name={r.icon} />
                  <span>
                    <strong>{r.title}</strong>
                    <small>{r.caption}</small>
                  </span>
                </button>
              ))}
            </div>
            {pane === "skills" && (
              <button onClick={() => finish(() => onAgents())}>
                Manage agent skills →
              </button>
            )}
          </>
        )}
      </div>
    </details>
  );
}
