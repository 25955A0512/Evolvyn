import { useEffect, useRef } from "react";
import { UiIcon } from "./UiIcon";
export function ComposerActions({
  onUpload,
  onConnections,
  onCanvas,
  onReports,
  onBuild,
  disabled,
}: {
  onUpload: () => void;
  onConnections: () => void;
  onCanvas: () => void;
  onReports: () => void;
  onBuild: () => void;
  disabled: boolean;
}) {
  const ref = useRef<HTMLDetailsElement>(null);
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
    <details className="composer-add" ref={ref}>
      <summary aria-label="Add files and tools" title="Add files and tools">
        <UiIcon name="plus" size={23} />
      </summary>
      <div
        className="composer-add-menu"
        role="group"
        aria-label="Files and workspace actions"
      >
        <small>ADD TO YOUR WORK</small>
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
      </div>
    </details>
  );
}
