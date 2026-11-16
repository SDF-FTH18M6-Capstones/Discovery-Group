// "My requests": everyone can ask for supplies or equipment, then edit or withdraw while pending.
import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import Pagination from "../../components/Pagination";
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
          className={`rounded-full px-3 py-1 text-sm ${value === tab.value ? "bg-evergreen text-white" : "border border-line bg-white"}`}
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

  const withdraw = async (request) => {
    const result = await dispatch(requests.deleteItem(request.id));
    if (requests.deleteItem.fulfilled.match(result)) {
      setNotice(`Request for ${request.item} withdrawn.`);
      reload();
    }
  };

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">My requests</h1>
          <p className="text-muted">
            Ask for supplies or equipment. A Procurement Manager approves or rejects each one.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEditing({})}
          className="rounded-lg bg-brand px-4 py-2 font-semibold text-white"
        >
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

      <ul className="flex flex-col gap-3">
        {list.status === "ready" && list.items.length === 0 && (
          <li className="rounded-xl border border-line bg-white p-4 text-muted">
            No requests here yet.
          </li>
        )}
        {list.items.map((request) => (
          <li
            key={request.id}
            className="flex flex-col gap-2 rounded-xl border border-line bg-white p-4"
          >
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
