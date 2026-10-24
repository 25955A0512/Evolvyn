import { useEffect, useRef, useState } from "react";
import type { client } from "../api";
import { UiIcon } from "./UiIcon";
import { AccountTeam } from "./AccountTeam";

export type Preferences = {
  theme: "light" | "dark" | "system";
  text_size: "normal" | "large";
  sound: boolean;
  browser_notifications: boolean;
};
export const defaults: Preferences = {
  theme: "system",
  text_size: "normal",
  sound: false,
  browser_notifications: false,
};
export function useWorkspacePreferences(
  api: ReturnType<typeof client>,
  accountId?: string,
) {
  const [prefs, setPrefs] = useState<Preferences>(defaults),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  useEffect(() => {
    let live = true;
    setPrefs(defaults);
    setError("");
    setNotice("");
    setBusy(!!accountId);
    if (accountId)
      api
        .json("/account/preferences")
        .then((p) => {
          if (live) setPrefs(p);
        })
        .catch((e) => {
          if (live) setError(e.message);
        })
        .finally(() => {
          if (live) setBusy(false);
        });
    return () => {
      live = false;
    };
  }, [accountId]);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      document.documentElement.dataset.theme =
        prefs.theme === "system"
          ? media.matches
            ? "dark"
            : "light"
          : prefs.theme;
      document.documentElement.dataset.textSize = prefs.text_size;
    };
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [prefs.theme, prefs.text_size]);
  async function save(value: Preferences) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (!accountId)
        throw Error("Sign in with an account to save personal settings");
      const result = await api.json("/account/preferences", {
        method: "PUT",
        body: JSON.stringify(value),
      });
      setPrefs(result);
      setNotice("Preferences saved to your account.");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return { prefs, save, busy, error, notice };
}
export function playCompletionTone() {
  const audio = new AudioContext(),
    oscillator = audio.createOscillator(),
    gain = audio.createGain();
  oscillator.connect(gain);
  gain.connect(audio.destination);
  oscillator.frequency.value = 660;
  gain.gain.setValueAtTime(0.04, audio.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.25);
  oscillator.start();
  oscillator.stop(audio.currentTime + 0.25);
  oscillator.onended = () => {
    audio.close().catch(() => {});
  };
}
export function ProfileMenu({
  name,
  email,
  role,
  onSettings,
  onAccount,
  onConnections,
  onSignOut,
}: {
  name: string;
  email?: string;
  role: string;
  onSettings: () => void;
  onAccount: () => void;
  onConnections: () => void;
  onSignOut: () => void;
}) {
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const close = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node))
        ref.current.open = false;
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape" && ref.current?.open) {
        ref.current.open = false;
        ref.current.querySelector("summary")?.focus();
      }
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", key);
    };
  }, []);
  const actions = [
    { name: "Account & team", icon: "users", fn: onAccount },
    { name: "Settings", icon: "layout-dashboard", fn: onSettings },
    { name: "Connections & models", icon: "plug-connected", fn: onConnections },
    { name: "Sign out", icon: "external-link", fn: onSignOut },
  ];
  return (
    <details className="profile-menu" ref={ref}>
      <summary aria-label="Open account menu">
        <span className="profile-avatar">{name.slice(0, 1).toUpperCase()}</span>
        <span>
          <strong>{name}</strong>
          <small>{role} · Private workspace</small>
        </span>
        <UiIcon name="chevron-right" size={16} />
      </summary>
      <div className="profile-popover">
        <strong>{name}</strong>
        {email && <small>{email}</small>}
        <div className="profile-popover-actions">
          {actions.map((a) => (
            <button
              key={a.name}
              onClick={() => {
                if (ref.current) ref.current.open = false;
                a.fn();
              }}
            >
              <UiIcon name={a.icon} />
              {a.name}
            </button>
          ))}
        </div>
      </div>
    </details>
  );
}
export function WorkspaceSettings({
  api,
  initialTab = "general",
  preferences,
  onClose,
  onConnections,
  onVault,
  onAgents,
}: {
  api: ReturnType<typeof client>;
  initialTab?: "general" | "account";
  preferences: ReturnType<typeof useWorkspacePreferences>;
  onClose: () => void;
  onConnections: () => void;
  onVault: () => void;
  onAgents: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null),
    [tab, setTab] = useState(initialTab),
    [permissionError, setPermissionError] = useState("");
  const { prefs, save, busy, error, notice } = preferences;
  useEffect(() => {
    dialog.current?.showModal();
    return () => dialog.current?.close();
  }, []);
  const jump = (fn: () => void) => {
    onClose();
    fn();
  };
  return (
    <dialog
      className="workspace-settings-dialog"
      aria-label="Workspace settings"
      ref={dialog}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === dialog.current) onClose();
      }}
    >
      <div className="settings-shell">
        <nav className="settings-navigation">
          <div className="settings-brand">
            <span className="mark">e</span>
            <strong>Workspace settings</strong>
          </div>
          <small>ACCOUNT</small>
          <button
            className={tab === "account" ? "selected" : ""}
            onClick={() => setTab("account")}
          >
            <UiIcon name="users" />
            Account & team
          </button>
          <small>PREFERENCES</small>
          <button
            className={tab === "general" ? "selected" : ""}
            onClick={() => setTab("general")}
          >
            <UiIcon name="layout-dashboard" />
            General
          </button>
          <small>CAPABILITIES</small>
          <button onClick={() => jump(onConnections)}>
            <UiIcon name="plug-connected" />
            Connectors & tools
          </button>
          <button onClick={() => jump(onVault)}>
            <UiIcon name="key" />
            Keys & model routes
          </button>
          <button onClick={() => jump(onAgents)}>
            <UiIcon name="brain" />
            Agent skills
          </button>
        </nav>
        <main className="settings-main">
          <header>
            <h2>{tab === "general" ? "General" : "Account & team"}</h2>
            <button aria-label="Close settings" onClick={onClose}>
              ×
            </button>
          </header>
          <div className="settings-content">
            {tab === "account" ? (
              <AccountTeam api={api} />
            ) : (
              <>
                <h3>Appearance</h3>
                <p>Choose how Evolvyn looks on this account.</p>
                <label>
                  Theme
                  <select
                    aria-label="Workspace theme"
                    value={prefs.theme}
                    disabled={busy}
                    onChange={(e) =>
                      save({
                        ...prefs,
                        theme: e.target.value as Preferences["theme"],
                      })
                    }
                  >
                    <option value="light">Light</option>
                    <option value="dark">Dark</option>
                    <option value="system">Use device setting</option>
                  </select>
                </label>
                <label>
                  Text size
                  <select
                    aria-label="Workspace text size"
                    value={prefs.text_size}
                    disabled={busy}
                    onChange={(e) =>
                      save({
                        ...prefs,
                        text_size: e.target.value as Preferences["text_size"],
                      })
                    }
                  >
                    <option value="normal">Comfortable</option>
                    <option value="large">Larger</option>
                  </select>
                </label>
                <h3>When an agent is working</h3>
                <p>
                  You can write your next message while a task runs. It stays in
                  the composer until you send it after the active run finishes;
                  it never interrupts the worker or bypasses approval.
                </p>
                <h3>Completion preferences</h3>
                <label className="preference-toggle">
                  <span>
                    <strong>Browser notifications</strong>
                    <small>
                      Generic task status only. No document contents or business
                      metrics appear in a notification.
                    </small>
                  </span>
                  <input
                    type="checkbox"
                    aria-label="Browser completion notifications"
                    checked={prefs.browser_notifications}
                    disabled={busy}
                    onChange={async (e) => {
                      setPermissionError("");
                      if (!e.target.checked) {
                        await save({ ...prefs, browser_notifications: false });
                        return;
                      }
                      if (!("Notification" in window)) {
                        setPermissionError(
                          "This browser does not support notifications.",
                        );
                        return;
                      }
                      const permission = await Notification.requestPermission();
                      if (permission !== "granted") {
                        setPermissionError(
                          "Browser permission was not granted. Enable it in site settings before trying again.",
                        );
                        return;
                      }
                      await save({ ...prefs, browser_notifications: true });
                    }}
                  />
                </label>
                {prefs.browser_notifications &&
                  "Notification" in window &&
                  Notification.permission !== "granted" && (
                    <p role="status">
                      This account enables notifications, but this browser has
                      not granted permission. Toggle off and on to request it
                      here.
                    </p>
                  )}
                <label className="preference-toggle">
                  <span>
                    <strong>Completion sound</strong>
                    <small>
                      A short tone when a watched run finishes or needs your
                      approval.
                    </small>
                  </span>
                  <input
                    type="checkbox"
                    aria-label="Completion sound"
                    checked={prefs.sound}
                    disabled={busy}
                    onChange={(e) =>
                      save({ ...prefs, sound: e.target.checked })
                    }
                  />
                </label>
                <button
                  onClick={() => {
                    try {
                      playCompletionTone();
                    } catch {
                      setPermissionError(
                        "Audio is unavailable in this browser.",
                      );
                    }
                  }}
                >
                  Preview sound
                </button>
                {permissionError && (
                  <p role="alert" className="error">
                    {permissionError}
                  </p>
                )}
                {error && (
                  <p role="alert" className="error">
                    {error}
                  </p>
                )}
                {busy && <p role="status">Saving preferences…</p>}
                {notice && <p role="status">{notice}</p>}
              </>
            )}
          </div>
        </main>
      </div>
    </dialog>
  );
}
