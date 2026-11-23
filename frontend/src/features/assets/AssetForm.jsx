import { useEffect, useState } from "react";
import { useDispatch } from "react-redux";

import { api, upload } from "../../api/client";
import { ROLE_NAMES } from "../../auth/roles";
import Field from "../../components/Field";
import PhotoPicker, { checkPhoto } from "../../components/PhotoPicker";
import { currencyCode, isoToday } from "../../format";
import { assets } from "../../store";

export const CONDITIONS = ["new", "good", "fair", "poor", "damaged"];
export const conditionLabel = (value) => (value ? value[0].toUpperCase() + value.slice(1) : "");

export function validateAsset(values) {
  const errors = {};
  if (!values.name.trim()) errors.name = "Name is required.";
  if (values.purchase_cost && !(Number(values.purchase_cost) >= 0))
    errors.purchase_cost = "Enter an amount of 0 or more.";
  if (values.expected_return && values.expected_return < isoToday())
    errors.expected_return = "Choose today or a later date.";
  return errors;
}

// US-32: the server gives every asset its code (AST-0001) and barcode.
export default function AssetForm({ asset, categories, onSaved, onCancel }) {
  const dispatch = useDispatch();
  const [people, setPeople] = useState([]);
  const [values, setValues] = useState({
    name: asset?.name || "",
    category_id: asset?.category_id ? String(asset.category_id) : "",
    serial_number: asset?.serial_number || "",
    purchase_date: asset?.purchase_date || "",
    purchase_cost: asset?.purchase_cost || "",
    condition: asset?.condition || "good",
    notes: asset?.notes || "",
    assigned_to: "",
    expected_return: "",
  });
  const [photo, setPhoto] = useState(null);
  const [photoError, setPhotoError] = useState("");
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (asset) return;
    api("/api/users/choices")
      .then(setPeople)
      .catch(() => setPeople([]));
  }, [asset]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const found = validateAsset(values);
    setErrors(found);
    if (Object.keys(found).length) return;

    const data = {
      name: values.name.trim(),
      category_id: values.category_id ? Number(values.category_id) : null,
      serial_number: values.serial_number.trim() || null,
      purchase_date: values.purchase_date || null,
      purchase_cost: values.purchase_cost ? Number(values.purchase_cost).toFixed(2) : null,
      condition: values.condition,
      notes: values.notes.trim() || null,
    };
    if (!asset) {
      data.assigned_to = values.assigned_to ? Number(values.assigned_to) : null;
      data.expected_return = values.assigned_to ? values.expected_return || null : null;
    }
    setBusy(true);
    const result = await dispatch(assets.saveItem({ id: asset?.id, data }));
    if (assets.saveItem.fulfilled.match(result)) {
      let saved = result.payload;
      if (photo) {
        try {
          saved = await upload(`/api/assets/${saved.id}/photo`, photo);
        } catch (error) {
          setPhotoError(`The asset was saved, but the photo was not: ${error.message}`);
          setBusy(false);
          return;
        }
      }
      onSaved(saved);
    } else {
      setBusy(false);
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
      className="card grid gap-5 p-6 sm:grid-cols-4"
    >
      <h2 className="text-lg font-semibold sm:col-span-4">
        {asset ? `Edit ${asset.asset_code}` : "Register an asset"}
      </h2>
      {formError && (
        <p role="alert" className="text-sm text-danger sm:col-span-4">
          {formError}
        </p>
      )}
      <div className="sm:col-span-2">
        <Field
          label="Name"
          name="name"
          placeholder="Dell Latitude 5440 laptop"
          value={values.name}
          onChange={handleChange}
          error={errors.name}
        />
      </div>
      <Field label="Category" name="category_id" error={errors.category_id}>
        {(id) => (
          <select
            id={id}
            name="category_id"
            value={values.category_id}
            onChange={handleChange}
            className="input px-2"
          >
            <option value="">None</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field
        label="Serial number"
        name="serial_number"
        value={values.serial_number}
        onChange={handleChange}
        error={errors.serial_number}
      />
      <Field
        label="Bought on"
        name="purchase_date"
        type="date"
        max={isoToday()}
        value={values.purchase_date}
        onChange={handleChange}
        error={errors.purchase_date}
      />
      <Field
        label={`Cost (${currencyCode()})`}
        name="purchase_cost"
        inputMode="decimal"
        value={values.purchase_cost}
        onChange={handleChange}
        error={errors.purchase_cost}
      />
      <Field label="Condition" name="condition" error={errors.condition}>
        {(id) => (
          <select
            id={id}
            name="condition"
            value={values.condition}
            onChange={handleChange}
            className="input px-2"
          >
            {CONDITIONS.map((value) => (
              <option key={value} value={value}>
                {conditionLabel(value)}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field
        label="Notes"
        name="notes"
        value={values.notes}
        onChange={handleChange}
        error={errors.notes}
      />
      {!asset && (
        <>
          <div className="sm:col-span-2">
            <Field label="Hand it to (optional)" name="assigned_to" error={errors.assigned_to}>
              {(id) => (
                <select
                  id={id}
                  name="assigned_to"
                  value={values.assigned_to}
                  onChange={handleChange}
                  className="input px-2"
                >
                  <option value="">Nobody yet</option>
                  {people.map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.full_name} · {ROLE_NAMES[person.role] || person.role}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          </div>
          <Field
            label="Expected back"
            name="expected_return"
            type="date"
            min={isoToday()}
            disabled={!values.assigned_to}
            value={values.expected_return}
            onChange={handleChange}
            error={errors.expected_return}
          />
        </>
      )}
      <div className="sm:col-span-4">
        <PhotoPicker
          currentUrl={asset?.image_url}
          file={photo}
          onPick={(file) => {
            const problem = checkPhoto(file);
            setPhotoError(problem);
            setPhoto(problem ? null : file);
          }}
          error={photoError}
        />
      </div>
      <div className="flex gap-2 sm:col-span-4">
        <button type="submit" disabled={busy} className="btn-primary">
          {busy ? "Saving…" : "Save asset"}
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  );
}
