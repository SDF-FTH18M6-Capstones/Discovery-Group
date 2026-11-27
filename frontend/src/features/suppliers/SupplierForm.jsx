import { useState } from "react";
import { useDispatch } from "react-redux";

import Field from "../../components/Field";
import { suppliers } from "../../store";

export function validateSupplier(values) {
  const errors = {};
  if (!values.name.trim()) errors.name = "Name is required.";
  if (values.email && !/^\S+@\S+\.\S+$/.test(values.email)) errors.email = "Enter a valid email.";
  if (values.phone && !/^\+?[0-9 ]{7,20}$/.test(values.phone))
    errors.phone = "Enter a valid phone number.";
  return errors;
}

export default function SupplierForm({ supplier, onSaved, onCancel }) {
  const dispatch = useDispatch();
  const [values, setValues] = useState({
    name: supplier?.name || "",
    email: supplier?.email || "",
    phone: supplier?.phone || "",
    address: supplier?.address || "",
    is_active: supplier ? supplier.is_active !== false : true,
    trusted: Boolean(supplier?.trusted),
  });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const found = validateSupplier(values);
    setErrors(found);
    if (Object.keys(found).length) return;

    const data = {
      name: values.name,
      email: values.email || null,
      phone: values.phone || null,
      address: values.address || null,
      is_active: values.is_active,
      trusted: values.trusted,
    };
    const result = await dispatch(suppliers.saveItem({ id: supplier?.id, data }));
    if (suppliers.saveItem.fulfilled.match(result)) {
      onSaved(result.payload);
    } else {
      setFormError(result.payload.message);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      aria-label={supplier ? "Edit supplier" : "Add supplier"}
      className="card grid gap-5 p-6 sm:grid-cols-3"
    >
      {formError && (
        <p role="alert" className="text-sm text-danger sm:col-span-3">
          {formError}
        </p>
      )}
      <Field
        label="Name"
        name="name"
        value={values.name}
        onChange={handleChange}
        error={errors.name}
      />
      <Field
        label="Email"
        name="email"
        type="email"
        value={values.email}
        onChange={handleChange}
        error={errors.email}
      />
      <Field
        label="Phone"
        name="phone"
        value={values.phone}
        onChange={handleChange}
        error={errors.phone}
      />
      <div className="sm:col-span-2">
        <Field
          label="Address"
          name="address"
          value={values.address}
          onChange={handleChange}
          error={errors.address}
        />
      </div>
      <label className="flex items-center gap-2 self-end pb-2 text-sm">
        <input
          type="checkbox"
          checked={values.is_active}
          onChange={(event) =>
            setValues((current) => ({ ...current, is_active: event.target.checked }))
          }
          className="size-4 accent-[var(--sp-brand)]"
        />
        Active (can receive new orders)
      </label>
      <label className="flex items-start gap-2 text-sm sm:col-span-2">
        <input
          type="checkbox"
          checked={values.trusted}
          onChange={(event) =>
            setValues((current) => ({ ...current, trusted: event.target.checked }))
          }
          className="mt-0.5 size-4 accent-[var(--sp-brand)]"
        />
        <span>
          Trusted supplier
          <span className="block text-muted">
            When stock runs low, orders for this supplier are placed and emailed to them straight
            away instead of waiting as drafts.
          </span>
        </span>
      </label>
      <div className="flex gap-2 sm:col-span-3">
        <button type="submit" className="btn-primary">
          Save supplier
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  );
}
