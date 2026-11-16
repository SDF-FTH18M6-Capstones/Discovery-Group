import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import Pagination from "../../components/Pagination";
import StatusBadge from "../../components/StatusBadge";
import { requests } from "../../store";
import { StatusTabs, shortDate } from "./RequestsPage";

function DecisionPanel({ request, onDone, onClose }) {
  const { user, hasRole } = useAuth();
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const own = request.requester_id === user.id;
  const canDecide = hasRole("procurement") && !own && request.status === "pending";

  const decide = async (action) => {
    if (action === "reject" && !comment.trim()) {
      setError("Say why the request is rejected.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(`/api/requests/${request.id}/${action}`, {
        method: "POST",
        body: comment.trim() ? { comment: comment.trim() } : {},
      });
      onDone(`${request.item}: ${action === "approve" ? "approved" : "rejected"}.`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <aside
      aria-label={`Request ${request.id}`}
      className="flex flex-col gap-3 rounded-xl border border-line bg-white p-5"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-bold">
          {request.item} × {request.quantity}
        </h2>
        <StatusBadge value={request.urgency} />
      </div>
      <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-muted">Requested by</dt>
        <dd>{request.requester_name}</dd>
        <dt className="text-muted">Submitted</dt>
        <dd>{shortDate(request.created_at)}</dd>
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
          <label htmlFor="decision-comment" className="text-sm font-semibold">
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
            className="rounded-lg border border-line px-3 py-2"
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
              className="flex-1 rounded-lg border border-danger px-4 py-2 font-semibold text-danger"
            >
              Reject
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => decide("approve")}
              className="flex-1 rounded-lg bg-brand px-4 py-2 font-semibold text-white"
            >
              Approve
            </button>
          </div>
        </>
      )}
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
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    dispatch(requests.fetchList({ status, page, per_page: 10 }));
  }, [dispatch, status, page]);

  return (
    <section className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold">Approvals</h1>
        <p className="text-muted">Every staff request. Open one to approve or reject it.</p>
      </div>

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
          setSelected(null);
        }}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="relative min-w-0 overflow-x-auto rounded-xl border border-line bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-canvas text-muted">
              <tr>
                <th className="p-3">Item</th>
                <th className="p-3 text-right">Qty</th>
                <th className="p-3">Requested by</th>
                <th className="p-3">Urgency</th>
                <th className="p-3">Status</th>
                <th className="p-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.status === "ready" && list.items.length === 0 && (
                <tr>
                  <td colSpan="6" className="p-3 text-muted">
                    Nothing to show.
                  </td>
                </tr>
              )}
              {list.items.map((request) => (
                <tr
                  key={request.id}
                  className={`border-t border-line ${selected?.id === request.id ? "bg-mint" : ""}`}
                >
                  <td className="p-3 font-semibold">{request.item}</td>
                  <td className="p-3 text-right">{request.quantity}</td>
                  <td className="p-3">{request.requester_name}</td>
                  <td className="p-3">
                    <StatusBadge value={request.urgency} />
                  </td>
                  <td className="p-3">
                    <StatusBadge value={request.status} />
                  </td>
                  <td className="p-3">
                    <button
                      type="button"
                      onClick={() => setSelected(request)}
                      className="text-brand-dark"
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

        {selected && (
          <DecisionPanel
            key={selected.id}
            request={selected}
            onClose={() => setSelected(null)}
            onDone={(message) => {
              setNotice(message);
              setSelected(null);
              dispatch(requests.fetchList({ status, page, per_page: 10 }));
            }}
          />
        )}
      </div>
    </section>
  );
}
