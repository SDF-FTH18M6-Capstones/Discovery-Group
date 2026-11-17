import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { PROCUREMENT, STOCK_MANAGERS } from "../../auth/roles";
import Icon from "../../components/Icon";
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
    <section className="flex flex-col gap-6">
      <PageHeader
        title="Purchases"
        subtitle="Orders to suppliers. Receiving an order adds its goods to stock."
      >
        {canOrder && !creating && (
          <button type="button" onClick={() => setCreating(true)} className="btn-primary">
            <Icon name="plus" size={16} />
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
        <div role="group" aria-label="Filter by status" className="seg">
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
        {list.status === "ready" && (
          <p className="text-sm text-muted">
            {list.count} {list.count === 1 ? "order" : "orders"}
          </p>
        )}
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
          list.items.map((purchase) => (
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
                <StatusBadge value={purchase.status} />
              </div>
              <table className="mx-5 text-sm">
                <thead className="sr-only">
                  <tr>
                    <th>Product</th>
                    <th>Quantity</th>
                    <th>Unit cost</th>
                  </tr>
                </thead>
                <tbody>
                  {purchase.items.map((line) => (
                    <tr key={line.product_id} className="border-t border-dashed border-line-strong">
                      <td className="py-2">{line.product_name}</td>
                      <td className="py-2 text-right text-muted">{line.quantity} ×</td>
                      <td className="w-28 py-2 text-right">{money(line.unit_cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="px-5 pt-3 text-xs text-muted">
                Ordered by {purchase.creator_name} on {shortDate(purchase.created_at)}
              </p>
              <span className="h-4" aria-hidden="true" />
              <div className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface-2 px-5 py-3">
                <span className="flex items-baseline gap-2">
                  <span className="text-sm text-muted">Total</span>
                  <span className="figure text-xl">{money(purchase.total)}</span>
                </span>
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