import { useState } from "react";
import { useDispatch } from "react-redux";

import Field from "../../components/Field";
import { requests } from "../../store";

export const URGENCIES = ["low", "normal", "high", "urgent"];

export function validateRequest(values) {
  const errors = {};
  if (!values.item.trim()) errors.item = "Say what you need.";
  if (!/^\d+$/.test(String(values.quantity)) || Number(values.quantity) < 1)
    errors.quantity = "Enter a whole number of 1 or more.";
  if (!values.reason.trim()) errors.reason = "Say why you need it.";
  return errors;
}

export default function RequestForm({ request, onSaved, onCancel }) {
  const dispatch = useDispatch();
  const [values, setValues] = useState({
    item: request?.item || "",
    quantity: request?.quantity ?? 1,
    urgency: request?.urgency || "normal",
    reason: request?.reason || "",
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
    const found = validateRequest(values);
    setErrors(found);
    if (Object.keys(found).length) return;

    const data = {
      item: values.item.trim(),
      quantity: Number(values.quantity),
      urgency: values.urgency,
      reason: values.reason.trim(),
    };
    const result = await dispatch(requests.saveItem({ id: request?.id, data }));
    if (requests.saveItem.fulfilled.match(result)) {
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
      aria-label={request ? "Edit request" : "New request"}
      className="card grid gap-4 p-5 sm:grid-cols-4"
    >
      {formError && (
        <p role="alert" className="text-sm text-danger sm:col-span-4">
          {formError}
        </p>
      )}
      <div className="sm:col-span-2">
        <Field
          label="What do you need?"
          name="item"
          value={values.item}
          onChange={handleChange}
          error={errors.item}
        />
      </div>
      <Field
        label="Quantity"
        name="quantity"
        type="number"
        min="1"
        value={values.quantity}
        onChange={handleChange}
        error={errors.quantity}
      />
      <Field label="Urgency" name="urgency" error={errors.urgency}>
        {(id) => (
          <select
            id={id}
            name="urgency"
            value={values.urgency}
            onChange={handleChange}
            className="input px-2"
          >
            {URGENCIES.map((urgency) => (
              <option key={urgency} value={urgency}>
                {urgency.charAt(0).toUpperCase() + urgency.slice(1)}
              </option>
            ))}
          </select>
        )}
      </Field>
      <div className="sm:col-span-4">
        <Field label="Reason" name="reason" error={errors.reason}>
          {(id) => (
            <textarea
              id={id}
              name="reason"
              rows="2"
              value={values.reason}
              onChange={handleChange}
              aria-invalid={Boolean(errors.reason)}
              className={`rounded-lg border px-3 py-2 ${errors.reason ? "border-danger" : "border-line"}`}
            />
          )}
        </Field>
      </div>
      <div className="flex gap-2 sm:col-span-4">
        <button type="submit" className="btn-primary">
          {request ? "Save changes" : "Submit request"}
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  );
}
