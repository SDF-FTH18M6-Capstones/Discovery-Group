import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { PROCUREMENT, STOCK_MANAGERS } from "../../auth/roles";
import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { SkeletonCards } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { money, shortDate } from "../../format";
import { purchases } from "../../store";
import PurchaseForm from "./PurchaseForm";

const TABS = [
  { value: "", label: "All" },
  { value: "ordered", label: "Ordered" },
  { value: "received", label: "Received" },
  { value: "cancelled", label: "Cancelled" },
];

export default function PurchasesPage() {
  const dispatch = useDispatch();
  const { hasRole } = useAuth();
  const canOrder = hasRole(...PROCUREMENT);
  const canReceive = hasRole(...STOCK_MANAGERS);
  const list = useSelector((state) => state.purchases);
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const params = { status, page, per_page: 10 };
  const reload = () => dispatch(purchases.fetchList(params));

  useEffect(() => {
    dispatch(purchases.fetchList({ status, page, per_page: 10 }));
  }, [dispatch, status, page]);

  const act = async (purchase, action) => {
    setBusyId(purchase.id);
    setError("");
    setNotice("");
    try {
      await api(`/api/purchases/${purchase.id}/${action}`, { method: "POST" });
      setNotice(
        action === "receive"
          ? `${purchase.reference} received. Stock updated.`
          : `${purchase.reference} cancelled.`,
      );
      reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        title="Purchases"
        subtitle="Orders to suppliers. Receiving an order adds its goods to stock."
      >
        {canOrder && !creating && (
          <button type="button" onClick={() => setCreating(true)} className="btn-primary">
            New purchase order
          </button>
        )}
      </PageHeader>

      {creating && (
        <PurchaseForm
          onCancel={() => setCreating(false)}
          onSaved={(saved) => {
            setCreating(false);
            setNotice(`${saved.reference} placed with ${saved.supplier_name}.`);
            reload();
          }}
        />
      )}

      {notice && (
        <p role="status" className="rounded-lg bg-mint p-3 text-sm">
          {notice}
        </p>
      )}
      {(error || list.error) && (
        <p role="alert" className="rounded-lg bg-danger-soft p-3 text-sm text-danger">
          {error || list.error}
        </p>
      )}

      <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            aria-pressed={status === tab.value}
            onClick={() => {
              setStatus(tab.value);
              setPage(1);
            }}
            className="chip"
          >
            {tab.label}
          </button>
        ))}
      </div>

      {list.status === "loading" && <SkeletonCards count={3} />}
      {list.status === "ready" && list.items.length === 0 && (
        <p className="card p-4 text-muted">No purchase orders here.</p>
      )}
      <ul className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        {list.status === "ready" &&
          list.items.map((purchase) => (
            <li key={purchase.id} className="card flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-display text-lg font-bold">{purchase.reference}</span>
                <StatusBadge value={purchase.status} />
              </div>
              <span className="text-sm text-muted">
                {purchase.supplier_name} · by {purchase.creator_name} ·{" "}
                {shortDate(purchase.created_at)}
              </span>
              <ul className="flex flex-col gap-1 rounded-lg bg-surface-2 p-3 text-sm">
                {purchase.items.map((line) => (
                  <li key={line.product_id} className="flex justify-between gap-3">
                    <span>
                      {line.quantity} × {line.product_name}
                    </span>
                    <span className="text-muted">{money(line.unit_cost)} each</span>
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">{money(purchase.total)}</span>
                {purchase.status === "ordered" && (
                  <div className="flex gap-2">
                    {canOrder && (
                      <button
                        type="button"
                        disabled={busyId === purchase.id}
                        onClick={() => act(purchase, "cancel")}
                        className="btn-danger"
                        aria-label={`Cancel ${purchase.reference}`}
                      >
                        Cancel order
                      </button>
                    )}
                    {canReceive && (
                      <button
                        type="button"
                        disabled={busyId === purchase.id}
                        onClick={() => act(purchase, "receive")}
                        className="btn-primary"
                        aria-label={`Receive ${purchase.reference}`}
                      >
                        Receive goods
                      </button>
                    )}
                  </div>
                )}
              </div>
            </li>
          ))}
      </ul>
      <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
    </section>
  );
}