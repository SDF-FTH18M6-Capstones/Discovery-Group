import { useState } from "react";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { ROLE_NAMES } from "../../auth/roles";
import Field from "../../components/Field";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import { Avatar } from "../../components/ui";
import { useTheme } from "../../theme/ThemeContext";
import BusinessSettings from "./BusinessSettings";

const firstMessages = (details = {}) =>
  Object.fromEntries(
    Object.entries(details).map(([key, messages]) => [key, [].concat(messages)[0]]),
  );

function ProfileForm() {
  const { user, updateUser } = useAuth();
  const [name, setName] = useState(user.full_name);
  const [phone, setPhone] = useState(user.phone || "");
  const [phoneError, setPhoneError] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setSaved("");
    if (name.trim().length < 2) {
      setError("Enter your full name.");
      return;
    }
    setBusy(true);
    try {
      const fresh = await api("/api/auth/me", {
        method: "PUT",
        body: { full_name: name.trim(), phone: phone.trim() || null },
      });
      updateUser(fresh);
      setSaved("Profile saved.");
    } catch (err) {
      const fields = firstMessages(err.details);
      setPhoneError(fields.phone || "");
      setError(fields.full_name || (fields.phone ? "" : err.message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-labelledby="profile-title"
      className="card flex flex-col gap-5 p-6"
    >
      <div className="-mx-6 -mt-6 flex items-center gap-4 rounded-t-2xl border-b border-line bg-surface-2 px-6 py-5">
        <Avatar name={user.full_name} size={56} />
        <div className="min-w-0">
          <h2 id="profile-title" className="text-lg font-bold">
            My profile
          </h2>
          <p className="truncate text-sm text-muted">
            {ROLE_NAMES[user.role] || user.role}, {user.email}
          </p>
        </div>
      </div>
      <Field
        label="Full name"
        name="full_name"
        value={name}
        onChange={(event) => {
          setName(event.target.value);
          setError("");
        }}
        error={error}
      />
      <Field
        label="Phone (optional)"
        name="phone"
        type="tel"
        autoComplete="tel"
        placeholder="+254 712 345678"
        value={phone}
        onChange={(event) => {
          setPhone(event.target.value);
          setPhoneError("");
        }}
        error={phoneError}
      />
      <p className="text-xs text-muted">Your email and role are set by an administrator.</p>
      {saved && (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {saved}
        </p>
      )}
      <button type="submit" disabled={busy} className="btn-primary self-start">
        Save profile
      </button>
    </form>
  );
}

function PasswordForm() {
  const empty = { current_password: "", new_password: "", confirm: "" };
  const [values, setValues] = useState(empty);
  const [errors, setErrors] = useState({});
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);

  const update = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined, form: undefined }));
  };

  const submit = async (event) => {
    event.preventDefault();
    setSaved("");
    const found = {};
    if (!values.current_password) found.current_password = "Enter your current password.";
    if (!/^(?=.*[A-Za-z])(?=.*\d).{8,}$/.test(values.new_password))
      found.new_password = "Use at least 8 characters with letters and numbers.";
    if (values.confirm !== values.new_password) found.confirm = "The passwords do not match.";
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    try {
      await api("/api/auth/password", {
        method: "POST",
        body: { current_password: values.current_password, new_password: values.new_password },
      });
      setValues(empty);
      setSaved("Password changed.");
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
      aria-labelledby="password-title"
      className="card flex flex-col gap-5 p-6"
    >
      <h2 id="password-title" className="text-lg font-bold">
        Change password
      </h2>
      <Field
        label="Current password"
        name="current_password"
        type="password"
        autoComplete="current-password"
        value={values.current_password}
        onChange={update}
        error={errors.current_password}
      />
      <Field
        label="New password"
        name="new_password"
        type="password"
        autoComplete="new-password"
        value={values.new_password}
        onChange={update}
        error={errors.new_password}
      />
      <Field
        label="Confirm new password"
        name="confirm"
        type="password"
        autoComplete="new-password"
        value={values.confirm}
        onChange={update}
        error={errors.confirm}
      />
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
        Change password
      </button>
    </form>
  );
}

const THEMES = [
  { value: "light", label: "Light", icon: "sun" },
  { value: "dark", label: "Dark", icon: "moon" },
  { value: "system", label: "Same as my device", icon: "settings" },
];

function Preview({ value }) {
  const half = (bg, card, line) => (
    <span className="flex flex-1 gap-1 p-1.5" style={{ background: bg }}>
      <span className="w-3 rounded-sm" style={{ background: "#0d3b33" }} />
      <span className="flex flex-1 flex-col gap-1">
        <span className="h-2 w-2/3 rounded-sm" style={{ background: line }} />
        <span className="flex-1 rounded-sm" style={{ background: card }} />
      </span>
    </span>
  );
  return (
    <span aria-hidden="true" className="flex h-16 overflow-hidden rounded-lg ring-1 ring-line">
      {value !== "dark" && half("#f4f6f3", "#ffffff", "#c9d3cd")}
      {value !== "light" && half("#0b1a17", "#10231f", "#2d524a")}
    </span>
  );
}

function Appearance() {
  const { choice, choose } = useTheme();
  return (
    <fieldset className="card flex flex-col gap-4 p-6">
      <legend className="sr-only">Appearance</legend>
      <h2 aria-hidden="true" className="text-lg font-bold">
        Appearance
      </h2>
      <div className="grid gap-3 sm:grid-cols-3">
        {THEMES.map((theme) => (
          <label
            key={theme.value}
            className={`flex cursor-pointer flex-col gap-3 rounded-xl border p-3 text-sm transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-saffron ${
              choice === theme.value
                ? "border-brand bg-mint font-semibold text-brand-dark"
                : "border-line-strong hover:border-brand"
            }`}
          >
            <Preview value={theme.value} />
            <span className="flex items-center gap-2">
              <input
                type="radio"
                name="theme"
                value={theme.value}
                checked={choice === theme.value}
                onChange={() => choose(theme.value)}
                className="accent-[var(--sp-brand)]"
              />
              <Icon name={theme.icon} size={16} />
              {theme.label}
            </span>
          </label>
        ))}
      </div>
      <p className="text-xs text-muted">Saved in this browser.</p>
    </fieldset>
  );
}

export default function SettingsPage() {
  return (
    <section className="flex flex-col gap-6">
      <PageHeader
        title="Settings"
        subtitle="Your business, your profile, your password and how StockPilot looks."
      />
      <BusinessSettings />
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          <ProfileForm />
          <Appearance />
        </div>
        <PasswordForm />
      </div>
    </section>
  );
}
