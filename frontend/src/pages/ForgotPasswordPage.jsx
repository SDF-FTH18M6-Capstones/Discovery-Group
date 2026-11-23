import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import Field from "../components/Field";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [sent, setSent] = useState("");
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email)) {
      setError("Enter your email address.");
      return;
    }
    setBusy(true);
    try {
      const result = await api("/api/auth/forgot-password", {
        method: "POST",
        body: { email },
        auth: false,
      });
      setSent(result.message);
    } catch (problem) {
      setError(problem.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="page-title">Reset your password</h1>
        <p className="text-sm text-muted">
          Enter your email and we will send a link to choose a new password. The link works once,
          for one hour.
        </p>
      </div>
      {sent ? (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {sent}
        </p>
      ) : (
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          <Field
            label="Email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              setError("");
            }}
            error={error}
          />
          <button type="submit" disabled={busy} className="btn-primary min-h-11">
            {busy ? "Sending…" : "Send the link"}
          </button>
        </form>
      )}
      <p className="border-t border-line pt-4 text-center text-sm text-muted">
        <Link to="/login" className="link">
          Back to sign in
        </Link>
      </p>
    </section>
  );
}
