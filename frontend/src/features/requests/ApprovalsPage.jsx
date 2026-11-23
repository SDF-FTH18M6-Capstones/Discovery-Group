import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import Icon from "../../components/Icon";
import Pagination from "../../components/Pagination";
import { SkeletonRows } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import Timeline from "../../components/Timeline";
import { Avatar } from "../../components/ui";
import { timeAgo } from "../../format";
import { requests } from "../../store";
import { reference, shortDate } from "./RequestsPage";

// US-17: the queue's filters. Awaiting and Urgent are sorted most urgent first, then oldest.
const QUEUES = [
  { key: "awaiting", label: "Awaiting", params: { status: "pending", sort: "urgency" } },
  {
    key: "urgent",
    label: "Urgent",
    params: { status: "pending", urgency: "urgent", sort: "urgency" },
  },
  { key: "today", label: "Decided today", params: { decided_today: "true" } },
  { key: "approved", label: "Approved", params: { status: "approved" } },
  { key: "all", label: "All", params: {} },
];

function DecisionPanel({ request, onStart, onDone, onClose }) {
  const { user, hasRole } = useAuth();
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const own = request.requester_id === user.id;
  const canDecide = hasRole("procurement") && !own && request.status === "pending";
  const canFulfil = request.status === "approved";

  const fulfil = async () => {
    setBusy(true);
    setError("");
    try {
      await api(`/api/requests/${request.id}/fulfil`, { method: "POST" });
      onDone(`${request.item}: marked fulfilled.`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  const decide = async (action) => {
    if (action === "reject" && !comment.trim()) {
      setError("Say why the request is rejected.");
      return;
    }
    setBusy(true);
    setError("");
    const undo = onStart(action === "approve" ? "approved" : "rejected");
    try {
      await api(`/api/requests/${request.id}/${action}`, {
        method: "POST",
        body: comment.trim() ? { comment: comment.trim() } : {},
      });
      onDone(`${request.item}: ${action === "approve" ? "approved" : "rejected"}.`);
    } catch (err) {
      undo();
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <aside
      aria-label={`Request ${request.id}`}
      className="panel flex flex-col gap-4 p-5 lg:sticky lg:top-24"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <span className="code text-muted">{reference(request)}</span>
          <h2 className="text-xl font-bold">
            {request.item} × {request.quantity}
          </h2>
        </div>
        <StatusBadge value={request.urgency} />
      </div>
      <div className="flex items-center gap-3 rounded-xl bg-surface-2 p-3">
        <Avatar name={request.requester_name} size={36} />
        <span className="text-sm">
          <span className="block font-medium">{request.requester_name}</span>
          <span className="text-muted">Asked on {shortDate(request.created_at)}</span>
        </span>
      </div>
      <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-2 text-sm">
        <dt className="text-muted">Reason</dt>
        <dd>{request.reason}</dd>
        {request.status !== "pending" && (
          <>
            <dt className="text-muted">Decided by</dt>
            <dd>
              {request.reviewer_name}: “{request.review_comment || "No comment"}”
            </dd>
          </>
        )}
      </dl>

      {canDecide && (
        <>
          <label
            htmlFor="decision-comment"
            className="border-t border-line pt-4 text-sm font-medium"
          >
            Comment
          </label>
          <textarea
            id="decision-comment"
            rows="3"
            value={comment}
            onChange={(event) => {
              setComment(event.target.value);
              setError("");
            }}
            className="input h-auto py-2"
          />
          <span className="text-xs text-muted">Required when rejecting.</span>
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => decide("reject")}
              className="btn-danger flex-1"
            >
              Reject
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => decide("approve")}
              className="flex-1 btn-primary"
            >
              Approve
            </button>
          </div>
        </>
      )}
      {canFulfil && (
        <div className="flex flex-col gap-2 border-t border-line pt-4">
          <p className="text-sm text-muted">
            Order it from a supplier, or hand it over from the store and mark it fulfilled.
          </p>
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Link to={`/purchases?new=1&request=${request.id}`} className="btn-primary">
              <Icon name="truck" size={16} /> Raise a purchase order
            </Link>
            <button type="button" disabled={busy} onClick={fulfil} className="btn-secondary">
              Mark fulfilled
            </button>
          </div>
        </div>
      )}
      <details className="border-t border-line pt-3">
        <summary className="cursor-pointer text-sm font-medium">Trace timeline</summary>
        <div className="-mx-5 mt-2">
          <Timeline url={`/api/requests/${request.id}/timeline`} />
        </div>
      </details>
      {request.status === "pending" && own && (
        <p className="text-sm text-muted">
          This is your own request: another Procurement Manager decides it.
        </p>
      )}
      {request.status === "pending" && !own && !hasRole("procurement") && (
        <p className="text-sm text-muted">Only a Procurement Manager can approve or reject.</p>
      )}
      <button type="button" onClick={onClose} className="self-start text-sm text-brand-dark">
        Close
      </button>
    </aside>
  );
}

export default function ApprovalsPage() {
  const dispatch = useDispatch();
  const list = useSelector((state) => state.requests);
  const [searchParams] = useSearchParams();
  const [queue, setQueue] = useState("awaiting");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [notice, setNotice] = useState("");
  const params = QUEUES.find((q) => q.key === queue).params;

  useEffect(() => {
    dispatch(requests.fetchList({ ...params, page, per_page: 10 }));
  }, [dispatch, queue, page]); // params follow `queue`

  // Opened from a notification: /approvals?open=12
  useEffect(() => {
    const id = searchParams.get("open");
    if (id)
      api(`/api/requests/${id}`)
        .then(setSelected)
        .catch(() => {});
  }, [searchParams]);

  return (
    <section className="flex flex-col gap-6">
      <div>
        <h1 className="page-title">Approvals</h1>
        <p className="text-muted">
          Most urgent first, then oldest. Open one to read the reason and decide.
        </p>
      </div>

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

      <div role="group" aria-label="Queue" className="seg self-start">
        {QUEUES.map((option) => (
          <button
            key={option.key}
            type="button"
            aria-pressed={queue === option.key}
            onClick={() => {
              setQueue(option.key);
              setPage(1);
              setSelected(null);
            }}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="panel relative min-w-0 overflow-x-auto">
          <table className="data-table w-full text-left text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-4 py-3">Request</th>
                <th className="px-4 py-3">Item</th>
                <th className="px-4 py-3 text-right">Qty</th>
                <th className="px-4 py-3">Requested by</th>
                <th className="px-4 py-3">Urgency</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Age</th>
                <th className="px-4 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.status === "loading" && <SkeletonRows cols={8} />}
              {list.status === "ready" && list.items.length === 0 && (
                <tr>
                  <td colSpan="8" className="px-4 py-3 text-muted">
                    Nothing to show.
                  </td>
                </tr>
              )}
              {list.items.map((request) => (
                <tr
                  key={request.id}
                  className={`border-t border-line ${selected?.id === request.id ? "bg-mint" : ""}`}
                >
                  <td className="code px-4 py-3 text-muted">{reference(request)}</td>
                  <td className="px-4 py-3 font-semibold">{request.item}</td>
                  <td className="px-4 py-3 text-right">{request.quantity}</td>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-2">
                      <Avatar name={request.requester_name} size={26} />
                      {request.requester_name}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge value={request.urgency} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge value={request.status} />
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-muted">
                    {timeAgo(request.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => setSelected(request)}
                      className="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                      aria-label={`Open request for ${request.item}`}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
        </div>

        {!selected && (
          <div className="rounded-2xl border border-dashed border-line-strong p-8 text-center text-sm text-muted">
            <Icon name="check" size={28} className="mx-auto mb-3 text-line-strong" />
            Open a request to read the reason and decide.
          </div>
        )}
        {selected && (
          <DecisionPanel
            key={selected.id}
            request={selected}
            onClose={() => setSelected(null)}
            onStart={(newStatus) => {
              // Optimistic: the row shows the decision straight away; undone if the server says no.
              const before = { items: list.items, count: list.count };
              dispatch(
                requests.actions.patchItem({ id: selected.id, changes: { status: newStatus } }),
              );
              return () => dispatch(requests.actions.restoreItems(before));
            }}
            onDone={(message) => {
              setNotice(message);
              setSelected(null);
              dispatch(requests.fetchList({ ...params, page, per_page: 10 }));
            }}
          />
        )}
      </div>
    </section>
  );
}
