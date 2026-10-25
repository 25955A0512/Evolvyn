import { useState } from "react";
import type { client } from "../api";
const fields = [
  ["objective", "Campaign objective"],
  ["channel", "Channel"],
  ["audience", "Audience"],
  ["consent_basis", "Consent / legal basis"],
  ["exclusions", "Audience exclusions"],
  ["copy", "Copy / creative brief"],
  ["cta", "Call to action"],
  ["destination", "Destination (HTTPS)"],
  ["timezone", "Schedule timezone (IANA)"],
  ["starts_at", "Start time (ISO with UTC offset)"],
  ["duration_days", "Duration (days)"],
  ["budget", "Budget cap"],
  ["currency", "Budget currency"],
  ["attribution_tags", "Attribution tags"],
  ["baseline", "Measured baseline / unknown"],
  ["success_metric", "Success metric"],
  ["guardrails", "Guardrails / frequency limit"],
  ["stop_conditions", "Stop conditions"],
];
export function GrowthCampaign({
  api,
  report,
  onSaved,
}: {
  api: ReturnType<typeof client>;
  report: any;
  onSaved: () => Promise<void>;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <form
      className="growth-campaign"
      onSubmit={async (e) => {
        e.preventDefault();
        const d = Object.fromEntries(new FormData(e.currentTarget));
        setBusy(true);
        setError("");
        try {
          await api.json(`/growth/reports/${report.id}/campaigns`, {
            method: "POST",
            body: JSON.stringify({
              ...d,
              duration_days: Number(d.duration_days),
              budget: d.budget,
            }),
          });
          await onSaved();
        } catch (e: any) {
          setError(e.message);
        } finally {
          setBusy(false);
        }
      }}
    >
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="growth-form-grid">
        {fields.map(([name, label]) => (
          <label key={name}>
            {label}
            {["copy", "guardrails", "stop_conditions"].includes(name) ? (
              <textarea
                name={name}
                required
                minLength={3}
                maxLength={name === "copy" ? 4000 : 1000}
              />
            ) : (
              <input
                name={name}
                required
                type={
                  ["duration_days", "budget"].includes(name)
                    ? "number"
                    : name === "destination"
                      ? "url"
                      : "text"
                }
                step={name === "budget" ? ".01" : undefined}
                min={
                  name === "budget"
                    ? 0
                    : name === "duration_days"
                      ? 1
                      : undefined
                }
                max={
                  name === "budget"
                    ? 1000000
                    : name === "duration_days"
                      ? 90
                      : undefined
                }
                maxLength={name === "destination" ? 2000 : 1000}
                placeholder={
                  name === "starts_at"
                    ? "2026-11-01T09:00:00+05:30"
                    : name === "timezone"
                      ? "Asia/Kolkata"
                      : name === "currency"
                        ? "INR"
                        : ""
                }
              />
            )}
          </label>
        ))}
      </div>
      <p>
        Saving creates an unapproved draft. Publishing is unavailable until a
        provider write adapter, authorized account and argument-bound approval
        are implemented and verified.
      </p>
      <button className="studio-primary" disabled={busy}>
        {busy ? "Saving draft…" : "Save campaign draft"}
      </button>
    </form>
  );
}
