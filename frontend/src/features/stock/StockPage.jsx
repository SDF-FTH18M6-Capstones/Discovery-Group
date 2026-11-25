import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Link } from "react-router-dom";

import { api, download } from "../../api/client";
import Field from "../../components/Field";
import SearchPicker, { describeProduct } from "../../components/SearchPicker";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { SkeletonRows } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { EmptyState, StatStrip } from "../../components/ui";
import { dateTime, isoToday } from "../../format";
import { movements } from "../../store";

function AdjustmentForm({ onSaved, onCancel }) {
  const [product, setProduct] = useState(null);
  const [values, setValues] = useState({ change: "", reason: "" });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  const update = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors({});
  };

  const submit = async (event) => {
    event.preventDefault();
    const found = {};
    if (!product) found.product_id = "Choose a product.";
    const change = Number(values.change);
    if (!Number.isInteger(change) || change === 0)
      found.change = "Enter a whole number, not 0 (minus to remove).";
    if (values.reason.trim().length < 3) found.reason = "Say why (3+ characters).";
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    try {
      const saved = await api("/api/stock/adjustments", {
        method: "POST",
        body: { product_id: product.id, change, reason: values.reason.trim() },
      });
      onSaved(saved);
    } catch (err) {
      const fields = Object.fromEntries(
        Object.entries(err.details || {}).map(([key, messages]) => [key, [].concat(messages)[0]]),
      );
      setErrors(Object.keys(fields).length ? fields : { form: err.message });
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-label="Adjust stock"
      className="card flex flex-col gap-5 p-6"
    >
      <h2 className="text-lg font-bold">Adjust stock</h2>
      <div className="grid gap-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <SearchPicker
          id="field-product_id"
          label="Product"
          path="/api/products/"
          extra="&status=all"
          placeholder="Name or SKU"
          value={product}
          describe={describeProduct}
          onPick={(picked) => {
            setProduct(picked);
            setErrors({});
          }}
          error={errors.product_id}
        />
        <Field
          label="Change"
          name="change"
          type="number"
          placeholder="-2 or 5"
          value={values.change}
          onChange={update}
          error={errors.change}
        />
      </div>
      <Field
        label="Reason"
        name="reason"
        placeholder="Damaged in store, stock count…"
        value={values.reason}
        onChange={update}
        error={errors.reason}
      />
      {errors.form && (
        <p role="alert" className="text-sm text-danger">
          {errors.form}
        </p>
      )}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="btn-primary">
          Save adjustment
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  );
}

const TYPES = [
  { value: "", label: "All" },
  { value: "sale", label: "Sales" },
  { value: "purchase", label: "Receipts" },
  { value: "adjustment", label: "Adjustments" },
  { value: "sale_void", label: "Voids" },
];

