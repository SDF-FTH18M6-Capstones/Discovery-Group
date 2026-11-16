import { useState } from "react";
import { useDispatch } from "react-redux";

import Field from "../../components/Field";
import { products } from "../../store";

const EMPTY = {
  sku: "",
  name: "",
  category_id: "",
  cost_price: "",
  selling_price: "",
  quantity: "0",
  reorder_level: "0",
};

export function validateProduct(values) {
  const errors = {};
  if (!values.sku.trim()) errors.sku = "SKU is required.";
  if (!values.name.trim()) errors.name = "Name is required.";
  if (!values.category_id) errors.category_id = "Choose a category.";
  for (const field of ["cost_price", "selling_price", "quantity", "reorder_level"]) {
    if (values[field] === "" || Number(values[field]) < 0 || Number.isNaN(Number(values[field]))) {
      errors[field] = "Enter a number of 0 or more.";
    }
  }
  return errors;
}

export default function ProductForm({ product, categoryOptions, onSaved, onCancel }) {
  const dispatch = useDispatch();
  const [values, setValues] = useState(
    product
      ? Object.fromEntries(Object.keys(EMPTY).map((key) => [key, String(product[key] ?? "")]))
      : EMPTY,
  );
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const found = validateProduct(values);
    setErrors(found);
    setFormError("");
    if (Object.keys(found).length) return;

    setSaving(true);
    const data = {
      ...values,
      category_id: Number(values.category_id),
      quantity: Number(values.quantity),
      reorder_level: Number(values.reorder_level),
    };
    const result = await dispatch(products.saveItem({ id: product?.id, data }));
    setSaving(false);
    if (products.saveItem.fulfilled.match(result)) {
      onSaved(result.payload);
    } else {
      // Show the backend's per-field errors next to each field.
      const flat = Object.fromEntries(
        Object.entries(result.payload.details).map(([key, list]) => [key, [].concat(list)[0]]),
      );
      setErrors(flat);
      setFormError(result.payload.message);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      aria-label={product ? "Edit product" : "Add product"}
      className="grid gap-4 rounded-xl border border-line bg-white p-5 sm:grid-cols-2"
    >
      <h2 className="text-lg font-semibold sm:col-span-2">
        {product ? `Edit ${product.name}` : "Add product"}
      </h2>
      {formError && (
        <p role="alert" className="rounded-lg bg-orange-50 p-2 text-sm text-danger sm:col-span-2">
          {formError}
        </p>
      )}
      <Field label="SKU" name="sku" value={values.sku} onChange={handleChange} error={errors.sku} />
      <Field
        label="Name"
        name="name"
        value={values.name}
        onChange={handleChange}
        error={errors.name}
      />
      <Field label="Category" name="category_id" error={errors.category_id}>
        {(id) => (
          <select
            id={id}
            name="category_id"
            value={values.category_id}
            onChange={handleChange}
            className="h-10 rounded-lg border border-line bg-white px-2"
          >
            <option value="">Choose…</option>
            {categoryOptions.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field
        label="Cost price (KES)"
        name="cost_price"
        inputMode="decimal"
        value={values.cost_price}
        onChange={handleChange}
        error={errors.cost_price}
      />
      <Field
        label="Selling price (KES)"
        name="selling_price"
        inputMode="decimal"
        value={values.selling_price}
        onChange={handleChange}
        error={errors.selling_price}
      />
      <Field
        label="Quantity in stock"
        name="quantity"
        inputMode="numeric"
        value={values.quantity}
        onChange={handleChange}
        error={errors.quantity}
      />
      <Field
        label="Reorder level"
        name="reorder_level"
        inputMode="numeric"
        value={values.reorder_level}
        onChange={handleChange}
        error={errors.reorder_level}
      />
      <div className="flex gap-2 sm:col-span-2">
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-brand px-4 py-2 font-semibold text-white disabled:opacity-60"
        >
          {saving ? "Saving…" : "Save product"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-line px-4 py-2"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
