import { useEffect, useState } from "react";
import { Trash2, X, RotateCcw } from "lucide-react";
import type { client } from "../api";
export function TrashDialog({
  api,
  onClose,
  onRestore,
}: {
  api: ReturnType<typeof client>;
  onClose: () => void;
  onRestore: () => void;
}) {
  const [rows, setRows] = useState<any[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function load() {
    setRows(await api.json("/trash"));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    function key(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, []);
  return (
    <div
      className="trash-backdrop"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <section
        className="trash-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="trash-title"
      >
        <header>
          <h2 id="trash-title">
            <Trash2 size={20} /> Trash
          </h2>
          <button aria-label="Close trash" onClick={onClose}>
            <X size={20} />
          </button>
        </header>
        <p>
          Conversations stay here for 15 days, then their conversation data is
          permanently deleted. Restoring does not restart cancelled agents.
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {!rows.length && <p className="trash-empty">Trash is empty.</p>}
        {rows.map((row) => (
          <article key={row.id}>
            <div>
              <strong>{row.title}</strong>
              <small>
                {row.target_kind === "product_spec"
                  ? "Product conversation"
                  : "Business conversation"}{" "}
                · Deletes {new Date(row.purge_at).toLocaleDateString()}
              </small>
            </div>
            <button
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await api.json("/trash/" + row.id + "/restore", {
                    method: "POST",
                  });
                  await load();
                  onRestore();
                } catch (e: any) {
                  setError(e.message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <RotateCcw size={16} /> Restore
            </button>
          </article>
        ))}
      </section>
    </div>
  );
}
