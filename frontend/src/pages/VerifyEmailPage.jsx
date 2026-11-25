import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import Field from "../components/Field";

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [state, setState] = useState(token ? "checking" : "invalid");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState("");
  const started = useRef(false);

  useEffect(() => {
    // A link works once, so never send it twice (React runs effects twice in development).
    if (!token || started.current) return;
    started.current = true;
    api("/api/auth/verify-email", { method: "POST", body: { token }, auth: false })
      .then((result) => {
        setMessage(result.message);
        setState("done");
      })
      .catch((err) => {
        setMessage(err.message);
        setState("invalid");
      });
  }, [token]);

  const resend = async (event) => {
    event.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email)) return;
    const result = await api("/api/auth/resend-verification", {
      method: "POST",
      body: { email },
      auth: false,
    }).catch((err) => ({ message: err.message }));
    setSent(result.message);
  };

  if (state === "checking") {
    return (
      <section className="flex flex-col gap-4">
        <h1 className="page-title">Confirming your email…</h1>
      </section>
    );
  }

  if (state === "done") {
    return (
      <section className="flex flex-col gap-6">
        <h1 className="page-title">Email confirmed</h1>
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {message}
        </p>
        <Link to="/login" className="btn-primary min-h-11">
          Sign in
        </Link>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="page-title">This link did not work</h1>
        <p className="text-sm text-muted">
          {message || "Open the link from the email exactly as it was sent."} Links work once and
          expire after 24 hours.
        </p>
      </div>
      {sent ? (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {sent}
        </p>
      ) : (
        <form onSubmit={resend} noValidate className="flex flex-col gap-4">
          <Field
            label="Your email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <button type="submit" className="btn-primary min-h-11">
            Send a new link
          </button>
        </form>
      )}
      <p className="border-t border-line pt-4 text-center text-sm">
        <Link to="/login" className="link">
          Back to sign in
        </Link>
      </p>
    </section>
  );
}
