import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import PageHeader from "../../components/PageHeader";
import { SkeletonCards } from "../../components/Skeleton";
import { money, shortDate } from "../../format";

const RANGES = [7, 30, 90];

function DailySales({ days }) {
  const highest = Math.max(...days.map((day) => Number(day.total)), 1);
  const label = (day) => `${shortDate(day.day)}: ${money(day.total)} from ${day.count} sales`;
  return (
    <figure className="card flex flex-col gap-3 p-5">
      <figcaption className="text-lg font-bold">Sales per day</figcaption>
      <div className="flex h-48 items-end gap-[3px]" role="list" aria-label="Sales per day">
        {days.map((day) => (
          <div
            key={day.day}
            role="listitem"
            aria-label={label(day)}
            title={label(day)}
            className="group flex h-full min-w-0 flex-1 items-end"
          >
            <div
              className="w-full rounded-t-[4px] bg-brand transition-opacity group-hover:opacity-80"
              style={{
                height: `${Math.max((Number(day.total) / highest) * 100, day.count ? 2 : 0.5)}%`,
              }}
            />
          </div>
        ))}
      </div>
      <div className="flex justify-between text-xs text-muted">
        <span>{shortDate(days[0]?.day)}</span>
        <span>Highest day: {money(highest)}</span>
        <span>{shortDate(days.at(-1)?.day)}</span>
      </div>
    </figure>
  );
}

export default function ReportsPage() {
  const [days, setDays] = useState(7);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setReport(null);
    api(`/api/reports/summary?days=${days}`)
      .then((data) => !cancelled && setReport(data))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [days]);

  const kpis = report && [
    ["Sales", money(report.sales_total), `${report.sales_count} sales`],
    ["Average sale", money(report.average_sale), "per receipt"],
    ["Estimated profit", money(report.estimated_profit), "at today's cost prices"],
    ["Goods received", money(report.purchases_received_total), "purchase orders"],
    ["Stock value", money(report.stock_value), "at cost, right now"],
  ];

  return (
    <section className="flex flex-col gap-5">
      <PageHeader
        title="Reports"
        subtitle={
          report
            ? `${shortDate(report.date_from)} to ${shortDate(report.date_to)}`
            : "How the shop is doing."
        }
      >
        <div role="group" aria-label="Period" className="flex gap-2">
          {RANGES.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={days === value}
              onClick={() => setDays(value)}
              className="chip"
            >
              {value} days
            </button>
          ))}
        </div>
      </PageHeader>

      {error && (
        <p role="alert" className="rounded-lg bg-danger-soft p-3 text-sm text-danger">
          {error}
        </p>
      )}
      {!report && !error && <SkeletonCards count={3} />}

      {report && (
        <>
          <dl className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            {kpis.map(([label, value, note]) => (
              <div key={label} className="card flex flex-col gap-1 p-4">
                <dt className="text-xs tracking-wide text-muted uppercase">{label}</dt>
                <dd className="font-display text-xl font-bold" data-testid={`kpi-${label}`}>
                  {value}
                </dd>
                <dd className="text-xs text-muted">{note}</dd>
              </div>
            ))}
          </dl>

          <DailySales days={report.by_day} />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="card overflow-x-auto">
              <h2 className="p-4 pb-2 text-lg font-bold">Best sellers</h2>
              <table className="w-full text-left text-sm">
                <thead className="table-head">
                  <tr>
                    <th className="p-3">Product</th>
                    <th className="p-3 text-right">Sold</th>
                    <th className="p-3 text-right">Takings</th>
                  </tr>
                </thead>
                <tbody>
                  {report.top_products.length === 0 && (
                    <tr>
                      <td colSpan="3" className="p-3 text-muted">
                        No sales in this period.
                      </td>
                    </tr>
                  )}
                  {report.top_products.map((product) => (
                    <tr key={product.product_id} className="border-t border-line">
                      <td className="p-3">{product.name}</td>
                      <td className="p-3 text-right tabular-nums">{product.quantity}</td>
                      <td className="p-3 text-right tabular-nums">{money(product.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card overflow-x-auto">
              <h2 className="p-4 pb-2 text-lg font-bold">Needs reordering</h2>
              <ul className="flex flex-col">
                {report.low_stock.length === 0 && (
                  <li className="p-4 pt-0 text-sm text-muted">
                    Everything is above its reorder level.
                  </li>
                )}
                {report.low_stock.map((product) => (
                  <li
                    key={product.id}
                    className="flex items-center justify-between gap-3 border-t border-line p-3 text-sm"
                  >
                    <Link to={`/products/${product.id}`} className="link">
                      {product.name}
                    </Link>
                    <span
                      className={product.quantity === 0 ? "font-semibold text-danger" : "text-warn"}
                    >
                      {product.quantity} left · reorder at {product.reorder_level}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </>
      )}
    </section>
  );
}