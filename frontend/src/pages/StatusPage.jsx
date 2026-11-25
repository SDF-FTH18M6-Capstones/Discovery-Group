import { useEffect, useState } from "react";

import { api, API_URL } from "../api/client";

export default function StatusPage() {
  const [result, setResult] = useState({ state: "checking" });

  useEffect(() => {
    api("/api/health")
      .then((data) => setResult({ state: "ok", data }))
      .catch((error) => setResult({ state: "error", message: error.message }));
  }, []);

  return (
    <section className="flex max-w-lg flex-col gap-4">
      <h1 className="page-title">System status</h1>
      <p className="text-muted">
        API address: <span className="code">{API_URL}</span>
      </p>
      {result.state === "checking" && <p>Checking…</p>}
      {result.state === "ok" && (
        <p className="flex items-center gap-2 rounded-xl border border-brand/30 bg-mint p-4 font-semibold text-brand-dark">
          <span aria-hidden="true" className="size-2.5 animate-pulse rounded-full bg-brand" />
          API is up · database {result.data.database}
        </p>
      )}
      {result.state === "error" && (
        <p role="alert" className="rounded-xl bg-danger-soft p-4 text-danger">
          {result.message}
        </p>
      )}
    </section>
  );
}
