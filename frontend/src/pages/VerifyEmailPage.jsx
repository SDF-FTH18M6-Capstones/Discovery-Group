import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api/client";

// Opened from the link in the verification email: /verify-email?token=...
export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [result, setResult] = useState(
    token ? { state: "checking" } : { state: "error", message: "This link is not valid." },
  );

  useEffect(() => {
    if (!token) return;
    api("/api/auth/verify-email", { method: "POST", body: { token }, auth: false })
      .then((data) => setResult({ state: "ok", message: data.message }))
      .catch((error) => setResult({ state: "error", message: error.message }));
  }, [token]);

  return (
    <section className="mx-auto flex max-w-sm flex-col gap-4 py-10">
      <h1 className="text-2xl font-bold">Verify your email</h1>
      {result.state === "checking" && <p>Checking your link…</p>}
      {result.state === "ok" && (
        <p role="status" className="rounded-lg bg-mint p-3 text-sm">
          {result.message}
        </p>
      )}
      {result.state === "error" && (
        <p role="alert" className="rounded-lg bg-orange-50 p-3 text-sm text-danger">
          {result.message}
        </p>
      )}
      <Link to="/login" className="text-brand-dark underline">
        Go to sign in
      </Link>
    </section>
  );
}