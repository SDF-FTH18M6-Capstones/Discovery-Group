import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import PageHeader from "../../components/PageHeader";
import { SkeletonCards } from "../../components/Skeleton";
import { BarChart, EmptyState, Panel, StatStrip, StockMeter } from "../../components/ui";
import { money, shortDate } from "../../format";

const RANGES = [7, 30, 90];

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

  const best = report?.top_products || [];
  const bestTotal = Math.max(...best.map((p) => Number(p.total)), 1);
  const profitShare =
    report && Number(report.sales_total)
      ? Math.round((Number(report.estimated_profit) / Number(report.sales_total)) * 100)
      : 0;

  return (
    <section className="flex flex-col gap-6">
      <PageHeader
        title="Reports"
        subtitle={
          report
            ? `From ${shortDate(report.date_from)} to ${shortDate(report.date_to)}.`
            : "How the shop is doing."
        }
      >
        <div role="group" aria-label="Period" className="seg">
          {RANGES.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={days === value}
              onClick={() => setDays(value)}
            >
              {value} days
            </button>
          ))}
        </div>
      </PageHeader>

      {error && (
        <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {error}
        </p>
      )}
      {!report && !error && <SkeletonCards count={3} />}

      {report && (
        <>
          <StatStrip
            items={[
              {
                label: "Sales",
                value: money(report.sales_total),
                hint: `${report.sales_count} receipts`,
                icon: "receipt",
                tone: "brand",
                testId: "kpi-Sales",
              },
              {
                label: "Average sale",
                value: money(report.average_sale),
                hint: "per receipt",
                icon: "cash",
                tone: "muted",
                testId: "kpi-Average sale",
              },
              {
                label: "Estimated profit",
                value: money(report.estimated_profit),
                hint: `${profitShare}% of sales, at today's cost prices`,
                icon: "up",
                tone: "brand",
                testId: "kpi-Estimated profit",
              },
              {
                label: "Goods received",
                value: money(report.purchases_received_total),
                hint: "from purchase orders",
                icon: "truck",
                tone: "info",
                testId: "kpi-Goods received",
              },
              {
                label: "Stock value",
                value: money(report.stock_value),
                hint: "at cost, right now",
                icon: "box",
                tone: "saffron",
                testId: "kpi-Stock value",
              },
            ]}
          />

          <Panel
            title="Sales per day"
            subtitle="Hover or tab through the bars for each day"
            bodyClassName="p-5"
          >
            <BarChart
              data={report.by_day.map((day) => ({
                label: shortDate(day.day),
                value: Number(day.total),
                detail: `${day.count} sales`,
              }))}
              format={money}
              label={`Sales per day, last ${days} days`}
              height={260}
            />
          </Panel>

          <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
            <Panel title="Best sellers" subtitle="By takings in this period">
              {best.length === 0 ? (
                <EmptyState icon="chart" title="No sales in this period" />
              ) : (
                <table className="data-table w-full text-left text-sm">
                  <thead className="table-head">
                    <tr>
                      <th className="px-5 py-3">Product</th>
                      <th className="px-3 py-3 text-right">Sold</th>
                      <th className="px-5 py-3 text-right">Takings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {best.map((product) => (
                      <tr key={product.product_id} className="border-t border-line">
                        <td className="px-5 py-3">
                          <span className="font-medium">{product.name}</span>
                          <span className="meter mt-2 block w-full max-w-56" aria-hidden="true">
                            <span
                              className="bg-brand"
                              style={{ width: `${(Number(product.total) / bestTotal) * 100}%` }}
                            />
                          </span>
                        </td>
                        <td className="px-3 py-3 text-right">{product.quantity}</td>
                        <td className="px-5 py-3 text-right font-semibold">
                          {money(product.total)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>
            <Panel title="Needs reordering" subtitle="At or below the reorder level">
              {report.low_stock.length === 0 ? (
                <EmptyState icon="box" title="Everything is above its reorder level" />
              ) : (
                <ul className="divide-y divide-line">
                  {report.low_stock.map((product) => (
                    <li key={product.id} className="flex items-center gap-4 px-5 py-3 text-sm">
                      <Link
                        to={`/products/${product.id}`}
                        className="min-w-0 flex-1 truncate font-medium hover:underline"
                      >
                        {product.name}
                      </Link>
                      <StockMeter quantity={product.quantity} reorder={product.reorder_level} />
                      <span
                        className={`w-28 text-right ${product.quantity === 0 ? "font-semibold text-danger" : "text-saffron-ink"}`}
                      >
                        {product.quantity} of {product.reorder_level}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </>
      )}
    </section>
  );
}