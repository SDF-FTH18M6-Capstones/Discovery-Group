import { useEffect, useState } from "react";

import { api } from "../../api/client";
import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { SkeletonRows } from "../../components/Skeleton";
import { EmptyState } from "../../components/ui";
import { fullDateTime } from "../../format";

const KINDS = [
  { value: "", label: "Everything" },
  { value: "user", label: "Users" },
  { value: "product", label: "Products" },
  { value: "request", label: "Requests" },
  { value: "purchase", label: "Purchases" },
  { value: "sale", label: "Sales" },
  { value: "asset", label: "Assets" },
  { value: "business", label: "Settings" },
  { value: "expense", label: "Expenses" },
];

const changeText = (changes) =>
  changes
    ? Object.entries(changes)
        .map(([key, [before, after]]) => `${key.replaceAll("_", " ")}: ${before ?? "—"} → ${after}`)
        .join("; ")
    : "";

export default function AuditPage() {
  const [kind, setKind] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    api(`/api/audit/?page=${page}&per_page=25${kind ? `&entity_type=${kind}` : ""}`)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [kind, page]);

  return (
    <section className="flex flex-col gap-6">
      <PageHeader
        title="Audit log"
        subtitle="Every role change, deactivation, edit, void and setting change, newest first."
      />
      {error && (
        <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {error}
        </p>
      )}
      <div role="group" aria-label="Show" className="seg flex-wrap self-start">
        {KINDS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={kind === option.value}
            onClick={() => {
              setKind(option.value);
              setPage(1);
            }}
          >
            {option.label}
          </button>
        ))}
      </div>
      <div className="panel relative overflow-x-auto">
        <table className="data-table w-full text-left text-sm">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3">Who</th>
              <th className="px-4 py-3">What</th>
              <th className="px-4 py-3">Change</th>
            </tr>
          </thead>
          <tbody>
            {data === null && !error && <SkeletonRows cols={4} />}
            {data?.results.map((entry) => (
              <tr key={entry.id} className="border-t border-line align-top">
                <td className="px-4 py-3 whitespace-nowrap text-muted">
                  {fullDateTime(entry.created_at)}
                </td>
                <td className="px-4 py-3">{entry.user_name || "System"}</td>
                <td className="px-4 py-3">{entry.summary}</td>
                <td className="px-4 py-3 text-muted">{changeText(entry.changes)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.results.length === 0 && <EmptyState icon="shield" title="Nothing recorded yet" />}
        {data && (
          <Pagination page={data.page} pages={data.pages} count={data.count} onChange={setPage} />
        )}
      </div>
    </section>
  );
}
