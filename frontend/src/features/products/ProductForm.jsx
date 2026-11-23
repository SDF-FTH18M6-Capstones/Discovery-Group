import { useState } from "react";
import { useDispatch } from "react-redux";

import { api, upload } from "../../api/client";
import Field from "../../components/Field";
import PhotoPicker, { checkPhoto } from "../../components/PhotoPicker";
import { currencyCode } from "../../format";
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

// Checks the form in the browser before anything is sent.
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
  // Every input reads from and writes to this one state object.
  const [values, setValues] = useState(
    product
      ? Object.fromEntries(Object.keys(EMPTY).map((key) => [key, String(product[key] ?? "")]))
      : EMPTY,
  );
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [photo, setPhoto] = useState(null);
  const [photoError, setPhotoError] = useState("");
  const [removePhoto, setRemovePhoto] = useState(false);
  const currency = currencyCode();

  const pickPhoto = (file) => {
    const problem = checkPhoto(file);
    setPhotoError(problem);
    setPhoto(problem ? null : file);
    if (file && !problem) setRemovePhoto(false);
  };

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
    if (product) delete data.quantity; // stock changes only through adjustments (US-09)
    const result = await dispatch(products.saveItem({ id: product?.id, data }));
    if (products.saveItem.fulfilled.match(result)) {
      let saved = result.payload;
      try {
        if (photo) saved = await upload(`/api/products/${saved.id}/photo`, photo);
        else if (removePhoto && product?.image_url)
          saved = await api(`/api/products/${saved.id}/photo`, { method: "DELETE" });
      } catch (error) {
        setSaving(false);
        setPhotoError(`The product was saved, but the photo was not: ${error.message}`);
        return;
      }
      setSaving(false);
      onSaved(saved);
    } else {
      setSaving(false);
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
      className="card grid gap-5 p-6 sm:grid-cols-2"
    >
      <h2 className="text-lg font-semibold sm:col-span-2">
        {product ? `Edit ${product.name}` : "Add product"}
      </h2>
      {formError && (
        <p role="alert" className="rounded-lg bg-danger-soft p-2 text-sm text-danger sm:col-span-2">
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
            className="input px-2"
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
        label={`Cost price (${currency})`}
        name="cost_price"
        inputMode="decimal"
        value={values.cost_price}
        onChange={handleChange}
        error={errors.cost_price}
      />
      <Field
        label={`Selling price (${currency})`}
        name="selling_price"
        inputMode="decimal"
        value={values.selling_price}
        onChange={handleChange}
        error={errors.selling_price}
      />
      {product ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-ink-2">Quantity in stock</span>
          <span className="figure text-xl">{product.quantity}</span>
          <span className="text-xs text-muted">
            Change stock with an adjustment on the Stock ledger, so every change is recorded.
          </span>
        </div>
      ) : (
        <Field
          label="Opening stock"
          name="quantity"
          inputMode="numeric"
          value={values.quantity}
          onChange={handleChange}
          error={errors.quantity}
        />
      )}
      <Field
        label="Reorder level"
        name="reorder_level"
        inputMode="numeric"
        value={values.reorder_level}
        onChange={handleChange}
        error={errors.reorder_level}
      />
      <div className="sm:col-span-2">
        <PhotoPicker
          currentUrl={removePhoto ? "" : product?.image_url}
          file={photo}
          onPick={pickPhoto}
          onRemove={() => {
            setPhoto(null);
            setRemovePhoto(true);
          }}
          error={photoError}
        />
      </div>
      {product && (
        <p className="text-xs text-muted sm:col-span-2">
          New prices apply to new sales only; past receipts keep the price they were sold at.
        </p>
      )}
      <div className="flex gap-2 sm:col-span-2">
        <button type="submit" disabled={saving} className="btn-primary">
          {saving ? "Saving…" : "Save product"}
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  );
}
