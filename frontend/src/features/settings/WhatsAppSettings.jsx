import { useEffect, useState } from "react";

import { api } from "../../api/client";
import Field from "../../components/Field";
import Icon from "../../components/Icon";

export default function WhatsAppSettings() {
  const [values, setValues] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/business/whatsapp")
      .then((data) => setValues({ ...data, whatsapp_number: data.whatsapp_number || "" }))
      .catch((err) => setError(err.message));
  }, []);

  if (!values) return null;

  const save = async (event) => {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const data = await api("/api/business/whatsapp", {
        method: "PUT",
        body: {
          whatsapp_number: values.whatsapp_number.trim() || null,
          whatsapp_alerts: values.whatsapp_alerts,
        },
      });
      setValues({ ...data, whatsapp_number: data.whatsapp_number || "" });
      setMessage("Saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setMessage("");
    setError("");
    try {
      await api("/api/business/whatsapp/test", { method: "POST" });
      setMessage(
        values.connected
          ? "Test message sent. It should arrive in a few seconds."
          : "WhatsApp isn't connected on the server yet, so the test was only recorded.",
      );
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <form
      onSubmit={save}
      noValidate
      aria-labelledby="whatsapp-title"
      className="card flex flex-col gap-5 p-6"
    >
      <div className="flex items-center gap-3">
        <span className="grid size-11 place-items-center rounded-xl bg-mint text-brand-dark">
          <Icon name="bell" />
        </span>
        <div>
          <h2 id="whatsapp-title" className="text-lg font-bold">
            WhatsApp alerts
          </h2>
          <p className="text-sm text-muted">
            Get a WhatsApp message when a product runs low, and in the evening if cash is likely to
            run short.
          </p>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="WhatsApp number"
          name="whatsapp-number"
          type="tel"
          placeholder="0712 345 678"
          value={values.whatsapp_number}
          onChange={(event) =>
            setValues((current) => ({ ...current, whatsapp_number: event.target.value }))
          }
        />
        <label className="flex items-center gap-3 self-end pb-2.5 text-sm font-medium">
          <input
            type="checkbox"
            checked={values.whatsapp_alerts}
            onChange={(event) =>
              setValues((current) => ({ ...current, whatsapp_alerts: event.target.checked }))
            }
            className="size-4"
          />
          Send alerts to this number
        </label>
      </div>
      {!values.connected && (
        <p className="text-xs text-muted">
          WhatsApp sending isn't set up on the server yet. Until it is, alerts are only recorded.
        </p>
      )}
      {message && (
        <p role="status" className="text-sm text-brand-dark">
          {message}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <button type="submit" disabled={busy} className="btn-primary">
          Save
        </button>
        {values.whatsapp_alerts && values.whatsapp_number && (
          <button type="button" onClick={test} className="btn-secondary">
            Send a test message
          </button>
        )}
      </div>
    </form>
  );
}
