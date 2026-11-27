import { useEffect, useState } from "react";

import { api } from "../../api/client";
import Field from "../../components/Field";
import Icon from "../../components/Icon";

const MODES = [
  ["off", "Off", "Record M-Pesa sales by hand."],
  ["simulate", "Test mode", "Practise the flow; no real prompt is sent."],
  ["sandbox", "Safaricom sandbox", "Real prompts from Safaricom's test system."],
  ["live", "Live", "Real payments into your own Paybill or till."],
];

const BLANK_SECRETS = { passkey: "", consumer_key: "", consumer_secret: "" };

export default function MpesaSettings() {
  const [values, setValues] = useState(null);
  const [saved, setSaved] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/business/mpesa")
      .then((data) => {
        setSaved(data);
        setValues({
          ...data,
          shortcode: data.shortcode || "",
          till: data.till || "",
          ...BLANK_SECRETS,
        });
      })
      .catch((err) => setError(err.message));
  }, []);

  if (!values) {
    return error ? (
      <p role="alert" className="card p-6 text-danger">
        {error}
      </p>
    ) : null;
  }

  const online = values.mode === "sandbox" || values.mode === "live";

  const change = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setMessage("");
    setError("");
  };

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const data = await api("/api/business/mpesa", {
        method: "PUT",
        body: {
          mode: values.mode,
          type: values.type,
          shortcode: values.shortcode || null,
          till: values.type === "till" ? values.till || null : null,
          ...Object.fromEntries(Object.keys(BLANK_SECRETS).map((key) => [key, values[key]])),
        },
      });
      setSaved(data);
      setValues((current) => ({ ...current, ...BLANK_SECRETS, mode: data.mode }));
      setMessage("M-Pesa settings saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const secretHint = (present) => (present ? "Saved. Leave empty to keep it." : undefined);

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-labelledby="mpesa-title"
      className="card flex flex-col gap-5 p-6"
    >
      <div className="flex items-center gap-3">
        <span className="grid size-11 place-items-center rounded-xl bg-mint text-brand-dark">
          <Icon name="phone" />
        </span>
        <div>
          <h2 id="mpesa-title" className="text-lg font-bold">
            M-Pesa at the till
          </h2>
          <p className="text-sm text-muted">
            Customers pay into your own Paybill or till; StockPilot never holds the money.
          </p>
        </div>
      </div>

      <fieldset className="grid gap-2 sm:grid-cols-2">
        <legend className="mb-2 text-sm font-medium text-ink-2">How the till takes M-Pesa</legend>
        {MODES.map(([value, label, hint]) => (
          <label
            key={value}
            className={`flex cursor-pointer gap-3 rounded-xl border p-3 text-sm ${
              values.mode === value ? "border-brand bg-mint" : "border-line-strong"
            }`}
          >
            <input
              type="radio"
              name="mode"
              value={value}
              checked={values.mode === value}
              onChange={change}
              className="mt-0.5 accent-[var(--sp-brand)]"
            />
            <span>
              <span className="font-semibold">{label}</span>
              <span className="block text-muted">{hint}</span>
            </span>
          </label>
        ))}
      </fieldset>

      {online && (
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Account type" name="type">
            {(id) => (
              <select
                id={id}
                name="type"
                value={values.type}
                onChange={change}
                className="input px-2"
              >
                <option value="paybill">Paybill</option>
                <option value="till">Buy Goods till</option>
              </select>
            )}
          </Field>
          <Field
            label={values.type === "till" ? "Store number" : "Paybill number"}
            name="shortcode"
            inputMode="numeric"
            value={values.shortcode}
            onChange={change}
          />
          {values.type === "till" && (
            <Field
              label="Till number"
              name="till"
              inputMode="numeric"
              value={values.till}
              onChange={change}
            />
          )}
          <Field
            label="Passkey"
            name="passkey"
            type="password"
            autoComplete="off"
            placeholder={secretHint(saved.has_passkey)}
            value={values.passkey}
            onChange={change}
          />
          <Field
            label="Consumer key"
            name="consumer_key"
            type="password"
            autoComplete="off"
            placeholder={secretHint(saved.has_keys)}
            value={values.consumer_key}
            onChange={change}
          />
          <Field
            label="Consumer secret"
            name="consumer_secret"
            type="password"
            autoComplete="off"
            placeholder={secretHint(saved.has_keys)}
            value={values.consumer_secret}
            onChange={change}
          />
          <p className="text-xs text-muted md:col-span-2">
            Get these from your app on developer.safaricom.co.ke. They are stored encrypted and
            never shown again.
          </p>
        </div>
      )}

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {message}
        </p>
      )}
      <button type="submit" disabled={busy} className="btn-primary self-start">
        Save M-Pesa settings
      </button>
    </form>
  );
}
