import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import Field from "../../components/Field";
import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { SkeletonRows } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { dateTime } from "../../format";
import { movements } from "../../store";

function AdjustmentForm({ products, onSaved, onCancel }) {
  const [values, setValues] = useState({ product_id: "", change: "", reason: "" });
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
    if (!values.product_id) found.product_id = "Choose a product.";
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
        body: { product_id: Number(values.product_id), change, reason: values.reason.trim() },
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
      className="card flex flex-col gap-4 p-5"
    >
      <h2 className="text-lg font-bold">Adjust stock</h2>
      <div className="grid gap-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Field label="Product" name="product_id" error={errors.product_id}>
          {(id) => (
            <select
              id={id}
              name="product_id"
              value={values.product_id}
              onChange={update}
              className="input"
            >
              <option value="">Choose…</option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name} ({product.quantity} in stock)
                </option>
              ))}
            </select>
          )}
        </Field>
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
  { value: "purchase", label: "Purchases" },
  { value: "adjustment", label: "Adjustments" },
];

export default function StockPage() {
  const dispatch = useDispatch();
  const list = useSelector((state) => state.movements);
  const [products, setProducts] = useState([]);
  const [type, setType] = useState("");
  const [productId, setProductId] = useState("");
  const [page, setPage] = useState(1);
  const [adjusting, setAdjusting] = useState(false);
  const [notice, setNotice] = useState("");

  const loadProducts = () =>
    api("/api/products/?per_page=100")
      .then((data) => setProducts(data.results))
      .catch(() => {});

  useEffect(() => {
    loadProducts();
  }, []);

  useEffect(() => {
    dispatch(movements.fetchList({ type, product_id: productId, page, per_page: 15 }));
  }, [dispatch, type, productId, page]);

  return (
    <section className="flex flex-col gap-4">
      <PageHeader title="Stock ledger" subtitle="Every change to stock, with who made it and why.">
        {!adjusting && (
          <button type="button" onClick={() => setAdjusting(true)} className="btn-primary">
            Adjust stock
          </button>
        )}
      </PageHeader>

      {adjusting && (
        <AdjustmentForm
          products={products}
          onCancel={() => setAdjusting(false)}
          onSaved={(movement) => {
            setAdjusting(false);
            setNotice(
              `${movement.product_name}: ${movement.change > 0 ? "+" : ""}${movement.change}. Now ${movement.balance_now} in stock.`,
            );
            loadProducts();
            dispatch(movements.fetchList({ type, product_id: productId, page, per_page: 15 }));
          }}
        />
      )}

      {notice && (
        <p role="status" className="rounded-lg bg-mint p-3 text-sm">
          {notice}
        </p>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <div role="group" aria-label="Filter by type" className="flex flex-wrap gap-2">
          {TYPES.map((tab) => (
            <button
              key={tab.value}
              type="button"
              aria-pressed={type === tab.value}
              onClick={() => {
                setType(tab.value);
                setPage(1);
              }}
              className="chip"
            >
              {tab.label}
            </button>
          ))}
        </div>
        <label htmlFor="ledger-product" className="sr-only">
          Filter by product
        </label>
        <select
          id="ledger-product"
          value={productId}
          onChange={(event) => {
            setProductId(event.target.value);
            setPage(1);
          }}
          className="input sm:ml-auto"
        >
          <option value="">All products</option>
          {products.map((product) => (
            <option key={product.id} value={product.id}>
              {product.name}
            </option>
          ))}
        </select>
      </div>

      {list.error && (
        <p role="alert" className="text-danger">
          {list.error}
        </p>
      )}

      <div className="card relative overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="table-head">
            <tr>
              <th className="p-3">When</th>
              <th className="p-3">Product</th>
              <th className="p-3">Type</th>
              <th className="p-3 text-right">Change</th>
              <th className="p-3">Reason</th>
              <th className="p-3">By</th>
            </tr>
          </thead>
          <tbody>
            {list.status === "loading" && <SkeletonRows cols={6} />}
            {list.status === "ready" && list.items.length === 0 && (
              <tr>
                <td colSpan="6" className="p-3 text-muted">
                  No stock changes found.
                </td>
              </tr>
            )}
            {list.status === "ready" &&
              list.items.map((movement) => (
                <tr key={movement.id} className="border-t border-line">
                  <td className="p-3 whitespace-nowrap text-muted">
                    {dateTime(movement.created_at)}
                  </td>
                  <td className="p-3">
                    <Link to={`/products/${movement.product_id}`} className="link">
                      {movement.product_name}
                    </Link>
                  </td>
                  <td className="p-3">
                    <StatusBadge value={movement.type} />
                  </td>
                  <td
                    className={`p-3 text-right font-semibold tabular-nums ${movement.change < 0 ? "text-danger" : "text-brand-dark"}`}
                  >
                    {movement.change > 0 ? `+${movement.change}` : movement.change}
                  </td>
                  <td className="p-3">{movement.reason}</td>
                  <td className="p-3 text-muted">{movement.user_name}</td>
                </tr>
              ))}
          </tbody>
        </table>
        <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
      </div>
    </section>
  );
}