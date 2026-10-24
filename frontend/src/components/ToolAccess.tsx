import { useEffect, useState } from "react";
import { Plug, RefreshCw } from "lucide-react";
import type { client } from "../api";
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
    [loading, setLoading] = useState(false);
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
      <div className="tool-access-panel">
        <div className="studio-card-heading">
          <strong>Shared workspace connections</strong>
          <button
            type="button"
            aria-label="Refresh available connections"
            onClick={load}
          >
            <RefreshCw size={16} />
          </button>
        </div>
        <p>
          Use the same MCP servers and tool registry in development, business
          analysis, market research and strategy. Connector claims are evidence
          to verify; tool access never grants permission to write.
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {loading && <p>Loading actual connection status…</p>}
        <div className="tool-access-actions">
          <button type="button" onClick={() => onManage("servers")}>
            Manage MCP connections
          </button>
          <button type="button" onClick={() => onManage("tools")}>
            Manage registered tools
          </button>
        </div>
        {servers.map((s) => (
          <p key={s.id}>
            <strong>{s.name}</strong> · {!s.enabled ? "disabled" : s.status} ·{" "}
            {s.tools?.length || 0} discovered tools
            {s.last_checked_at
              ? " · checked " + new Date(s.last_checked_at).toLocaleString()
              : " · not verified yet"}
          </p>
        ))}
        {!tools.length && !loading && (
          <p>
            No MCP tool bindings available. Register a server, check
            health/discovery, then register one of its tools. An empty registry
            is not a connected integration.
          </p>
        )}
        {tools.map((t) => {
          const selected = calls?.find((c) => c.name === t.name),
            read = t.risk === "read";
          return (
            <div className="tool-access-item" key={t.name}>
              {onChange && read ? (
                <label className="tool-access-check">
                  <input
                    type="checkbox"
                    checked={!!selected}
                    disabled={!selected && (calls?.length || 0) >= 3}
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
              <small>
                {t.risk} ·{" "}
                {read
                  ? "May be selected as analysis evidence"
                  : "Requires a separate, explicit write approval"}
              </small>
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
        {!onChange && (
          <p>
            Use the registry to test or invoke a tool. Product exports start
            with fresh credentials and connections; private connector data is
            not silently copied into generated source.
          </p>
        )}
      </div>
    </details>
  );
}
