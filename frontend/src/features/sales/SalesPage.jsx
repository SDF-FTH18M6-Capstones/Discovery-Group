import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Link } from "react-router-dom";

import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { SkeletonRows } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { Avatar, EmptyState } from "../../components/ui";
import { PAYMENT_LABELS, dateTime, money } from "../../format";
import { sales } from "../../store";
import Receipt from "./Receipt";

export default function SalesPage() {
  const dispatch = useDispatch();
  const list = useSelector((state) => state.sales);
  const [payment, setPayment] = useState("");
  const [day, setDay] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(null);

  useEffect(() => {
    dispatch(sales.fetchList({ payment_method: payment, day, page, per_page: 10 }));
  }, [dispatch, payment, day, page]);

  const pageTotal = list.items.reduce((sum, sale) => sum + Number(sale.total), 0);

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
              className="input"
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
                      <td className="px-5 py-3 text-right font-semibold">{money(sale.total)}</td>
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
            <Receipt key={open.id} sale={open} onClose={() => setOpen(null)} />
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