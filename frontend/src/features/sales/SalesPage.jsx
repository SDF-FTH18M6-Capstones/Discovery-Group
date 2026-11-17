import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Link } from "react-router-dom";

import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { SkeletonRows } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
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

  return (
    <section className="flex flex-col gap-4">
      <PageHeader title="Sales" subtitle="Every sale with its receipt.">
        <Link to="/sales/new" className="btn-primary">
          New sale
        </Link>
      </PageHeader>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="sales-payment" className="text-sm font-semibold">
            Payment
          </label>
          <select
            id="sales-payment"
            value={payment}
            onChange={(event) => {
              setPayment(event.target.value);
              setPage(1);
            }}
            className="input"
          >
            <option value="">All</option>
            {Object.entries(PAYMENT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="sales-day" className="text-sm font-semibold">
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
        </div>
      </div>

      {list.error && (
        <p role="alert" className="text-danger">
          {list.error}
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="card relative min-w-0 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="table-head">
              <tr>
                <th className="p-3">Receipt</th>
                <th className="p-3">When</th>
                <th className="p-3">Served by</th>
                <th className="p-3">Payment</th>
                <th className="p-3 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {list.status === "loading" && <SkeletonRows cols={5} />}
              {list.status === "ready" && list.items.length === 0 && (
                <tr>
                  <td colSpan="5" className="p-3 text-muted">
                    No sales found.
                  </td>
                </tr>
              )}
              {list.status === "ready" &&
                list.items.map((sale) => (
                  <tr
                    key={sale.id}
                    className={`border-t border-line ${open?.id === sale.id ? "bg-mint" : ""}`}
                  >
                    <td className="p-3">
                      <button type="button" onClick={() => setOpen(sale)} className="link">
                        {sale.receipt_number}
                      </button>
                    </td>
                    <td className="p-3 text-muted">{dateTime(sale.created_at)}</td>
                    <td className="p-3">{sale.attendant_name}</td>
                    <td className="p-3">
                      <StatusBadge value={sale.payment_method} />
                    </td>
                    <td className="p-3 text-right font-semibold">{money(sale.total)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
          <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
        </div>
        {open && <Receipt key={open.id} sale={open} onClose={() => setOpen(null)} />}
      </div>
    </section>
  );
}