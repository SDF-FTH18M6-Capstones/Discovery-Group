import { useEffect, useState } from "react";

import { api } from "../api/client";
import { fullDateTime, whenShort } from "../format";
import { EmptyState } from "./ui";

const TONE = {
  Received: "bg-mint text-brand-dark",
  Sold: "bg-info-soft text-info",
  Adjusted: "bg-surface-2 text-ink-2",
  "Sale voided": "bg-saffron-soft text-saffron-ink",
  Approved: "bg-mint text-brand-dark",
  Fulfilled: "bg-mint text-brand-dark",
  Rejected: "bg-danger-soft text-danger",
  Cancelled: "bg-danger-soft text-danger",
  Assigned: "bg-info-soft text-info",
  Returned: "bg-mint text-brand-dark",
  Repair: "bg-saffron-soft text-saffron-ink",
  Retired: "bg-danger-soft text-danger",
};

// US-40 Trace Timeline: everything that happened to a record, newest first.
// `url` is a paginated timeline endpoint, e.g. /api/products/7/timeline.
export default function Timeline({ url, empty = "Nothing has happened yet." }) {
  const [entries, setEntries] = useState(null);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api(`${url}?page=${page}&per_page=15`)
      .then((data) => {
        if (cancelled) return;
        setEntries((current) =>
          page === 1 ? data.results : [...(current || []), ...data.results],
        );
        setPages(data.pages);
      })
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [url, page]);

  if (error) {
    return (
      <p role="alert" className="p-5 text-sm text-danger">
        {error}
      </p>
    );
  }
  if (entries === null) return <p className="p-5 text-sm text-muted">Loading history…</p>;
  if (entries.length === 0) return <EmptyState icon="clock" title={empty} />;

  return (
    <div className="flex flex-col">
      <ol aria-label="History" className="relative flex flex-col">
        {entries.map((entry, index) => (
          <li
            key={`${entry.at}-${index}`}
            className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 border-t border-line px-5 py-3 first:border-t-0 sm:grid-cols-[auto_minmax(0,1fr)_auto]"
          >
            <span
              className={`h-fit rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ${TONE[entry.action] || "bg-surface-2 text-ink-2"}`}
            >
              {entry.action}
            </span>
            <span className="min-w-0">
              {entry.change && <span className="figure mr-2 text-sm">{entry.change}</span>}
              {entry.summary && <span className="text-sm">{entry.summary}</span>}
              <span className="block text-xs text-muted">
                {entry.reference && <span className="code mr-2">{entry.reference}</span>}
                {entry.user_name || "System"}
              </span>
            </span>
            <time
              dateTime={entry.at}
              title={fullDateTime(entry.at)}
              className="col-start-2 text-xs whitespace-nowrap text-muted sm:col-start-3"
            >
              {whenShort(entry.at)}
            </time>
          </li>
        ))}
      </ol>
      {page < pages && (
        <button
          type="button"
          className="btn-ghost m-3 self-center"
          onClick={() => setPage((current) => current + 1)}
        >
          Show older
        </button>
      )}
    </div>
  );
}
