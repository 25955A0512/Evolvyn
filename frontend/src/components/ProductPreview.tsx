import { useEffect, useState } from "react";
import type { client } from "../api";
type API = ReturnType<typeof client>;
export function ProductPreview({ api, build }: { api: API; build: any }) {
  const [entity, setEntity] = useState(build.spec.entities[0]?.name || ""),
    [rows, setRows] = useState<any[]>([]),
    [error, setError] = useState("");
  const schema = build.spec.entities.find((e: any) => e.name === entity);
  async function load() {
    setRows(
      await api.json("/studio/builds/" + build.id + "/preview/" + entity),
    );
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [entity, build.id]);
  return (
    <section
      className={"product-preview " + build.spec.theme}
      style={{ "--product-accent": build.spec.accent } as any}
    >
      <div className="prototype-label">
        <span className="live-dot" />
        Interactive prototype · saved workspace data
      </div>
      <div className="product-preview-header">
        <div>
          <small>{build.spec.audience}</small>
          <h2>{build.spec.name}</h2>
          <p>{build.spec.goal}</p>
        </div>
        <span className="prototype-avatar">{build.spec.name[0]}</span>
      </div>
      <nav>
        {build.spec.entities.map((e: any) => (
          <button
            key={e.name}
            className={entity === e.name ? "selected" : ""}
            onClick={() => setEntity(e.name)}
          >
            {e.label}
          </button>
        ))}
      </nav>
      {build.spec.experience && (
        <section className="prototype-experience">
          <h2>{build.spec.experience.headline}</h2>
          <p>{build.spec.experience.description}</p>
          <div>
            {build.spec.experience.sections.map((s: any, i: number) => (
              <article key={i}>
                <h3>{s.heading}</h3>
                <p>{s.text}</p>
              </article>
            ))}
          </div>
        </section>
      )}
      {error && (
        <div role="alert" className="error">
          {error}
        </div>
      )}
      {!!build.spec.design?.elements?.length && (
        <section
          className="design-preview-layout"
          aria-label="Canvas design preview"
        >
          {[...build.spec.design.elements]
            .sort((a: any, b: any) => a.y - b.y || a.x - b.x)
            .map((e: any) => (
              <article key={e.id} className={e.kind}>
                {e.kind === "heading" ? (
                  <h3>{e.label}</h3>
                ) : e.kind === "button" ? (
                  <span>{e.label}</span>
                ) : (
                  <p>
                    {e.kind === "image" ? "◇ " : ""}
                    {e.label}
                  </p>
                )}
              </article>
            ))}
        </section>
      )}
      <div className="prototype-stat">
        <strong>{rows.length}</strong>
        <span>{schema?.label} in this prototype</span>
      </div>
      {schema && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const values: any = Object.fromEntries(new FormData(form));
            for (const f of schema.fields)
              if (f.type === "number") values[f.name] = Number(values[f.name]);
            try {
              await api.json(
                "/studio/builds/" + build.id + "/preview/" + entity,
                { method: "POST", body: JSON.stringify(values) },
              );
              form.reset();
              await load();
            } catch (e: any) {
              setError(e.message);
            }
          }}
        >
          {schema.fields.map((f: any) => (
            <label key={f.name}>
              {f.label}
              <input
                name={f.name}
                type={
                  f.type === "number"
                    ? "number"
                    : f.type === "date"
                      ? "date"
                      : f.type === "email"
                        ? "email"
                        : "text"
                }
                required
                maxLength={2000}
              />
            </label>
          ))}
          <button className="primary">Add {schema.label}</button>
        </form>
      )}
      <div className="prototype-records">
        {!rows.length && <p>Your product is ready for its first record.</p>}
        {rows.map((row) => (
          <article key={row.id}>
            <div>
              {Object.entries(row.data).map(([key, value]) => (
                <span key={key}>
                  <small>
                    {schema.fields.find((f: any) => f.name === key)?.label ||
                      key}
                  </small>
                  <strong>{String(value)}</strong>
                </span>
              ))}
            </div>
            <button
              onClick={async () => {
                try {
                  await api.json(
                    "/studio/builds/" +
                      build.id +
                      "/preview/" +
                      entity +
                      "/" +
                      row.id,
                    { method: "DELETE" },
                  );
                  await load();
                } catch (e: any) {
                  setError(e.message);
                }
              }}
            >
              Delete
            </button>
          </article>
        ))}
      </div>
      <small className="prototype-footnote">
        This prototype uses Evolvyn workspace storage. The generated app
        includes its own accounts and database; it has not been deployed.
      </small>
    </section>
  );
}
