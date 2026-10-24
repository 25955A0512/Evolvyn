import { useState } from "react";
import {
  ShoppingBag,
  GitBranch,
  MessageSquare,
  FolderOpen,
  BookOpen,
  Globe,
  ChartNoAxesCombined,
  FileSpreadsheet,
  Plus,
  Search,
  ArrowUpRight,
} from "lucide-react";
export function ConnectorArt({
  name,
  size = 26,
}: {
  name: string;
  size?: number;
}) {
  const key = name.toLowerCase();
  const [Icon, color] =
    key.includes("shop") || key.includes("commerce") || key.includes("product")
      ? [ShoppingBag, "#75a833"]
      : key.includes("github") || key.includes("build")
        ? [GitBranch, "#262b32"]
        : key.includes("slack")
          ? [MessageSquare, "#704267"]
          : key.includes("drive")
            ? [FolderOpen, "#377bc8"]
            : key.includes("notion")
              ? [BookOpen, "#373b3a"]
              : key.includes("evidence") || key.includes("csv")
                ? [FileSpreadsheet, "#31876a"]
                : key.includes("strateg") || key.includes("analy")
                  ? [ChartNoAxesCombined, "#8070c6"]
                  : [Globe, "#3b8a9a"];
  return (
    <span
      className="connector-art"
      style={{ "--connector-color": color } as any}
    >
      <Icon size={size} />
      <svg viewBox="0 0 80 80" aria-hidden="true">
        <circle cx="65" cy="12" r="15" />
        <path d="M0 60L80 20M0 75L80 35" />
      </svg>
    </span>
  );
}
const RECIPES = [
  {
    name: "Business strategy",
    profile: "business_strategy",
    category: "Business",
    description:
      "Prioritize evidence-linked proposals using the bundled strategy MCP server.",
  },
  {
    name: "Evidence utilities",
    profile: "evidence_utilities",
    category: "Business",
    description:
      "Validate funnel data and compare observed rates with real typed tools.",
  },
  {
    name: "Shopify",
    category: "Business",
    description:
      "Connect your authorized merchant MCP endpoint for catalog, sales or store tools.",
  },
  {
    name: "GitHub",
    category: "Development",
    description:
      "Bring repository capabilities through your own authorized MCP server.",
  },
  {
    name: "Slack",
    category: "Productivity",
    description:
      "Use a configured MCP endpoint to access permitted team context.",
  },
  {
    name: "Google Drive",
    category: "Productivity",
    description:
      "Add an authorized MCP server for document and file capabilities.",
  },
  {
    name: "Notion",
    category: "Productivity",
    description:
      "Discover workspace tools exposed by your configured MCP server.",
  },
  {
    name: "Custom MCP",
    category: "Development",
    description:
      "Register a public HTTPS MCP endpoint, then discover and validate its actual tools.",
  },
];
export function ConnectorGallery({
  servers,
  onConfigure,
  onBundled,
}: {
  servers: any[];
  onConfigure: (name: string) => void;
  onBundled: (name: string, profile: string) => void;
}) {
  const [query, setQuery] = useState(""),
    [category, setCategory] = useState("All");
  return (
    <section className="connector-gallery">
      <div className="connector-gallery-heading">
        <div>
          <span className="eyebrow">DISCOVER CONNECTIONS</span>
          <h3>Bring your tools into the conversation.</h3>
        </div>
        <label>
          <Search size={18} />
          <input
            aria-label="Search connector catalog"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search connectors"
          />
        </label>
      </div>
      <div className="connector-filters">
        {["All", "Business", "Development", "Productivity"].map((c) => (
          <button
            className={c === category ? "selected" : ""}
            key={c}
            onClick={() => setCategory(c)}
          >
            {c}
          </button>
        ))}
      </div>
      <div className="connector-market-grid">
        {RECIPES.filter(
          (r) =>
            (category === "All" || r.category === category) &&
            (r.name + " " + r.description)
              .toLowerCase()
              .includes(query.toLowerCase()),
        ).map((r) => {
          const server = r.profile
            ? servers.find((s) => s.profile === r.profile)
            : null;
          return (
            <article className="connector-market-card" key={r.name}>
              <ConnectorArt name={r.name} />
              <div>
                <h4>{r.name}</h4>
                <p>{r.description}</p>
                <small>
                  {r.profile
                    ? server
                      ? `MCP ${server.status} · ${server.tools?.length || 0} discovered tools`
                      : "Bundled MCP · no key required"
                    : "Requires your MCP endpoint and permissions; not connected by this card"}
                </small>
              </div>
              <button
                aria-label={"Configure " + r.name}
                onClick={() =>
                  r.profile ? onBundled(r.name, r.profile) : onConfigure(r.name)
                }
              >
                {server ? <ArrowUpRight size={19} /> : <Plus size={20} />}
              </button>
            </article>
          );
        })}
      </div>
      <p className="connector-gallery-note">
        Catalog entries are setup recipes. Only actual registrations, successful
        checks and tool calls establish access. No third-party OAuth connection
        or store access is implied.
      </p>
    </section>
  );
}
