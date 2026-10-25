import { useState } from "react";
import { UiIcon } from "./UiIcon";
import { serviceLogos } from "../assets/connector-logos";
import { instagramLogo } from "../assets/instagram-logo";
import { Plus, Search, ArrowUpRight } from "lucide-react";
export function ConnectorArt({
  name,
  size = 26,
}: {
  name: string;
  size?: number;
}) {
  const key = name.toLowerCase();
  const logo = key.includes("instagram")
    ? "instagram"
    : key.includes("gemini")
      ? "gemini"
      : key.includes("groq")
        ? "groq"
        : key.includes("github")
          ? "github"
          : key.includes("slack")
            ? "slack"
            : key.includes("drive")
              ? "google-drive"
              : key.includes("notion")
                ? "notion"
                : key.includes("shopify")
                  ? "shopify"
                  : null;
  const asset = key.includes("github")
    ? "brand-github"
    : key.includes("slack")
      ? "brand-slack"
      : key.includes("drive")
        ? "brand-google-drive"
        : key.includes("notion")
          ? "brand-notion"
          : key.includes("figma")
            ? "brand-figma"
            : key.includes("shop") || key.includes("commerce")
              ? "shopping-bag"
              : key.includes("evidence") || key.includes("csv")
                ? "file-spreadsheet"
                : key.includes("strateg") || key.includes("analy")
                  ? "chart-line"
                  : key.includes("build")
                    ? "code"
                    : "world";
  const color =
    key.includes("shop") || key.includes("commerce") || key.includes("product")
      ? "#75a833"
      : key.includes("github") || key.includes("build")
        ? "#262b32"
        : key.includes("slack")
          ? "#704267"
          : key.includes("drive")
            ? "#377bc8"
            : key.includes("notion")
              ? "#373b3a"
              : key.includes("evidence") || key.includes("csv")
                ? "#31876a"
                : key.includes("strateg") || key.includes("analy")
                  ? "#8070c6"
                  : "#3b8a9a";
  return (
    <span
      className="connector-art"
      style={{ "--connector-color": color } as any}
    >
      {logo ? (
        <img
          className="connector-logo"
          src={logo === "instagram" ? instagramLogo : serviceLogos[logo]}
          width={size + 6}
          height={size + 6}
          alt=""
        />
      ) : (
        <UiIcon name={asset} size={size} />
      )}
      {!logo && (
        <svg viewBox="0 0 80 80" aria-hidden="true">
          <circle cx="65" cy="12" r="15" />
          <path d="M0 60L80 20M0 75L80 35" />
        </svg>
      )}
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
  busy = false,
}: {
  servers: any[];
  onConfigure: (name: string) => void;
  onBundled: (name: string, profile: string) => void;
  busy?: boolean;
}) {
  const [query, setQuery] = useState(""),
    [category, setCategory] = useState("All");
  return (
    <section className="connector-gallery">
      <div className="connector-gallery-heading">
        <div>
          <h3>Discover connectors</h3>
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
                      : "Local MCP · no key"
                    : "Setup required"}
                </small>
              </div>
              <button
                aria-label={"Configure " + r.name}
                disabled={busy}
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
        Connections are verified through successful checks.
      </p>
    </section>
  );
}
