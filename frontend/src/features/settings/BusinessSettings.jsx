import { useEffect, useState } from "react";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import Field from "../../components/Field";
import Icon from "../../components/Icon";

const firstMessages = (details = {}) =>
  Object.fromEntries(Object.entries(details).map(([key, list]) => [key, [].concat(list)[0]]));

const ZONES =
  typeof Intl.supportedValuesOf === "function"
    ? Intl.supportedValuesOf("timeZone")
    : ["Africa/Nairobi", "Africa/Kampala", "Africa/Dar_es_Salaam", "Africa/Kigali", "UTC"];

// Invite staff: the join code and a link that fills it in for them.
function JoinCode({ code, onNewCode }) {
  const [copied, setCopied] = useState("");
  const [busy, setBusy] = useState(false);
  const link = `${window.location.origin}/register?code=${code}`;

  const copy = async (text, what) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
    } catch {
      setCopied("");
    }
  };

  const regenerate = async () => {
    if (!window.confirm("Make a new join code? The old code and invite link stop working.")) return;
    setBusy(true);
    try {
      const result = await api("/api/business/join-code", { method: "POST" });
      onNewCode(result.join_code);
      setCopied("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-dashed border-line-strong bg-surface-2 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">Invite your staff</p>
          <p className="text-xs text-muted">
            They sign up with this code and start as Employee. Change their role under Users.
          </p>
        </div>
        <span className="code text-lg tracking-[0.2em]" data-testid="join-code">
          {code}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-secondary" onClick={() => copy(code, "code")}>
          {copied === "code" ? "Code copied" : "Copy code"}
        </button>
        <button type="button" className="btn-secondary" onClick={() => copy(link, "link")}>
          {copied === "link" ? "Link copied" : "Copy invite link"}
        </button>
        <button type="button" className="btn-ghost" disabled={busy} onClick={regenerate}>
          <Icon name="lock" size={16} /> New code
        </button>
      </div>
    </div>
  );
}

export default function BusinessSettings() {
  const { user, reloadUser } = useAuth();
  const isAdmin = user.role === "admin";
  const [business, setBusiness] = useState(null);
  const [values, setValues] = useState(null);
  const [errors, setErrors] = useState({});
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/business")
      .then((data) => {
        setBusiness(data);
        setValues({
          name: data.name,
          timezone: data.timezone,
          currency: data.currency,
          vat_rate: data.vat_rate,
          phone: data.phone || "",
          email: data.email || "",
          address: data.address || "",
          receipt_footer: data.receipt_footer || "",
        });
      })
      .catch(() => setBusiness(false));
  }, []);

  if (business === null) {
    return <div className="card h-28 animate-pulse" aria-label="Loading business" />;
  }
  if (business === false) return null;

  if (!isAdmin) {
    return (
      <section aria-labelledby="business-title" className="card flex items-center gap-4 p-6">
        <span className="grid size-11 place-items-center rounded-xl bg-mint text-brand-dark">
          <Icon name="building" />
        </span>
        <div>
          <h2 id="business-title" className="text-lg font-bold">
            {business.name}
          </h2>
          <p className="text-sm text-muted">
            Prices in {business.currency} · VAT {Number(business.vat_rate)}% · {business.timezone}
          </p>
        </div>
      </section>
    );
  }

  const change = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({
      ...current,
      [name]: name === "currency" ? value.toUpperCase() : value,
    }));
    setErrors((current) => ({ ...current, [name]: undefined }));
    setSaved("");
  };

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setSaved("");
    try {
      const body = { ...values };
      for (const key of ["phone", "email", "address", "receipt_footer"])
        body[key] = body[key] || null;
      const fresh = await api("/api/business", { method: "PUT", body });
      setBusiness(fresh);
      await reloadUser();
      setSaved("Business settings saved.");
    } catch (err) {
      const fields = firstMessages(err.details);
      setErrors(Object.keys(fields).length ? fields : { form: err.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-labelledby="business-title"
      className="card flex flex-col gap-5 p-6"
    >
      <div className="flex items-center gap-3">
        <span className="grid size-11 place-items-center rounded-xl bg-mint text-brand-dark">
          <Icon name="building" />
        </span>
        <div>
          <h2 id="business-title" className="text-lg font-bold">
            Business
          </h2>
          <p className="text-sm text-muted">
            Printed on receipts and used for every date, price and report.
          </p>
        </div>
      </div>
      <JoinCode
        code={business.join_code}
        onNewCode={(join_code) => setBusiness((current) => ({ ...current, join_code }))}
      />
      <div className="grid gap-4 md:grid-cols-2">
        <Field
          label="Business name"
          name="name"
          value={values.name}
          onChange={change}
          error={errors.name}
        />
        <Field label="Time zone" name="timezone" error={errors.timezone}>
          {(id) => (
            <select
              id={id}
              name="timezone"
              className="input"
              value={values.timezone}
              onChange={change}
            >
              {ZONES.map((zone) => (
                <option key={zone}>{zone}</option>
              ))}
            </select>
          )}
        </Field>
        <Field
          label="Currency (3 letters)"
          name="currency"
          maxLength={3}
          value={values.currency}
          onChange={change}
          error={errors.currency}
        />
        <Field
          label="VAT included in prices (%)"
          name="vat_rate"
          type="number"
          min="0"
          max="99"
          step="0.01"
          value={values.vat_rate}
          onChange={change}
          error={errors.vat_rate}
        />
        <Field
          label="Phone"
          name="phone"
          type="tel"
          value={values.phone}
          onChange={change}
          error={errors.phone}
        />
        <Field
          label="Email"
          name="email"
          type="email"
          value={values.email}
          onChange={change}
          error={errors.email}
        />
        <Field
          label="Address"
          name="address"
          value={values.address}
          onChange={change}
          error={errors.address}
        />
        <Field
          label="Receipt footer"
          name="receipt_footer"
          placeholder="Thank you for shopping with us!"
          value={values.receipt_footer}
          onChange={change}
          error={errors.receipt_footer}
        />
      </div>
      {errors.form && (
        <p role="alert" className="text-sm text-danger">
          {errors.form}
        </p>
      )}
      {saved && (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {saved}
        </p>
      )}
      <button type="submit" disabled={busy} className="btn-primary self-start">
        Save business settings
      </button>
    </form>
  );
}
