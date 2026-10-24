/** Locally served, MIT-licensed Tabler SVGs. No remote asset requests. */
export function UiIcon({
  name,
  size = 20,
  className = "",
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  return (
    <span
      className={"ui-icon " + className}
      style={{
        width: size,
        height: size,
        maskImage: `url(/assets/tabler/${name}.svg)`,
        WebkitMaskImage: `url(/assets/tabler/${name}.svg)`,
      }}
      aria-hidden="true"
    />
  );
}

export function WorkspaceArtwork({
  kind,
}: {
  kind: "build" | "growth" | "discuss";
}) {
  return (
    <div className={"workspace-art art-" + kind} aria-hidden="true">
      {kind === "build" ? (
        <>
          <div className="art-browser">
            <div className="art-browser-bar">
              <i />
              <i />
              <i />
              <span />
            </div>
            <div className="art-page">
              <span className="art-page-nav" />
              <div className="art-page-hero">
                <b />
                <span />
                <span />
                <i />
              </div>
              <div className="art-page-cards">
                <i />
                <i />
                <i />
              </div>
            </div>
          </div>
          <span className="art-float">
            <UiIcon name="code" size={20} />
          </span>
        </>
      ) : kind === "growth" ? (
        <>
          <div className="art-report">
            <span className="art-report-title" />
            <div className="art-bars">
              <i />
              <i />
              <i />
              <i />
              <i />
              <i />
              <i />
            </div>
            <div className="art-report-foot">
              <i />
              <i />
            </div>
          </div>
          <span className="art-float">
            <UiIcon name="chart-line" size={20} />
          </span>
        </>
      ) : (
        <>
          <span className="art-person">
            <UiIcon name="users" size={25} />
          </span>
          <div className="art-chat">
            <span />
            <span />
            <span />
          </div>
          <span className="art-float">
            <UiIcon name="message-circle" size={20} />
          </span>
        </>
      )}
    </div>
  );
}
