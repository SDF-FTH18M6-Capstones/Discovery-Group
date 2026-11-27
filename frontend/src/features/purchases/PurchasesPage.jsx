import { useEffect, useMemo, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useSearchParams } from "react-router-dom";

import { api, newIdempotencyKey } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import Icon from "../../components/Icon";
import Modal from "../../components/Modal";
import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { SkeletonCards } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { EmptyState } from "../../components/ui";
import { money, shortDate } from "../../format";
import { purchases } from "../../store";
import PurchaseForm from "./PurchaseForm";

const TABS = [
  { value: "", label: "All" },
  { value: "draft", label: "Drafts" },
  { value: "awaiting", label: "Awaiting delivery" },
  { value: "received", label: "Received" },
  { value: "cancelled", label: "Cancelled" },
];

function ReceiveDialog({ purchase, onClose, onDone }) {
  const key = useMemo(() => newIdempotencyKey(), []);
  const open = purchase.items.filter((line) => line.outstanding > 0);
  const [counts, setCounts] = useState(
    Object.fromEntries(open.map((line) => [line.id, String(line.outstanding)])),
  );
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const lines = open
      .map((line) => ({ item_id: line.id, quantity: Number(counts[line.id] || 0) }))
      .filter((line) => line.quantity > 0);
    const over = open.find((line) => Number(counts[line.id] || 0) > line.outstanding);
    if (over) {
      setError(`${over.product_name}: only ${over.outstanding} still to come.`);
      return;
    }
    if (open.some((line) => !/^\d*$/.test(counts[line.id] || ""))) {
      setError("Enter whole numbers.");
      return;
    }
    if (!lines.length) {
      setError("Enter how many of at least one product arrived.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const saved = await api(`/api/purchases/${purchase.id}/receive`, {
        method: "POST",
        body: { lines, idempotency_key: key, note: note.trim() || null },
      });
      const grn = saved.receipts[saved.receipts.length - 1];
      onDone(
        `${grn?.reference || "Delivery"} recorded for ${purchase.reference}: ${
          saved.status === "received" ? "order complete" : "still waiting for the rest"
        }. Stock updated.`,
      );
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <Modal
      title={`Receive ${purchase.reference}`}
      subtitle={`${purchase.supplier_name}. Enter what actually arrived.`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={submit}>
            {busy ? "Saving…" : "Confirm delivery"}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted">
            <tr>
              <th className="py-2">Product</th>
              <th className="py-2 text-right">Ordered</th>
              <th className="py-2 text-right">Still to come</th>
              <th className="py-2 text-right">Arrived now</th>
            </tr>
          </thead>
          <tbody>
            {open.map((line) => (
              <tr key={line.id} className="border-t border-line">
                <td className="py-2 font-medium">{line.product_name}</td>
                <td className="py-2 text-right text-muted">{line.quantity}</td>
                <td className="py-2 text-right">{line.outstanding}</td>
                <td className="py-2 text-right">
                  <label htmlFor={`arrived-${line.id}`} className="sr-only">
                    {line.product_name} arrived
                  </label>
                  <input
                    id={`arrived-${line.id}`}
                    type="number"
                    min="0"
                    max={line.outstanding}
                    value={counts[line.id]}
                    onChange={(event) =>
                      setCounts((current) => ({ ...current, [line.id]: event.target.value }))
                    }
                    className="input ml-auto w-24 text-right"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="font-medium text-ink-2">Delivery note (optional)</span>
          <input
            className="input"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="e.g. Driver: Peter, delivery note 4471"
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}

function CancelDialog({ purchase, onClose, onDone }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (reason.trim().length < 3) {
      setError("Say why the order is cancelled.");
      return;
    }
    setBusy(true);
    try {
      await api(`/api/purchases/${purchase.id}/cancel`, {
        method: "POST",
        body: { reason: reason.trim() },
      });
      onDone(`${purchase.reference} cancelled.`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <Modal
      size="sm"
      title={`Cancel ${purchase.reference}?`}
      subtitle="It stops showing as awaiting delivery. The reason is kept."
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Keep the order
          </button>
          <button type="button" className="btn-danger" disabled={busy} onClick={submit}>
            Cancel order
          </button>
        </>
      }
    >
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium text-ink-2">Reason</span>
        <textarea
          rows={3}
          className="input h-auto py-2"
          value={reason}
          onChange={(event) => {
            setReason(event.target.value);
            setError("");
          }}
        />
      </label>
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </Modal>
  );
}

export default function PurchasesPage() {
  const dispatch = useDispatch();
  const { canDo } = useAuth();
  const canOrder = canDo("procurement");
  const canReceive = canDo("inventory");
  const list = useSelector((state) => state.purchases);
  const [searchParams, setSearchParams] = useSearchParams();
  const [status, setStatus] = useState(searchParams.get("status") || "");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [form, setForm] = useState(
    searchParams.get("new") ? { mode: "new", requestId: searchParams.get("request") } : null,
  );
  const [dialog, setDialog] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    if (searchParams.get("new")) setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  const params = { status, search, page, per_page: 10 };
  const reload = () => dispatch(purchases.fetchList(params));

  useEffect(() => {
    dispatch(purchases.fetchList({ status, search, page, per_page: 10 }));
  }, [dispatch, status, search, page]);

  const confirm = async (purchase) => {
    setBusyId(purchase.id);
    setError("");
    setNotice("");
    try {
      await api(`/api/purchases/${purchase.id}/confirm`, { method: "POST" });
      setNotice(`${purchase.reference} placed with ${purchase.supplier_name}.`);
      reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const finished = (message) => {
    setDialog(null);
    setError("");
    setNotice(message);
    reload();
  };

  return (
    <section className="flex flex-col gap-6">
      <PageHeader
        title="Purchases"
        subtitle="Orders to suppliers. Goods enter stock only when a delivery is received."
      >
        {canOrder && !form && (
          <button type="button" onClick={() => setForm({ mode: "new" })} className="btn-primary">
            <Icon name="plus" size={16} />
            New purchase order
          </button>
        )}
      </PageHeader>

      {form && (
        <PurchaseForm
          key={form.purchase?.id || "new"}
          purchase={form.mode === "edit" ? form.purchase : null}
          requestId={form.requestId}
          onCancel={() => setForm(null)}
          onSaved={(saved) => {
            setForm(null);
            setNotice(
              saved.status === "draft"
                ? `${saved.reference} saved as a draft.`
                : `${saved.reference} placed with ${saved.supplier_name}.`,
            );
            reload();
          }}
        />
      )}

      {notice && (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {notice}
        </p>
      )}
      {(error || list.error) && (
        <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {error || list.error}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Filter by status" className="seg flex-wrap">
          {TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              aria-pressed={status === tab.value}
              onClick={() => {
                setStatus(tab.value);
                setPage(1);
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <label htmlFor="po-search" className="sr-only">
          Find an order by number
        </label>
        <input
          id="po-search"
          type="search"
          placeholder="PO number, e.g. PO-0012"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          className="input w-56"
        />
      </div>

      {list.status === "loading" && <SkeletonCards count={3} />}
      {list.status === "ready" && list.items.length === 0 && (
        <div className="panel">
          <EmptyState icon="truck" title="No purchase orders here">
            {canOrder
              ? "Place an order with a supplier to restock."
              : "Orders placed by procurement appear here."}
          </EmptyState>
        </div>
      )}
      <ul className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        {list.status === "ready" &&
          list.items.map((purchase) => {
            const awaiting = ["ordered", "partially_received"].includes(purchase.status);
            const cancellable =
              purchase.status === "draft" ||
              (purchase.status === "ordered" &&
                purchase.items.every((line) => !line.received_quantity));
            return (
              <li key={purchase.id} className="panel flex flex-col">
                <div className="flex flex-wrap items-start justify-between gap-3 p-5 pb-4">
                  <div className="flex items-center gap-3">
                    <span className="grid size-11 place-items-center rounded-xl bg-surface-2 text-brand-dark">
                      <Icon name="truck" />
                    </span>
                    <span className="flex flex-col">
                      <span className="code text-sm font-semibold">{purchase.reference}</span>
                      <span className="font-display text-lg font-semibold">
                        {purchase.supplier_name}
                      </span>
                    </span>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <StatusBadge value={purchase.status} />
                    {purchase.source === "low_stock" && (
                      <span className="rounded-full bg-warn-soft px-2 py-0.5 text-xs font-semibold text-warn">
                        Auto: low stock
                      </span>
                    )}
                    {purchase.request_reference && (
                      <span className="code text-xs text-muted">
                        For {purchase.request_reference}
                      </span>
                    )}
                  </div>
                </div>
                <table className="mx-5 text-sm">
                  <thead className="text-left text-xs text-muted">
                    <tr>
                      <th className="pb-1 font-normal">Product</th>
                      <th className="pb-1 text-right font-normal">Received</th>
                      <th className="pb-1 text-right font-normal">Unit cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {purchase.items.map((line) => (
                      <tr key={line.id} className="border-t border-dashed border-line-strong">
                        <td className="py-2">{line.product_name}</td>
                        <td
                          className={`py-2 text-right tabular ${line.outstanding && purchase.status !== "draft" && purchase.status !== "cancelled" ? "text-saffron-ink" : "text-muted"}`}
                        >
                          {line.received_quantity} / {line.quantity}
                        </td>
                        <td className="w-28 py-2 text-right">{money(line.unit_cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="flex flex-col gap-1 px-5 pt-3 text-xs text-muted">
                  <span>
                    {purchase.source !== "manual" && purchase.status === "draft"
                      ? "Prepared automatically"
                      : `${purchase.status === "draft" ? "Drafted" : "Ordered"} by ${purchase.creator_name}`}{" "}
                    on {shortDate(purchase.ordered_at || purchase.created_at)}
                  </span>
                  {purchase.receipts?.map((grn) => (
                    <span key={grn.id}>
                      <span className="code text-ink-2">{grn.reference}</span> received by{" "}
                      {grn.received_by_name} on {shortDate(grn.created_at)}:{" "}
                      {grn.items.map((i) => `${i.quantity} ${i.product_name}`).join(", ")}
                    </span>
                  ))}
                  {purchase.cancel_reason && (
                    <span className="text-danger">Cancelled: {purchase.cancel_reason}</span>
                  )}
                  {purchase.notes && <span>Note: {purchase.notes}</span>}
                </div>
                <span className="h-4" aria-hidden="true" />
                <div className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface-2 px-5 py-3">
                  <span className="flex items-baseline gap-2">
                    <span className="text-sm text-muted">Total</span>
                    <span className="figure text-xl">{money(purchase.total)}</span>
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {canOrder && cancellable && (
                      <button
                        type="button"
                        disabled={busyId === purchase.id}
                        onClick={() => setDialog({ kind: "cancel", purchase })}
                        className="btn-ghost text-danger"
                        aria-label={`Cancel ${purchase.reference}`}
                      >
                        Cancel
                      </button>
                    )}
                    {canOrder && purchase.status === "draft" && (
                      <>
                        <button
                          type="button"
                          onClick={() => setForm({ mode: "edit", purchase })}
                          className="btn-secondary"
                          aria-label={`Edit ${purchase.reference}`}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          disabled={busyId === purchase.id}
                          onClick={() => confirm(purchase)}
                          className="btn-primary"
                          aria-label={`Place ${purchase.reference}`}
                        >
                          Place order
                        </button>
                      </>
                    )}
                    {canReceive && awaiting && (
                      <button
                        type="button"
                        onClick={() => setDialog({ kind: "receive", purchase })}
                        className="btn-primary"
                        aria-label={`Receive ${purchase.reference}`}
                      >
                        Receive goods
                      </button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
      </ul>
      <Pagination
        standalone
        page={list.page}
        pages={list.pages}
        count={list.count}
        onChange={setPage}
      />

      {dialog?.kind === "receive" && (
        <ReceiveDialog
          purchase={dialog.purchase}
          onClose={() => setDialog(null)}
          onDone={finished}
        />
      )}
      {dialog?.kind === "cancel" && (
        <CancelDialog
          purchase={dialog.purchase}
          onClose={() => setDialog(null)}
          onDone={finished}
        />
      )}
    </section>
  );
}
