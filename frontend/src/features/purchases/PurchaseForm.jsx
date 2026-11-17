import { useEffect, useState } from "react";

import { api } from "../../api/client";
import Field from "../../components/Field";
import Icon from "../../components/Icon";
import { money } from "../../format";

let nextKey = 0;
const emptyLine = () => ({ key: (nextKey += 1), product_id: "", quantity: "1", unit_cost: "" });

export default function PurchaseForm({ onSaved, onCancel }) {
  const [suppliers, setSuppliers] = useState([]);
  const [products, setProducts] = useState([]);
  const [supplierId, setSupplierId] = useState("");
  const [lines, setLines] = useState([emptyLine()]);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/suppliers/?per_page=100")
      .then((data) => setSuppliers(data.results))
      .catch(() => {});
    api("/api/products/?per_page=100")
      .then((data) => setProducts(data.results))
      .catch(() => {});
  }, []);

  const change = (key, field, value) => {
    setErrors({});
    setLines((current) =>
      current.map((line) => {
        if (line.key !== key) return line;
        const next = { ...line, [field]: value };
        if (field === "product_id") {
          const product = products.find((p) => String(p.id) === value);
          next.unit_cost = product ? product.cost_price : "";
        }
        return next;
      }),
    );
  };

  const total = lines.reduce(
    (sum, line) => sum + (Number(line.quantity) || 0) * (Number(line.unit_cost) || 0),
    0,
  );

  const submit = async (event) => {
    event.preventDefault();
    const found = {};
    if (!supplierId) found.supplier = "Choose a supplier.";
    const filled = lines.filter((line) => line.product_id);
    if (!filled.length) found.lines = "Add at least one product.";
    if (filled.some((line) => !(Number(line.quantity) >= 1)))
      found.lines = "Each quantity must be 1 or more.";
    if (filled.some((line) => line.unit_cost === "" || Number(line.unit_cost) < 0))
      found.lines = "Each unit cost must be 0 or more.";
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    try {
      const saved = await api("/api/purchases/", {
        method: "POST",
        body: {
          supplier_id: Number(supplierId),
          items: filled.map((line) => ({
            product_id: Number(line.product_id),
            quantity: Number(line.quantity),
            unit_cost: Number(line.unit_cost).toFixed(2),
          })),
        },
      });
      onSaved(saved);
    } catch (err) {
      setErrors({ form: err.message });
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-label="New purchase order"
      className="card flex flex-col gap-4 p-5"
    >
      <h2 className="text-lg font-bold">New purchase order</h2>
      <Field label="Supplier" name="supplier" error={errors.supplier}>
        {(id) => (
          <select
            id={id}
            value={supplierId}
            onChange={(event) => {
              setSupplierId(event.target.value);
              setErrors({});
            }}
            className="input"
          >
            <option value="">Choose…</option>
            {suppliers.map((supplier) => (
              <option key={supplier.id} value={supplier.id}>
                {supplier.name}
              </option>
            ))}
          </select>
        )}
      </Field>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 text-sm font-semibold">Products</legend>
        {lines.map((line, index) => (
          <div
            key={line.key}
            className="grid grid-cols-[minmax(0,1fr)_5rem_6.5rem_auto] items-end gap-2"
          >
            <div className="flex min-w-0 flex-col gap-1">
              <label htmlFor={`line-${line.key}-product`} className="text-xs text-muted">
                Product {index + 1}
              </label>
              <select
                id={`line-${line.key}-product`}
                value={line.product_id}
                onChange={(event) => change(line.key, "product_id", event.target.value)}
                className="input min-w-0 text-sm text-ink"
              >
                <option value="">Choose…</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name} ({product.quantity} in stock)
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor={`line-${line.key}-qty`} className="text-xs text-muted">
                Qty {index + 1}
              </label>
              <input
                id={`line-${line.key}-qty`}
                type="number"
                min="1"
                value={line.quantity}
                onChange={(event) => change(line.key, "quantity", event.target.value)}
                className="input w-full text-sm text-ink"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor={`line-${line.key}-cost`} className="text-xs text-muted">
                Unit cost {index + 1}
              </label>
              <input
                id={`line-${line.key}-cost`}
                type="number"
                min="0"
                step="0.01"
                value={line.unit_cost}
                onChange={(event) => change(line.key, "unit_cost", event.target.value)}
                className="input w-full text-sm text-ink"
              />
            </div>
            <button
              type="button"
              aria-label={`Remove product ${index + 1}`}
              disabled={lines.length === 1}
              onClick={() => setLines((current) => current.filter((l) => l.key !== line.key))}
              className="grid size-10 place-items-center rounded-lg border border-line text-muted disabled:opacity-40"
            >
              <Icon name="close" size={16} />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setLines((current) => [...current, emptyLine()])}
          className="btn-secondary self-start"
        >
          <Icon name="plus" size={16} /> Add product line
        </button>
        {errors.lines && <span className="text-sm text-danger">{errors.lines}</span>}
      </fieldset>

      <div className="flex items-baseline justify-between border-t border-line pt-3">
        <span className="text-muted">Order total</span>
        <span className="font-display text-xl font-bold">{money(total)}</span>
      </div>
      {errors.form && (
        <p role="alert" className="text-sm text-danger">
          {errors.form}
        </p>
      )}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="btn-primary">
          Place order
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  );
}