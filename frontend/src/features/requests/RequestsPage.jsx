import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import Pagination from "../../components/Pagination";
import { SkeletonCards } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { Avatar, EmptyState } from "../../components/ui";
import { requests } from "../../store";
import RequestForm from "./RequestForm";

export const STATUS_TABS = [
  { value: "", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

export const shortDate = (iso) =>
  iso
    ? new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })
    : "";

export function StatusTabs({ value, onChange }) {
  return (
    <div role="group" aria-label="Filter by status" className="seg self-start">
      {STATUS_TABS.map((tab) => (
        <button
          key={tab.value}
          type="button"
          aria-pressed={value === tab.value}
          onClick={() => onChange(tab.value)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export default function RequestsPage() {
  const dispatch = useDispatch();
  const list = useSelector((state) => state.requests);
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null); // null = closed, {} = new, request = edit
  const [notice, setNotice] = useState("");

  const params = { mine: true, status, page, per_page: 10 };
  const reload = () => dispatch(requests.fetchList(params));

  useEffect(() => {
    dispatch(requests.fetchList({ mine: true, status, page, per_page: 10 }));
  }, [dispatch, status, page]);

  // Optimistic: the card disappears at once; if the server refuses, it comes back
  // and the server's message is shown.
  const withdraw = async (request) => {
    const before = { items: list.items, count: list.count };
    dispatch(requests.actions.removeItem(request.id));
    const result = await dispatch(requests.deleteItem(request.id));
    if (requests.deleteItem.fulfilled.match(result)) {
      setNotice(`Request for ${request.item} withdrawn.`);
      reload();
    } else {
      dispatch(requests.actions.restoreItems(before));
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">My requests</h1>
          <p className="text-muted">
            Ask for supplies or equipment. A Procurement Manager approves or rejects each one.
          </p>
        </div>
        <button type="button" onClick={() => setEditing({})} className="btn-primary">
          New request
        </button>
      </div>

      {editing && (
        <RequestForm
          key={editing.id || "new"}
          request={editing.id ? editing : null}
          onCancel={() => setEditing(null)}
          onSaved={(saved) => {
            setEditing(null);
            setNotice(editing.id ? "Request updated." : `Request for ${saved.item} submitted.`);
            reload();
          }}
        />
      )}

      {notice && (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {notice}
        </p>
      )}
      {list.error && (
        <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {list.error}
        </p>
      )}

      <StatusTabs
        value={status}
        onChange={(value) => {
          setStatus(value);
          setPage(1);
        }}
      />

      <ul className="grid grid-cols-1 gap-4 xl:grid-cols-2" aria-busy={list.status === "loading"}>
        {list.status === "loading" && list.items.length === 0 && (
          <li>
            <SkeletonCards count={3} />
          </li>
        )}
        {list.status === "ready" && list.items.length === 0 && (
          <li className="panel xl:col-span-2">
            <EmptyState icon="inbox" title="No requests here yet">
              Ask for equipment or supplies with New request; procurement decides.
            </EmptyState>
          </li>
        )}
        {list.items.map((request) => (
          <li key={request.id} className="panel flex flex-col gap-4 p-5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <span className="font-display text-lg font-semibold">
                {request.item} × {request.quantity}
              </span>
              <StatusBadge value={request.status} />
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              <span className="code rounded-md bg-surface-2 px-1.5 py-0.5">
                REQ-{String(request.id).padStart(4, "0")}
              </span>
              <StatusBadge value={request.urgency} />
              <span>{shortDate(request.created_at)}</span>
            </div>
            <p className="border-l-2 border-saffron pl-3 text-sm text-ink-2">{request.reason}</p>
            {request.status !== "pending" && (
              <div className="flex items-start gap-3 rounded-xl bg-surface-2 p-3">
                <Avatar name={request.reviewer_name || "?"} size={28} />
                <span className="text-sm">
                  {request.reviewer_name}: “{request.review_comment || "No comment"}”
                </span>
              </div>
            )}
            {request.status === "pending" && (
              <div className="flex gap-1 border-t border-line pt-3 text-sm">
                <button
                  type="button"
                  onClick={() => setEditing(request)}
                  className="btn-ghost min-h-0 px-2.5 py-1.5"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => withdraw(request)}
                  className="btn-ghost min-h-0 px-2.5 py-1.5 hover:text-danger"
                >
                  Withdraw
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
      <Pagination
        standalone
        page={list.page}
        pages={list.pages}
        count={list.count}
        onChange={setPage}
      />
    </section>
  );
}