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
    <section className="flex max-w-lg flex-col gap-3">
      <h1 className="page-title">System status</h1>
      <p className="text-muted">API address: {API_URL}</p>
      {result.state === "checking" && <p>Checking…</p>}
      {result.state === "ok" && (
        <p className="rounded-lg bg-mint p-3 font-semibold text-brand-dark">
          API is up · database {result.data.database}
        </p>
      )}
      {result.state === "error" && (
        <p role="alert" className="rounded-lg bg-danger-soft p-3 text-danger">
          {result.message}
        </p>
      )}
    </section>
  );
}
