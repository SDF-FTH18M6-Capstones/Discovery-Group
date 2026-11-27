import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { SkeletonRows } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { Avatar, EmptyState } from "../../components/ui";
import { PAYMENT_LABELS, dateTime, isoToday, money } from "../../format";
import { sales } from "../../store";
import Receipt from "./Receipt";

function VoidButton({ sale, onVoided }) {
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const today = new Date(sale.created_at).toDateString() === new Date().toDateString();
  if (sale.status === "voided" || !today) return null;

  const submit = async () => {
    if (reason.trim().length < 3) {
      setError("Say why the sale is voided.");
      return;
    }
    setBusy(true);
    try {
      onVoided(
        await api(`/api/sales/${sale.id}/void`, {
          method: "POST",
          body: { reason: reason.trim() },
        }),
      );
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  if (!asking) {
    return (
      <button type="button" className="btn-ghost text-danger" onClick={() => setAsking(true)}>
        Void sale
      </button>
    );
  }
  return (
    <div className="flex w-full flex-col gap-2 text-left">
      <label htmlFor="void-reason" className="text-sm font-medium">
        Why void {sale.receipt_number}? Stock goes back on the shelf.
      </label>
      <input
        id="void-reason"
        className="input"
        value={reason}
        onChange={(event) => {
          setReason(event.target.value);
          setError("");
        }}
      />
      {error && (
        <span role="alert" className="text-sm text-danger">
          {error}
        </span>
      )}
      <div className="flex gap-2">
        <button type="button" className="btn-danger" disabled={busy} onClick={submit}>
          Void
        </button>
        <button type="button" className="btn-secondary" onClick={() => setAsking(false)}>
          Keep
        </button>
      </div>
    </div>
  );
}

export default function SalesPage() {
  const dispatch = useDispatch();
  const { user, canDo } = useAuth();
  const canVoid = (sale) =>
    canDo("sales") && (user.role === "admin" || sale.attendant_id === user.id);
  const list = useSelector((state) => state.sales);
  const [params] = useSearchParams();
  const [payment, setPayment] = useState("");
  const [day, setDay] = useState(params.get("day") || "");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(null);

  const query = { payment_method: payment, day, search, page, per_page: 10 };
  useEffect(() => {
    dispatch(sales.fetchList({ payment_method: payment, day, search, page, per_page: 10 }));
  }, [dispatch, payment, day, search, page]);

  const pageTotal = list.items
    .filter((sale) => sale.status !== "voided")
    .reduce((sum, sale) => sum + Number(sale.total), 0);

  return (
    <section className="flex flex-col gap-6">
      <PageHeader title="Sales" subtitle="Every receipt from the till. Open one to print it again.">
        <Link to="/sales/new" className="btn-primary">
          <Icon name="sale" size={16} />
          New sale
        </Link>
      </PageHeader>

      {list.error && (
        <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {list.error}
        </p>
      )}

      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_23rem]">
        <div className="panel min-w-0">
          <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
            <div role="group" aria-label="Payment" className="seg">
              {[["", "All"], ...Object.entries(PAYMENT_LABELS)].map(([value, text]) => (
                <button
                  key={value || "all"}
                  type="button"
                  aria-pressed={payment === value}
                  onClick={() => {
                    setPayment(value);
                    setPage(1);
                  }}
                >
                  {text}
                </button>
              ))}
            </div>
            <label htmlFor="sales-day" className="sr-only">
              Day
            </label>
            <input
              id="sales-day"
              type="date"
              value={day}
              onChange={(event) => {
                setDay(event.target.value);
                setPage(1);
              }}
              max={isoToday()}
              className="input"
            />
            <label htmlFor="sales-search" className="sr-only">
              Receipt number
            </label>
            <input
              id="sales-search"
              type="search"
              placeholder="Receipt no., e.g. S-0012"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              className="input w-48"
            />
            {list.status === "ready" && list.items.length > 0 && (
              <p className="ml-auto text-sm text-muted">
                This page: <span className="figure text-base text-ink">{money(pageTotal)}</span>
              </p>
            )}
          </div>
          <div className="relative overflow-x-auto">
            <table className="data-table w-full text-left text-sm">
              <thead className="table-head">
                <tr>
                  <th className="px-5 py-3">Receipt</th>
                  <th className="px-3 py-3">When</th>
                  <th className="px-3 py-3">Served by</th>
                  <th className="px-3 py-3">Payment</th>
                  <th className="px-5 py-3 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {list.status === "loading" && <SkeletonRows cols={5} />}
                {list.status === "ready" &&
                  list.items.map((sale) => (
                    <tr
                      key={sale.id}
                      className={`border-t border-line ${open?.id === sale.id ? "bg-mint" : ""}`}
                    >
                      <td className="px-5 py-3">
                        <button
                          type="button"
                          onClick={() => setOpen(sale)}
                          className="code rounded-md bg-surface-2 px-2 py-1 font-semibold text-brand-dark hover:bg-mint"
                        >
                          {sale.receipt_number}
                        </button>
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap text-muted">
                        {dateTime(sale.created_at)}
                      </td>
                      <td className="px-3 py-3">
                        <span className="flex items-center gap-2">
                          <Avatar name={sale.attendant_name} size={26} />
                          {sale.attendant_name}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <StatusBadge value={sale.payment_method} />
                      </td>
                      <td
                        className={`px-5 py-3 text-right font-semibold ${sale.status === "voided" ? "text-muted line-through" : ""}`}
                      >
                        {money(sale.total)}
                        {sale.status === "voided" && (
                          <span className="ml-2 no-underline">
                            <StatusBadge value="voided" />
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
            {list.status === "ready" && list.items.length === 0 && (
              <EmptyState icon="receipt" title="No sales found">
                {payment || day
                  ? "Try another day or payment method."
                  : "Sales from the till appear here."}
              </EmptyState>
            )}
          </div>
          <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
        </div>

        <div className="xl:sticky xl:top-24">
          {open ? (
            <Receipt key={`${open.id}-${open.status}`} sale={open} onClose={() => setOpen(null)}>
              {canVoid(open) && (
                <VoidButton
                  sale={open}
                  onVoided={(voided) => {
                    setOpen(voided);
                    dispatch(sales.fetchList(query));
                  }}
                />
              )}
            </Receipt>
          ) : (
            <div className="rounded-2xl border border-dashed border-line-strong p-8 text-center text-sm text-muted">
              <Icon name="receipt" size={28} className="mx-auto mb-3 text-line-strong" />
              Choose a receipt number to see the receipt here.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
