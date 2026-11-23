import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useSearchParams } from "react-router-dom";

import { api } from "../../api/client";
import Icon from "../../components/Icon";
import Modal from "../../components/Modal";
import Pagination from "../../components/Pagination";
import { SkeletonCards } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import Timeline from "../../components/Timeline";
import { Avatar, EmptyState } from "../../components/ui";
import { requests } from "../../store";
import RequestForm from "./RequestForm";

export const STATUS_TABS = [
  { value: "", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

// US-15: Active (Pending, Approved) and Completed (Fulfilled, Rejected, Cancelled).
const MY_TABS = [
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
  { value: "", label: "All" },
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

export const reference = (request) =>
  request.reference || `REQ-${String(request.id).padStart(4, "0")}`;

function RequestDetails({ request }) {
  return (
    <div className="flex flex-col gap-5">
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line text-sm sm:grid-cols-4">
        {[
          ["Request", <span className="code">{reference(request)}</span>],
          ["Quantity", request.quantity],
          ["Urgency", <StatusBadge value={request.urgency} />],
          ["Asked on", shortDate(request.created_at)],
        ].map(([label, value]) => (
          <div key={label} className="flex flex-col gap-1 bg-surface p-3">
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-col gap-1.5">
        <h3 className="text-sm font-medium text-muted">Why you need it</h3>
        <p className="border-l-2 border-saffron pl-3 text-ink-2">{request.reason}</p>
      </div>
      {request.purchases?.length > 0 && (
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <Icon name="truck" size={16} className="text-brand-dark" />
          Ordered on{" "}
          {request.purchases.map((po) => (
            <span key={po.id} className="code rounded-md bg-surface-2 px-1.5 py-0.5">
              {po.reference} · {po.status.replaceAll("_", " ")}
            </span>
          ))}
        </p>
      )}
      {request.status === "pending" ? (
        <p className="flex items-center gap-2 rounded-xl bg-saffron-soft p-3 text-sm text-saffron-ink">
          <Icon name="clock" size={16} />
          Waiting for a Procurement Manager. You can still edit or cancel it.
        </p>
      ) : request.status === "cancelled" ? (
        <p className="rounded-xl bg-surface-2 p-3 text-sm text-muted">
          You cancelled this request.
        </p>
      ) : (
        <div className="flex flex-col gap-1.5">
          <h3 className="text-sm font-medium text-muted">Decision</h3>
          <div className="flex items-start gap-3 rounded-xl bg-surface-2 p-3">
            <Avatar name={request.reviewer_name || "?"} size={30} />
            <span className="text-sm">
              {request.reviewer_name}: “{request.review_comment || "No comment"}”
            </span>
          </div>
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        <h3 className="text-sm font-medium text-muted">Trace timeline</h3>
        <div className="overflow-hidden rounded-xl border border-line">
          <Timeline url={`/api/requests/${request.id}/timeline`} />
        </div>
      </div>
    </div>
  );
}

export default function RequestsPage() {
  const dispatch = useDispatch();
  const list = useSelector((state) => state.requests);
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState(searchParams.get("tab") ?? "active");
  const [page, setPage] = useState(1);
  const [popup, setPopup] = useState(searchParams.get("new") ? { mode: "new" } : null);
  const [confirming, setConfirming] = useState(false);
  const [notice, setNotice] = useState("");
  const [failure, setFailure] = useState("");

  useEffect(() => {
    if (searchParams.get("new")) setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  // Opened from a notification: /requests?open=12
  useEffect(() => {
    const id = searchParams.get("open");
    if (!id) return;
    api(`/api/requests/${id}`)
      .then((request) => setPopup({ mode: "view", request }))
      .catch(() => setNotice("That request could not be found."));
  }, [searchParams]);

  const open = (next) => {
    setConfirming(false);
    setPopup(next);
  };

  const params = { mine: true, tab, page, per_page: 10 };
  const reload = () => dispatch(requests.fetchList(params));

  useEffect(() => {
    dispatch(requests.fetchList({ mine: true, tab, page, per_page: 10 }));
  }, [dispatch, tab, page]);

  // US-16: cancelling keeps the request on record as Cancelled.
  const withdraw = async (request) => {
    setPopup(null);
    setNotice("");
    setFailure("");
    const before = { items: list.items, count: list.count };
    if (tab === "active") dispatch(requests.actions.removeItem(request.id));
    else dispatch(requests.actions.patchItem({ id: request.id, changes: { status: "cancelled" } }));
    try {
      await api(`/api/requests/${request.id}/cancel`, { method: "POST" });
      setNotice(`Request for ${request.item} cancelled.`);
      reload();
    } catch (error) {
      dispatch(requests.actions.restoreItems(before));
      setFailure(error.message);
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="flex flex-col gap-1.5">
          <h1 className="page-title">My requests</h1>
          <p className="text-muted">
            Ask for supplies or equipment. A Procurement Manager approves or rejects each one.
          </p>
        </div>
        <button type="button" onClick={() => open({ mode: "new" })} className="btn-primary">
          <Icon name="plus" size={16} />
          New request
        </button>
      </div>

      {notice && (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {notice}
        </p>
      )}
      {(failure || list.error) && (
        <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {failure || list.error}
        </p>
      )}

      <div role="group" aria-label="Show" className="seg self-start">
        {MY_TABS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={tab === option.value}
            onClick={() => {
              setTab(option.value);
              setPage(1);
            }}
          >
            {option.label}
          </button>
        ))}
      </div>

      <ul className="grid grid-cols-1 gap-4 xl:grid-cols-2" aria-busy={list.status === "loading"}>
        {list.status === "loading" && list.items.length === 0 && (
          <li>
            <SkeletonCards count={3} />
          </li>
        )}
        {list.status === "ready" && list.items.length === 0 && (
          <li className="panel xl:col-span-2">
            <EmptyState
              icon="inbox"
              title={tab === "completed" ? "Nothing completed yet" : "No requests here yet"}
            >
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
                {reference(request)}
              </span>
              <StatusBadge value={request.urgency} />
              <span>{shortDate(request.created_at)}</span>
            </div>
            <p className="line-clamp-2 border-l-2 border-saffron pl-3 text-sm text-ink-2">
              {request.reason}
            </p>
            <div className="mt-auto flex items-center justify-between gap-3 border-t border-line pt-3 text-sm">
              <span className="text-muted">
                {request.status === "pending"
                  ? "Waiting for a decision"
                  : request.status === "cancelled"
                    ? "Cancelled by you"
                    : `Decided by ${request.reviewer_name}`}
              </span>
              <button
                type="button"
                onClick={() => open({ mode: "view", request })}
                aria-label={`View request for ${request.item}`}
                className="btn-secondary min-h-0 px-3 py-1.5"
              >
                View
              </button>
            </div>
          </li>
        ))}
      </ul>
      {popup?.mode === "new" && (
        <Modal
          title="New request"
          subtitle="Say what you need and why. Procurement will approve or reject it."
          onClose={() => setPopup(null)}
        >
          <RequestForm
            bare
            request={null}
            onCancel={() => setPopup(null)}
            onSaved={(saved) => {
              setPopup(null);
              setNotice(`Request for ${saved.item} submitted.`);
              reload();
            }}
          />
        </Modal>
      )}

      {popup?.mode === "edit" && (
        <Modal
          title="Edit request"
          subtitle={reference(popup.request)}
          onClose={() => setPopup(null)}
        >
          <RequestForm
            bare
            key={popup.request.id}
            request={popup.request}
            onCancel={() => open({ mode: "view", request: popup.request })}
            onSaved={() => {
              setPopup(null);
              setNotice("Request updated.");
              reload();
            }}
          />
        </Modal>
      )}

      {popup?.mode === "view" && (
        <Modal
          title={`${popup.request.item} × ${popup.request.quantity}`}
          subtitle={<StatusBadge value={popup.request.status} />}
          onClose={() => setPopup(null)}
          footer={
            popup.request.status !== "pending" ? (
              <button type="button" onClick={() => setPopup(null)} className="btn-secondary">
                Close
              </button>
            ) : confirming ? (
              <>
                <span className="mr-auto text-sm font-medium">Cancel this request?</span>
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  className="btn-secondary"
                >
                  Keep it
                </button>
                <button
                  type="button"
                  onClick={() => withdraw(popup.request)}
                  className="btn-danger"
                >
                  Yes, cancel it
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => setConfirming(true)}
                  className="btn-danger mr-auto"
                >
                  Cancel request
                </button>
                <button type="button" onClick={() => setPopup(null)} className="btn-secondary">
                  Close
                </button>
                <button
                  type="button"
                  onClick={() => open({ mode: "edit", request: popup.request })}
                  className="btn-primary"
                >
                  Edit
                </button>
              </>
            )
          }
        >
          <RequestDetails request={popup.request} />
        </Modal>
      )}

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
