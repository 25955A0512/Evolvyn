import { useLocation, useNavigate } from "react-router-dom";
import { OAuthButtons } from "./OAuthSetup";
import { useEffect, useState } from "react";
export function AccountAccess({
  onAuthenticated,
}: {
  onAuthenticated: (organizationId: string) => void;
}) {
  const [providers, setProviders] = useState<any[]>([]);
  useEffect(() => {
    fetch("/api/auth/providers")
      .then((r) => (r.ok ? r.json() : []))
      .then(setProviders)
      .catch(() => {});
  }, []);
  const route=useLocation(),navigate=useNavigate();
  const [register, setRegisterState] = useState(route.pathname==="/signup");
  function setRegister(value:boolean){setRegisterState(value);navigate(value?"/signup":"/login");}
  useEffect(()=>{setRegisterState(route.pathname==="/signup");},[route.pathname]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <section className="account-access">
      <div className="account-tabs">
        <button
          className={!register ? "selected" : ""}
          onClick={() => setRegister(false)}
        >
          Sign in
        </button>
        <button
          className={register ? "selected" : ""}
          onClick={() => setRegister(true)}
        >
          Create account
        </button>
      </div>
      <OAuthButtons register={register} />
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          const data = Object.fromEntries(new FormData(e.currentTarget));
          try {
            const response = await fetch(
              "/api/auth/" + (register ? "register" : "login"),
              {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-Requested-With": "Evolvyn",
                },
                body: JSON.stringify(data),
              },
            );
            const body = await response.json();
            if (!response.ok)
              throw Error(
                typeof body.detail === "string"
                  ? body.detail
                  : "Check your email and password; use at least 12 password characters",
              );
            onAuthenticated(body.organization_id);
            if (["/login","/signup","/auth/callback"].includes(route.pathname)) navigate("/dashboard");
          } catch (e) {
            setError(String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {register && (
          <label>
            Workspace name
            <input
              name="name"
              required
              maxLength={100}
              autoComplete="organization"
            />
          </label>
        )}
        <label>
          Email
          <input type="email" name="email" required autoComplete="email" />
        </label>
        <label>
          Password
          <input
            type="password"
            name="password"
            required
            minLength={register ? 12 : 1}
            maxLength={128}
            autoComplete={register ? "new-password" : "current-password"}
          />
        </label>
        <button className="primary" disabled={busy}>
          {busy
            ? "Opening workspace…"
            : register
              ? "Create your workspace"
              : "Sign in"}
        </button>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </form>
    </section>
  );
}
