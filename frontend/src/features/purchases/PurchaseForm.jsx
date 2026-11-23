import { useEffect, useState } from "react";

import { api } from "../../api/client";
import Field from "../../components/Field";
import Icon from "../../components/Icon";
import SearchPicker, { describeProduct } from "../../components/SearchPicker";
import { money } from "../../format";

let nextKey = 0;
const emptyLine = (product = null, quantity = "1", unitCost = "") => ({
  key: (nextKey += 1),
  product,
  quantity,
  unit_cost: unitCost,
});

const describeSupplier = (supplier) => ({
  title: supplier.name,
  detail: supplier.code,
});

// New order, or editing a draft (`purchase`). US-19: a PO starts as a Draft and becomes
// Ordered when confirmed; it can be linked to an approved request.
export default function PurchaseForm({ purchase = null, requestId = null, onSaved, onCancel }) {
  const [supplier, setSupplier] = useState(
    purchase
      ? { id: purchase.supplier_id, name: purchase.supplier_name, code: purchase.supplier_code }
      : null,
  );
  const [lines, setLines] = useState(
    purchase
      ? purchase.items.map((item) =>
          emptyLine(
            { id: item.product_id, name: item.product_name, sku: item.sku, quantity: "?" },
            String(item.quantity),
            item.unit_cost,
          ),
        )
      : [emptyLine()],
  );
  const [approved, setApproved] = useState([]);
  const [linked, setLinked] = useState(String(purchase?.request_id || requestId || ""));
  const [notes, setNotes] = useState(purchase?.notes || "");
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/requests/?status=approved&per_page=50")
      .then((data) => {
        const list = data.results;
        // keep the linked request in the list even if it is no longer "approved"
        if (purchase?.request_id && !list.some((r) => r.id === purchase.request_id)) {
          list.push({
            id: purchase.request_id,
            reference: purchase.request_reference,
            item: "",
            quantity: "",
          });
        }
        setApproved(list);
      })
      .catch(() => {});
  }, [purchase]);

  const change = (key, field, value) => {
    setErrors({});
    setLines((current) =>
      current.map((line) => {
        if (line.key !== key) return line;
        const next = { ...line, [field]: value };
        if (field === "product") next.unit_cost = value ? value.cost_price : "";
        return next;
      }),
    );
  };

  const total = lines.reduce(
    (sum, line) => sum + (Number(line.quantity) || 0) * (Number(line.unit_cost) || 0),
    0,
  );

  const submit = async (confirm) => {
    const found = {};
    if (!supplier) found.supplier = "Choose a supplier.";
    const filled = lines.filter((line) => line.product);
    if (!filled.length) found.lines = "Add at least one product.";
    if (filled.some((line) => !(Number(line.quantity) >= 1)))
      found.lines = "Each quantity must be 1 or more.";
    if (filled.some((line) => line.unit_cost === "" || Number(line.unit_cost) < 0))
      found.lines = "Each unit cost must be 0 or more.";
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    try {
      const saved = await api(purchase ? `/api/purchases/${purchase.id}` : "/api/purchases/", {
        method: purchase ? "PUT" : "POST",
        body: {
          supplier_id: supplier.id,
          request_id: linked ? Number(linked) : null,
          notes: notes.trim() || null,
          confirm,
          items: filled.map((line) => ({
            product_id: line.product.id,
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
      onSubmit={(event) => {
        event.preventDefault();
        submit(true);
      }}
      noValidate
      aria-label={purchase ? `Edit ${purchase.reference}` : "New purchase order"}
      className="card flex flex-col gap-5 p-6"
    >
      <h2 className="text-lg font-bold">
        {purchase ? `Edit draft ${purchase.reference}` : "New purchase order"}
      </h2>
      <div className="grid gap-4 md:grid-cols-2">
        <SearchPicker
          label="Supplier"
          path="/api/suppliers/"
          extra="&active=true"
          placeholder="Search active suppliers"
          value={supplier}
          describe={describeSupplier}
          onPick={(picked) => {
            setSupplier(picked);
            setErrors({});
          }}
          error={errors.supplier}
        />
        <Field label="For an approved request (optional)" name="request">
          {(id) => (
            <select
              id={id}
              value={linked}
              onChange={(event) => setLinked(event.target.value)}
              className="input"
            >
              <option value="">Not linked</option>
              {approved.map((request) => (
                <option key={request.id} value={request.id}>
                  {request.reference}
                  {request.item ? `: ${request.item} × ${request.quantity}` : ""}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 text-sm font-semibold">Products</legend>
        {lines.map((line, index) => (
          <div
            key={line.key}
            className="grid grid-cols-[minmax(0,1fr)_5rem_6.5rem_auto] items-end gap-2"
          >
            <SearchPicker
              id={`line-${line.key}-product`}
              label={`Product ${index + 1}`}
              path="/api/products/"
              placeholder="Name or SKU"
              value={line.product}
              describe={describeProduct}
              onPick={(picked) => change(line.key, "product", picked)}
            />
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

      <Field label="Notes for the supplier or store (optional)" name="notes">
        {(id) => (
          <textarea
            id={id}
            rows={2}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className="input h-auto py-2"
          />
        )}
      </Field>

      <div className="flex items-baseline justify-between border-t border-line pt-3">
        <span className="text-muted">Order total (worked out again by the server)</span>
        <span className="font-display text-xl font-bold">{money(total)}</span>
      </div>
      {errors.form && (
        <p role="alert" className="text-sm text-danger">
          {errors.form}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={busy} className="btn-primary">
          Place order
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => submit(false)}
          className="btn-secondary"
        >
          Save as draft
        </button>
        <button type="button" onClick={onCancel} className="btn-ghost">
          Cancel
        </button>
      </div>
    </form>
  );
}
