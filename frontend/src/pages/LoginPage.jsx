import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Field from "../components/Field";

function CodeStep({ challenge, onSignedIn, onStartAgain }) {
  const { verifyCode, resendCode } = useAuth();
  const [code, setCode] = useState("");
  const [current, setCurrent] = useState(challenge);
  const [wait, setWait] = useState(challenge.resend_after);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const input = useRef(null);

  useEffect(() => {
    input.current?.focus();
  }, []);

  useEffect(() => {
    if (wait <= 0) return undefined;
    const timer = setTimeout(() => setWait((seconds) => seconds - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);

  const submit = async (event) => {
    event.preventDefault();
    if (!/^\d{6}$/.test(code)) {
      setError("Enter the 6-digit code from the email.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await verifyCode(current.challenge_id, code);
      onSignedIn();
    } catch (err) {
      setBusy(false);
      setCode("");
      if (err.reason === "wrong_code") setError(err.message);
      else onStartAgain(err.message);
    }
  };

  const resend = async () => {
    setError("");
    try {
      const fresh = await resendCode(current.challenge_id);
      setCurrent(fresh);
      setWait(fresh.resend_after);
      setNotice(`We sent a new code to ${fresh.email_hint}. The old one no longer works.`);
    } catch (err) {
      if (err.status === 429) setError(err.message);
      else onStartAgain(err.message);
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="page-title">Check your email</h1>
        <p className="text-sm text-muted">
          We sent a 6-digit code to <strong>{current.email_hint}</strong>. It works once and expires
          in {Math.round(current.expires_in / 60)} minutes.
        </p>
      </div>
      {notice && (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {notice}
        </p>
      )}
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="login-code" className="text-sm font-medium text-ink-2">
            Sign-in code
          </label>
          <input
            id="login-code"
            ref={input}
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            placeholder="123456"
            value={code}
            onChange={(event) => {
              setCode(event.target.value.replace(/\D/g, "").slice(0, 6));
              setError("");
            }}
            aria-invalid={Boolean(error)}
            className={`input text-center font-mono text-2xl tracking-[0.5em] ${error ? "border-danger" : ""}`}
          />
          {error && (
            <span role="alert" className="text-sm text-danger">
              {error}
            </span>
          )}
        </div>
        <button type="submit" disabled={busy} className="btn-primary min-h-11">
          {busy ? "Checking…" : "Sign in"}
        </button>
      </form>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4 text-sm">
        <button type="button" className="link" onClick={() => onStartAgain("")}>
          Use a different account
        </button>
        {wait > 0 ? (
          <span className="text-muted" aria-live="polite">
            Send a new code in {wait}s
          </span>
        ) : (
          <button type="button" className="link" onClick={resend}>
            Send a new code
          </button>
        )}
      </div>
    </section>
  );
}

function ResendLink({ email }) {
  const [sent, setSent] = useState("");
  const send = async () => {
    try {
      const result = await api("/api/auth/resend-verification", {
        method: "POST",
        body: { email },
        auth: false,
      });
      setSent(result.message);
    } catch (err) {
      setSent(err.message);
    }
  };
  return sent ? (
    <span className="block pt-1 text-ink">{sent}</span>
  ) : (
    <button type="button" className="link block pt-1 font-semibold" onClick={send}>
      Send the link again
    </button>
  );
}

export default function LoginPage() {
  const { signIn, sessionExpired } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [values, setValues] = useState({ email: location.state?.email || "", password: "" });
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState(
    location.state?.message ||
      (sessionExpired ? "Your session has expired. Please sign in again." : ""),
  );
  const [formError, setFormError] = useState("");
  const [unverified, setUnverified] = useState(false);
  const [challenge, setChallenge] = useState(null);
  const [busy, setBusy] = useState(false);
  const goOn = () => navigate(location.state?.from || "/", { replace: true });

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const found = {};
    if (!/^\S+@\S+\.\S+$/.test(values.email)) found.email = "Enter your email address.";
    if (!values.password) found.password = "Enter your password.";
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    setMessage("");
    setFormError("");
    setUnverified(false);
    try {
      const result = await signIn(values.email, values.password);
      if (result.challenge) {
        setChallenge(result.challenge);
        setBusy(false);
      } else {
        goOn();
      }
    } catch (error) {
      setFormError(error.message);
      setUnverified(error.reason === "email_unverified");
      setBusy(false);
    }
  };

  if (challenge) {
    return (
      <CodeStep
        challenge={challenge}
        onSignedIn={goOn}
        onStartAgain={(reason) => {
          setChallenge(null);
          setValues((current) => ({ ...current, password: "" }));
          setFormError(reason);
        }}
      />
    );
  }

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="page-title">Sign in</h1>
        <p className="text-sm text-muted">Use the email and password you signed up with.</p>
      </div>
      {message && (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {message}
        </p>
      )}
      {formError && (
        <div role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {formError}
          {unverified && <ResendLink email={values.email} />}
        </div>
      )}
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <Field
          label="Email"
          name="email"
          type="email"
          autoComplete="email"
          value={values.email}
          onChange={handleChange}
          error={errors.email}
        />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={values.password}
          onChange={handleChange}
          error={errors.password}
        />
        <Link to="/forgot-password" className="link -mt-2 self-end text-sm">
          Forgot your password?
        </Link>
        <button type="submit" disabled={busy} className="btn-primary mt-2 min-h-11">
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="border-t border-line pt-4 text-center text-sm text-muted">
          New here?{" "}
          <Link to="/register" className="link">
            Join your team
          </Link>{" "}
          or{" "}
          <Link to="/register?start=1" className="link">
            start a business
          </Link>
        </p>
      </form>
    </section>
  );
}