export default function StockPage() {
  const dispatch = useDispatch();
  const list = useSelector((state) => state.movements);
  const [type, setType] = useState("");
  const [product, setProduct] = useState(null);
  const productId = product?.id || "";
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [exporting, setExporting] = useState("");
  const [page, setPage] = useState(1);
  const [adjusting, setAdjusting] = useState(false);
  const [notice, setNotice] = useState("");

  const [totals, setTotals] = useState({});
  const loadTotals = () =>
    Promise.allSettled(
      ["sale", "purchase", "adjustment"].map((kind) =>
        api(`/api/stock/movements?type=${kind}&per_page=1`),
      ),
    ).then((results) =>
      setTotals(Object.fromEntries(results.map((r, i) => [i, r.value?.count ?? "—"]))),
    );

  useEffect(() => {
    loadTotals();
  }, []);

  const filters = { type, product_id: productId, date_from: dateFrom, date_to: dateTo };
  useEffect(() => {
    dispatch(
      movements.fetchList({
        type,
        product_id: productId,
        date_from: dateFrom,
        date_to: dateTo,
        page,
        per_page: 15,
      }),
    );
  }, [dispatch, type, productId, dateFrom, dateTo, page]);

  const exportCsv = async () => {
    setExporting("Preparing…");
    const query = new URLSearchParams(
      Object.entries(filters).filter(([, value]) => value !== "" && value != null),
    );
    try {
      await download(`/api/stock/movements.csv?${query}`, `stock-ledger-${isoToday()}.csv`);
      setExporting("");
    } catch (err) {
      setExporting(err.message);
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <PageHeader title="Stock ledger" subtitle="Every change to stock, with who made it and why.">
        <button type="button" onClick={exportCsv} className="btn-secondary">
          <Icon name="down" size={16} />
          Export CSV
        </button>
        {!adjusting && (
          <button type="button" onClick={() => setAdjusting(true)} className="btn-primary">
            <Icon name="ledger" size={16} />
            Adjust stock
          </button>
        )}
      </PageHeader>

      <StatStrip
        items={[
          { label: "Lines from the till", value: totals[0], icon: "receipt", tone: "info" },
          { label: "Deliveries received", value: totals[1], icon: "truck", tone: "brand" },
          { label: "Adjustments made", value: totals[2], icon: "ledger", tone: "saffron" },
        ]}
      />

      {adjusting && (
        <AdjustmentForm
          onCancel={() => setAdjusting(false)}
          onSaved={(movement) => {
            setAdjusting(false);
            setNotice(
              `${movement.product_name}: ${movement.change > 0 ? "+" : ""}${movement.change}. Now ${movement.balance_now} in stock.`,
            );
            loadTotals();
            dispatch(movements.fetchList({ ...filters, page, per_page: 15 }));
          }}
        />
      )}

      {notice && (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {notice}
        </p>
      )}

      {(list.error || exporting) && (
        <p role={list.error ? "alert" : "status"} className="rounded-xl bg-surface-2 p-3 text-sm">
          {list.error || exporting}
        </p>
      )}

      <div className="panel">
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
          <div role="group" aria-label="Filter by type" className="seg">
            {TYPES.map((tab) => (
              <button
                key={tab.value}
                type="button"
                aria-pressed={type === tab.value}
                onClick={() => {
                  setType(tab.value);
                  setPage(1);
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="w-64">
            <SearchPicker
              id="ledger-product"
              label="Product"
              path="/api/products/"
              extra="&status=all"
              placeholder="All products"
              value={product}
              describe={describeProduct}
              onPick={(picked) => {
                setProduct(picked);
                setPage(1);
              }}
            />
          </div>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-2">
            From
            <input
              type="date"
              className="input"
              value={dateFrom}
              max={dateTo || isoToday()}
              onChange={(event) => {
                setDateFrom(event.target.value);
                setPage(1);
              }}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-2">
            To
            <input
              type="date"
              className="input"
              value={dateTo}
              min={dateFrom}
              max={isoToday()}
              onChange={(event) => {
                setDateTo(event.target.value);
                setPage(1);
              }}
            />
          </label>
        </div>
        <div className="relative overflow-x-auto">
          <table className="data-table w-full text-left text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-5 py-3 text-right">Change</th>
                <th className="px-3 py-3 text-right">After</th>
                <th className="px-3 py-3">Product</th>
                <th className="px-3 py-3">Reference</th>
                <th className="px-3 py-3">Reason</th>
                <th className="px-3 py-3">Type</th>
                <th className="px-3 py-3">By</th>
                <th className="px-5 py-3">When</th>
              </tr>
            </thead>
            <tbody>
              {list.status === "loading" && <SkeletonRows cols={8} />}
              {list.status === "ready" &&
                list.items.map((movement) => (
                  <tr key={movement.id} className="border-t border-line">
                    <td className="px-5 py-3 text-right">
                      <span
                        className={`figure inline-block min-w-12 rounded-lg px-2 py-1 text-center ${
                          movement.change < 0
                            ? "bg-danger-soft text-danger"
                            : "bg-mint text-brand-dark"
                        }`}
                      >
                        {movement.change > 0 ? `+${movement.change}` : movement.change}
                      </span>
                    </td>
                    <td className="figure px-3 py-3 text-right">{movement.quantity_after}</td>
                    <td className="px-3 py-3">
                      <Link
                        to={`/products/${movement.product_id}`}
                        className="font-medium hover:text-brand-dark hover:underline"
                      >
                        {movement.product_name}
                      </Link>
                    </td>
                    <td className="code px-3 py-3 text-muted">{movement.reference || "—"}</td>
                    <td className="px-3 py-3">{movement.reason}</td>
                    <td className="px-3 py-3">
                      <StatusBadge value={movement.type} />
                    </td>
                    <td className="px-3 py-3 text-muted">{movement.user_name}</td>
                    <td className="px-5 py-3 whitespace-nowrap text-muted">
                      {dateTime(movement.created_at)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
          {list.status === "ready" && list.items.length === 0 && (
            <EmptyState icon="ledger" title="No stock changes found">
              Sales, deliveries and adjustments show up here as they happen.
            </EmptyState>
          )}
        </div>
        <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
      </div>
    </section>
  );
}
