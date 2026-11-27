import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, download } from "../../api/client";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import { SkeletonCards } from "../../components/Skeleton";
import { BarChart, EmptyState, Panel, StatStrip, StockMeter } from "../../components/ui";
import { saveCsv } from "../../csv";
import { currencyCode, isoToday, money, shortDate } from "../../format";

const RANGES = [
  { key: "today", label: "Today" },
  { key: "7", label: "7 days" },
  { key: "month", label: "This month" },
  { key: "30", label: "30 days" },
  { key: "custom", label: "Custom" },
];

function rangeQuery(key, from, to) {
  const today = isoToday();
  if (key === "today") return `date_from=${today}&date_to=${today}`;
  if (key === "month") return `date_from=${today.slice(0, 8)}01&date_to=${today}`;
  if (key === "custom") return from && to ? `date_from=${from}&date_to=${to}` : null;
  return `days=${key}`;
}

function CsvButton({ name, columns, rows }) {
  return (
    <button
      type="button"
      className="btn-ghost text-sm"
      disabled={!rows?.length}
      onClick={() => saveCsv(`${name}.csv`, columns, rows)}
    >
      <Icon name="down" size={14} /> CSV
    </button>
  );
}

function Expenses({ from, to, onChanged }) {
  const [list, setList] = useState(null);
  const [values, setValues] = useState({
    spent_on: isoToday(),
    category: "",
    description: "",
    amount: "",
  });
  const [error, setError] = useState("");

  const load = () =>
    api(`/api/expenses/?per_page=50&date_from=${from}&date_to=${to}`)
      .then((data) => setList(data.results))
      .catch(() => setList([]));

  useEffect(() => {
    load();
  }, [from, to]);

  const add = async (event) => {
    event.preventDefault();
    if (values.category.trim().length < 2 || !(Number(values.amount) > 0)) {
      setError("Give a category and an amount above 0.");
      return;
    }
    try {
      await api("/api/expenses/", {
        method: "POST",
        body: {
          spent_on: values.spent_on,
          category: values.category.trim(),
          description: values.description.trim() || null,
          amount: Number(values.amount).toFixed(2),
        },
      });
      setValues((current) => ({ ...current, description: "", amount: "" }));
      setError("");
      load();
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (expense) => {
    try {
      await api(`/api/expenses/${expense.id}`, { method: "DELETE" });
      load();
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  };

  const set = (name) => (event) => setValues((c) => ({ ...c, [name]: event.target.value }));

  return (
    <Panel
      title="Expenses"
      subtitle="Rent, wages, power… in this period"
      actions={
        <CsvButton
          name="expenses"
          rows={list}
          columns={[
            { label: "Date", value: (e) => e.spent_on },
            { label: "Category", value: (e) => e.category },
            { label: "Description", value: (e) => e.description },
            { label: `Amount (${currencyCode()})`, value: (e) => e.amount },
            { label: "Recorded by", value: (e) => e.created_by_name },
          ]}
        />
      }
    >
      <form onSubmit={add} className="grid gap-2 border-b border-line p-4 sm:grid-cols-5">
        <label className="sr-only" htmlFor="expense-date">
          Date
        </label>
        <input
          id="expense-date"
          type="date"
          className="input"
          max={isoToday()}
          value={values.spent_on}
          onChange={set("spent_on")}
        />
        <label className="sr-only" htmlFor="expense-category">
          Category
        </label>
        <input
          id="expense-category"
          className="input"
          placeholder="Category"
          list="expense-categories"
          value={values.category}
          onChange={set("category")}
        />
        <datalist id="expense-categories">
          {["Rent", "Wages", "Electricity", "Water", "Transport", "Internet", "Repairs"].map(
            (c) => (
              <option key={c} value={c} />
            ),
          )}
        </datalist>
        <label className="sr-only" htmlFor="expense-description">
          Description
        </label>
        <input
          id="expense-description"
          className="input"
          placeholder="Description"
          value={values.description}
          onChange={set("description")}
        />
        <label className="sr-only" htmlFor="expense-amount">
          Amount
        </label>
        <input
          id="expense-amount"
          className="input"
          inputMode="decimal"
          placeholder={`Amount (${currencyCode()})`}
          value={values.amount}
          onChange={set("amount")}
        />
        <button type="submit" className="btn-primary">
          Add expense
        </button>
        {error && (
          <p role="alert" className="text-sm text-danger sm:col-span-5">
            {error}
          </p>
        )}
      </form>
      {list?.length === 0 && (
        <p className="px-5 py-6 text-center text-sm text-muted">No expenses in this period.</p>
      )}
      <ul className="divide-y divide-line">
        {list?.map((expense) => (
          <li key={expense.id} className="flex items-center gap-3 px-5 py-2 text-sm">
            <span className="w-20 text-muted">{shortDate(expense.spent_on)}</span>
            <span className="min-w-0 flex-1 truncate">
              <span className="font-medium">{expense.category}</span>
              {expense.description && <span className="text-muted"> · {expense.description}</span>}
            </span>
            <span className="figure">{money(expense.amount)}</span>
            <button
              type="button"
              className="btn-ghost min-h-0 px-2 py-1 text-xs text-danger"
              onClick={() => remove(expense)}
              aria-label={`Delete expense ${expense.category} ${expense.amount}`}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function PerformanceReport() {
  const [months, setMonths] = useState("6");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const get = async () => {
    setBusy(true);
    setError("");
    try {
      await download(
        `/api/reports/performance.pdf?months=${months}`,
        `performance-report-${isoToday()}.pdf`,
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel
      title="Loan-readiness report"
      subtitle="A clean PDF of your sales and cashflow, month by month, to take to a SACCO or bank."
    >
      <div className="flex flex-wrap items-end gap-3 p-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="performance-months" className="text-sm font-medium text-ink-2">
            Covering
          </label>
          <select
            id="performance-months"
            value={months}
            onChange={(event) => setMonths(event.target.value)}
            className="input w-auto"
          >
            <option value="3">The last 3 months</option>
            <option value="6">The last 6 months</option>
            <option value="12">The last 12 months</option>
          </select>
        </div>
        <button type="button" onClick={get} disabled={busy} className="btn-primary">
          <Icon name="printer" size={16} />
          {busy ? "Preparing…" : "Download PDF"}
        </button>
        <p className="w-full text-xs text-muted">
          Uses full months up to the end of last month. Importing your M-Pesa statements first makes
          it much stronger.
        </p>
        {error && (
          <p role="alert" className="w-full text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </Panel>
  );
}

export default function ReportsPage() {
  const [range, setRange] = useState("7");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const query = rangeQuery(range, from, to);

  useEffect(() => {
    if (!query) return undefined;
    let cancelled = false;
    setError("");
    api(`/api/reports/summary?${query}`)
      .then((data) => !cancelled && setReport(data))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [query, version]);

  const best = report?.top_products || [];
  const bestTotal = Math.max(...best.map((p) => Number(p.total)), 1);
  const share = (part) =>
    report && Number(report.sales_total)
      ? Math.round((Number(part) / Number(report.sales_total)) * 100)
      : 0;
  const currency = currencyCode();
  const period = report ? `${report.date_from}_to_${report.date_to}` : "";

  return (
    <section className="flex flex-col gap-6">
      <PageHeader
        title="Reports"
        subtitle={
          report
            ? `From ${shortDate(report.date_from)} to ${shortDate(report.date_to)} (${report.days} ${report.days === 1 ? "day" : "days"}). Voided sales are left out.`
            : "How the business is doing."
        }
      >
        <div role="group" aria-label="Period" className="seg flex-wrap">
          {RANGES.map((option) => (
            <button
              key={option.key}
              type="button"
              aria-pressed={range === option.key}
              onClick={() => setRange(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </PageHeader>

      {range === "custom" && (
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            From
            <input
              type="date"
              className="input"
              value={from}
              max={to || isoToday()}
              onChange={(event) => setFrom(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            To
            <input
              type="date"
              className="input"
              value={to}
              min={from}
              max={isoToday()}
              onChange={(event) => setTo(event.target.value)}
            />
          </label>
          {!query && <p className="text-sm text-muted">Choose both dates (up to one year).</p>}
        </div>
      )}

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
                hint: `${report.sales_count} receipts · VAT ${money(report.vat_total)}`,
                icon: "receipt",
                tone: "brand",
                testId: "kpi-Sales",
              },
              {
                label: "Gross profit",
                value: money(report.gross_profit),
                hint: `${share(report.gross_profit)}% of sales, at the cost when sold`,
                icon: "up",
                tone: "brand",
                testId: "kpi-Gross profit",
              },
              {
                label: "Expenses",
                value: money(report.expenses_total),
                hint: "recorded below",
                icon: "down",
                tone: "danger",
                testId: "kpi-Expenses",
              },
              {
                label: "Net profit",
                value: money(report.net_profit),
                hint: "gross profit − expenses",
                icon: "chart",
                tone: Number(report.net_profit) < 0 ? "danger" : "brand",
                testId: "kpi-Net profit",
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
                label: "Goods received",
                value: money(report.purchases_received_total),
                hint: "deliveries at order cost",
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
              {
                label: "Voided sales",
                value: report.voided_count,
                hint: "not counted above",
                icon: "alert",
                tone: "muted",
                testId: "kpi-Voided",
              },
            ]}
          />

          <Panel
            title="Sales per day"
            subtitle="Hover or tab through the bars for each day"
            bodyClassName="p-5"
            actions={
              <CsvButton
                name={`sales-by-day_${period}`}
                rows={report.by_day}
                columns={[
                  { label: "Day", value: (d) => d.day },
                  { label: "Receipts", value: (d) => d.count },
                  { label: `Sales (${currency})`, value: (d) => d.total },
                  { label: `Gross profit (${currency})`, value: (d) => d.profit },
                ]}
              />
            }
          >
            <BarChart
              data={report.by_day.map((day) => ({
                label: shortDate(day.day),
                value: Number(day.total),
                detail: `${day.count} sales`,
              }))}
              format={money}
              label={`Sales per day, ${report.days} days`}
              height={260}
            />
          </Panel>

          <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
            <Panel
              title="Best sellers"
              subtitle="By takings in this period"
              actions={
                <CsvButton
                  name={`best-sellers_${period}`}
                  rows={best}
                  columns={[
                    { label: "SKU", value: (p) => p.sku },
                    { label: "Product", value: (p) => p.name },
                    { label: "Sold", value: (p) => p.quantity },
                    { label: `Takings (${currency})`, value: (p) => p.total },
                    { label: `Gross profit (${currency})`, value: (p) => p.profit },
                  ]}
                />
              }
            >
              {best.length === 0 ? (
                <EmptyState icon="chart" title="No sales in this period" />
              ) : (
                <table className="data-table w-full text-left text-sm">
                  <thead className="table-head">
                    <tr>
                      <th className="px-5 py-3">Product</th>
                      <th className="px-3 py-3 text-right">Sold</th>
                      <th className="px-3 py-3 text-right">Takings</th>
                      <th className="px-5 py-3 text-right">Profit</th>
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
                        <td className="px-3 py-3 text-right font-semibold">
                          {money(product.total)}
                        </td>
                        <td className="px-5 py-3 text-right text-brand-dark">
                          {money(product.profit)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>

            <Panel
              title="Needs reordering"
              subtitle="At or below the reorder level"
              actions={
                <CsvButton
                  name="needs-reordering"
                  rows={report.low_stock}
                  columns={[
                    { label: "SKU", value: (p) => p.sku },
                    { label: "Product", value: (p) => p.name },
                    { label: "In stock", value: (p) => p.quantity },
                    { label: "Reorder level", value: (p) => p.reorder_level },
                  ]}
                />
              }
            >
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

            {[
              ["By payment method", "by_payment", "Method"],
              ["By attendant", "by_attendant", "Attendant"],
            ].map(([title, key, what]) => (
              <Panel
                key={key}
                title={title}
                actions={
                  <CsvButton
                    name={`${key}_${period}`}
                    rows={report[key]}
                    columns={[
                      { label: what, value: (r) => r.label },
                      { label: "Receipts", value: (r) => r.count },
                      { label: `Sales (${currency})`, value: (r) => r.total },
                    ]}
                  />
                }
              >
                {report[key].length === 0 ? (
                  <p className="px-5 py-6 text-center text-sm text-muted">No sales.</p>
                ) : (
                  <ul className="divide-y divide-line">
                    {report[key].map((row) => (
                      <li key={row.key} className="flex items-center gap-3 px-5 py-3 text-sm">
                        <span className="min-w-0 flex-1 font-medium">{row.label}</span>
                        <span className="text-muted">{row.count} receipts</span>
                        <span className="figure w-32 text-right">{money(row.total)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            ))}
          </div>

          <Expenses
            from={report.date_from}
            to={report.date_to}
            onChanged={() => setVersion((v) => v + 1)}
          />
        </>
      )}
      <PerformanceReport />
    </section>
  );
}
