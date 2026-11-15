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

    // Empty optional fields are sent as null, not "".
    const data = { name: values.name, email: values.email || null, phone: values.phone || null };
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
      className="grid gap-4 rounded-xl border border-line bg-white p-5 sm:grid-cols-3"
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
      <div className="flex gap-2 sm:col-span-3">
        <button type="submit" className="rounded-lg bg-brand px-4 py-2 font-semibold text-white">
          Save supplier
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