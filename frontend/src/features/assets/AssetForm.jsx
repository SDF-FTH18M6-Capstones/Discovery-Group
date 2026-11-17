import { useEffect, useState } from "react";
import { useDispatch } from "react-redux";

import { api } from "../../api/client";
import { ROLE_NAMES } from "../../auth/roles";
import Field from "../../components/Field";
import { assets } from "../../store";

export const ASSET_STATUSES = ["available", "assigned", "in_repair"];

export function validateAsset(values) {
  const errors = {};
  if (!values.asset_code.trim()) errors.asset_code = "Asset code is required.";
  if (!values.name.trim()) errors.name = "Name is required.";
  if (values.status === "assigned" && !values.assigned_to)
    errors.assigned_to = "Choose who holds it.";
  return errors;
}

export default function AssetForm({ asset, onSaved, onCancel }) {
  const dispatch = useDispatch();
  const [people, setPeople] = useState([]);
  const [values, setValues] = useState({
    asset_code: asset?.asset_code || "",
    name: asset?.name || "",
    status: asset?.status || "available",
    assigned_to: asset?.assigned_to ? String(asset.assigned_to) : "",
  });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");

  useEffect(() => {
    api("/api/users/choices")
      .then(setPeople)
      .catch(() => setPeople([]));
  }, []);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({
      ...current,
      [name]: value,
      ...(name === "status" && value === "available" ? { assigned_to: "" } : {}),
    }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const found = validateAsset(values);
    setErrors(found);
    if (Object.keys(found).length) return;

    const data = {
      asset_code: values.asset_code.trim(),
      name: values.name.trim(),
      status: values.status,
      assigned_to: values.assigned_to ? Number(values.assigned_to) : null,
    };
    const result = await dispatch(assets.saveItem({ id: asset?.id, data }));
    if (assets.saveItem.fulfilled.match(result)) {
      onSaved(result.payload);
    } else {
      setFormError(result.payload.message);
      const flat = Object.fromEntries(
        Object.entries(result.payload.details).map(([key, list]) => [key, [].concat(list)[0]]),
      );
      setErrors(flat);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      aria-label={asset ? "Edit asset" : "Add asset"}
      className="card grid gap-4 p-5 sm:grid-cols-4"
    >
      {formError && (
        <p role="alert" className="text-sm text-danger sm:col-span-4">
          {formError}
        </p>
      )}
      <Field
        label="Asset code"
        name="asset_code"
        placeholder="AST-0005"
        value={values.asset_code}
        onChange={handleChange}
        error={errors.asset_code}
      />
      <Field
        label="Name"
        name="name"
        value={values.name}
        onChange={handleChange}
        error={errors.name}
      />
      <Field label="Status" name="status" error={errors.status}>
        {(id) => (
          <select
            id={id}
            name="status"
            value={values.status}
            onChange={handleChange}
            className="input px-2"
          >
            <option value="available">Available</option>
            <option value="assigned">Assigned</option>
            <option value="in_repair">In repair</option>
          </select>
        )}
      </Field>
      <Field label="Held by" name="assigned_to" error={errors.assigned_to}>
        {(id) => (
          <select
            id={id}
            name="assigned_to"
            value={values.assigned_to}
            onChange={handleChange}
            disabled={values.status === "available"}
            aria-invalid={Boolean(errors.assigned_to)}
            className={`h-10 rounded-lg border bg-surface px-2 disabled:bg-canvas ${errors.assigned_to ? "border-danger" : "border-line"}`}
          >
            <option value="">Nobody</option>
            {people.map((person) => (
              <option key={person.id} value={person.id}>
                {person.full_name} · {ROLE_NAMES[person.role] || person.role}
              </option>
            ))}
          </select>
        )}
      </Field>
      <div className="flex gap-2 sm:col-span-4">
        <button type="submit" className="btn-primary">
          Save asset
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  );
}
