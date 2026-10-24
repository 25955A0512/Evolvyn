import { useEffect, useState } from "react";
import {
  Plug,
  RefreshCw,
  Plus,
  Settings2,
  Search,
  ChevronRight,
} from "lucide-react";
import type { client } from "../api";
import { ConnectorArt } from "./ConnectorGallery";
export type ManageConnections = (
  tab?: "servers" | "tools",
  serverName?: string,
) => void;
export type ContextCall = { name: string; arguments: Record<string, unknown> };
export function parseCalls(value: string): ContextCall[] {
  try {
    const rows = JSON.parse(value);
    return Array.isArray(rows) &&
      rows.every(
        (c) =>
          c &&
          typeof c.name === "string" &&
          c.arguments &&
          typeof c.arguments === "object" &&
          !Array.isArray(c.arguments),
      )
      ? rows
      : [];
  } catch {
    return [];
  }
}
export function ToolAccess({
  api,
  onManage,
  calls,
  onChange,
  conversationId,
  inline = false,
}: {
  api: ReturnType<typeof client>;
  onManage: ManageConnections;
  calls?: ContextCall[];
  onChange?: (calls: ContextCall[]) => void;
  conversationId?: string;
  inline?: boolean;
}) {
  const [tools, setTools] = useState<any[]>([]),
    [servers, setServers] = useState<any[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [query, setQuery] = useState("");
  async function load() {
    setLoading(true);
    setError("");
    try {
      const [a, b] = await Promise.all([
        api.json("/tool-registry"),
        api.json("/mcp/servers"),
      ]);
      setTools(a.filter((t: any) => t.adapter === "mcp"));
      setServers(b);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  return (
    <details className={"tool-access " + (inline ? "inline" : "")}>
      <summary>
        <Plug size={17} />
        Connections & tools{calls?.length ? ` · ${calls.length} selected` : ""}
      </summary>
      <div className="tool-access-panel connector-popover">
        <div className="connector-search">
          <Search size={16} />
          <input
            aria-label="Search connections and tools"
            placeholder="Search connectors and tools"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button
            type="button"
            aria-label="Refresh available connections"
            onClick={load}
          >
            <RefreshCw size={16} />
          </button>
        </div>
        <div className="connector-menu-actions">
          <button type="button" onClick={() => onManage("servers")}>
            <Plus size={18} /> Add connector <ChevronRight size={16} />
          </button>
          <button type="button" onClick={() => onManage("servers")}>
            <Settings2 size={18} /> Manage connectors
          </button>
          <button type="button" onClick={() => onManage("tools")}>
            <Search size={18} /> Tool access <ChevronRight size={16} />
          </button>
        </div>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {loading && <p>Loading actual connection status…</p>}
        {servers
          .filter((s) =>
            (s.name + " " + (s.profile || ""))
              .toLowerCase()
              .includes(query.toLowerCase()),
          )
          .map((s) => (
            <div className="connector-menu-row" key={s.id}>
              <ConnectorArt
                name={s.profile === "github" ? "GitHub" : s.name}
                size={24}
              />
              <div>
                <strong>{s.name}</strong>
                <small>
                  {!s.enabled
                    ? "Disabled"
                    : s.status === "healthy"
                      ? "Last test passed"
                      : "Needs connection test"}{" "}
                  · {s.tools?.length || 0} tools
                </small>
              </div>
              <span
                className={
                  "connection-dot " +
                  (s.enabled && s.status === "healthy" ? "healthy" : "")
                }
              />
            </div>
          ))}
        {!tools.length && !loading && (
          <p className="connector-empty">
            Connect a service to make its tools available here.
          </p>
        )}
        {tools
          .filter((t) =>
            (t.name + " " + t.description)
              .toLowerCase()
              .includes(query.toLowerCase()),
          )
          .map((t) => {
            const selected = calls?.find((c) => c.name === t.name),
              read = t.risk === "read";
            return (
              <div className="tool-access-item" key={t.name}>
                {onChange && read ? (
                  <label className="tool-access-check">
                    <input
                      type="checkbox"
                      checked={!!selected}
                      disabled={
                        !selected && (!t.enabled || (calls?.length || 0) >= 3)
                      }
                      onChange={(e) => {
                        if (e.target.checked) {
                          const args: Record<string, unknown> = {};
                          if (
                            t.input_schema?.properties?.conversation_id &&
                            conversationId
                          )
                            args.conversation_id = conversationId;
                          onChange([
                            ...(calls || []),
                            { name: t.name, arguments: args },
                          ]);
                        } else
                          onChange(
                            (calls || []).filter((c) => c.name !== t.name),
                          );
                      }}
                    />
                    {t.name}
                  </label>
                ) : (
                  <strong>{t.name}</strong>
                )}
                <p>{t.description}</p>
                <small>{read ? "Read access" : "Approval required"}</small>
                {selected && onChange && (
                  <label>
                    Arguments JSON
                    <textarea
                      aria-label={"Arguments for " + t.name}
                      key={t.name}
                      defaultValue={JSON.stringify(selected.arguments, null, 2)}
                      onBlur={(e) => {
                        try {
                          const args = JSON.parse(e.target.value);
                          if (
                            !args ||
                            Array.isArray(args) ||
                            typeof args !== "object"
                          )
                            throw Error();
                          onChange(
                            (calls || []).map((c) =>
                              c.name === t.name ? { ...c, arguments: args } : c,
                            ),
                          );
                          setError("");
                        } catch {
                          setError("Tool arguments must be a JSON object");
                        }
                      }}
                    />
                    <details>
                      <summary>Required tool contract</summary>
                      <pre>{JSON.stringify(t.input_schema, null, 2)}</pre>
                    </details>
                  </label>
                )}
              </div>
            );
          })}
      </div>
    </details>
  );
}
