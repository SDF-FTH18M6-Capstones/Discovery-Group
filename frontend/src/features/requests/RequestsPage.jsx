import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import Pagination from "../../components/Pagination";
import { SkeletonCards } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
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
    <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
      {STATUS_TABS.map((tab) => (
        <button
          key={tab.value}
          type="button"
          aria-pressed={value === tab.value}
          onClick={() => onChange(tab.value)}
          className="chip"
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
  const [editing, setEditing] = useState(null); 
  const [notice, setNotice] = useState("");

  const params = { mine: true, status, page, per_page: 10 };
  const reload = () => dispatch(requests.fetchList(params));

  useEffect(() => {
    dispatch(requests.fetchList({ mine: true, status, page, per_page: 10 }));
  }, [dispatch, status, page]);

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
    <section className="flex flex-col gap-4">
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
        <p role="status" className="rounded-lg bg-mint p-3 text-sm">
          {notice}
        </p>
      )}
      {list.error && (
        <p role="alert" className="text-danger">
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

      <ul className="flex flex-col gap-3" aria-busy={list.status === "loading"}>
        {list.status === "loading" && list.items.length === 0 && (
          <li>
            <SkeletonCards count={3} />
          </li>
        )}
        {list.status === "ready" && list.items.length === 0 && (
          <li className="card p-4 text-muted">No requests here yet.</li>
        )}
        {list.items.map((request) => (
          <li key={request.id} className="card flex flex-col gap-2 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold">
                {request.item} × {request.quantity}
              </span>
              <StatusBadge value={request.status} />
            </div>
            <span className="text-sm text-muted">
              REQ-{String(request.id).padStart(4, "0")} · {request.urgency} ·{" "}
              {shortDate(request.created_at)} · “{request.reason}”
            </span>
            {request.status !== "pending" && (
              <span className="text-sm">
                {request.reviewer_name}: “{request.review_comment || "No comment"}”
              </span>
            )}
            {request.status === "pending" && (
              <div className="flex gap-4 text-sm">
                <button
                  type="button"
                  onClick={() => setEditing(request)}
                  className="text-brand-dark"
                >
                  Edit
                </button>
                <button type="button" onClick={() => withdraw(request)} className="text-danger">
                  Withdraw
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
      <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
    </section>
  );
}
