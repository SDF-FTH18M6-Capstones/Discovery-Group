import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import Field from "../components/Field";

export function validateRegistration(values, mode = "join") {
  const errors = {};
  if (mode === "business" && values.business_name.trim().length < 2) {
    errors.business_name = "Enter the business name.";
  }
  if (mode === "join" && values.join_code.trim().length < 4) {
    errors.join_code = "Enter the join code your manager gave you.";
  }
  if (values.full_name.trim().length < 2) errors.full_name = "Enter your full name.";
  if (!/^\S+@\S+\.\S+$/.test(values.email)) errors.email = "Enter a valid email.";
  if (
    values.password.length < 8 ||
    !/[A-Za-z]/.test(values.password) ||
    !/\d/.test(values.password)
  ) {
    errors.password = "Use at least 8 characters with letters and numbers.";
  }
  if (values.confirm !== values.password) errors.confirm = "The passwords do not match.";
  return errors;
}

const firstOf = (details = {}) =>
  Object.fromEntries(Object.entries(details).map(([key, list]) => [key, [].concat(list)[0]]));

export default function RegisterPage({ startMode }) {
  const { register, registerBusiness } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [mode, setMode] = useState(startMode || (params.get("start") ? "business" : "join"));
  const [values, setValues] = useState({
    business_name: "",
    join_code: (params.get("code") || "").toUpperCase(),
    full_name: "",
    email: "",
    password: "",
    confirm: "",
  });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({
      ...current,
      [name]: name === "join_code" ? value.toUpperCase() : value,
    }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const found = validateRegistration(values, mode);
    setErrors(found);
    setFormError("");
    if (Object.keys(found).length) return;
    setBusy(true);
    const { full_name, email, password } = values;
    try {
      if (mode === "business") {
        const result = await registerBusiness({
          business_name: values.business_name,
          full_name,
          email,
          password,
        });
        if (result.message) navigate("/login", { state: { message: result.message, email } });
        else navigate("/", { replace: true, state: { welcome: true } });
      } else {
        const result = await register({ full_name, email, password, join_code: values.join_code });
        navigate("/login", { state: { message: result.message, email } });
      }
    } catch (error) {
      setFormError(error.message);
      setErrors(firstOf(error.details));
      setBusy(false);
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="page-title">
          {mode === "business" ? "Start your business" : "Join your team"}
        </h1>
        <p className="text-sm text-muted">
          {mode === "business"
            ? "Set up StockPilot for your shop. You become its Administrator and can invite your staff."
            : "Use the join code from your manager. New accounts start as Employee; an administrator can change your role."}
        </p>
      </div>
      <div className="seg grid grid-cols-2" role="group" aria-label="How are you joining?">
        {[
          ["join", "Join a business"],
          ["business", "New business"],
        ].map(([key, text]) => (
          <button
            key={key}
            type="button"
            aria-pressed={mode === key}
            onClick={() => {
              setMode(key);
              setErrors({});
              setFormError("");
            }}
          >
            {text}
          </button>
        ))}
      </div>
      {formError && (
        <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {formError}
        </p>
      )}
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        {mode === "business" ? (
          <Field
            label="Business name"
            name="business_name"
            autoComplete="organization"
            value={values.business_name}
            onChange={handleChange}
            error={errors.business_name}
          />
        ) : (
          <Field
            label="Join code"
            name="join_code"
            autoComplete="off"
            placeholder="e.g. K7M2QX9P"
            value={values.join_code}
            onChange={handleChange}
            error={errors.join_code}
          />
        )}
        <Field
          label="Full name"
          name="full_name"
          autoComplete="name"
          value={values.full_name}
          onChange={handleChange}
          error={errors.full_name}
        />
        <Field
          label={mode === "business" ? "Your work email" : "Email"}
          name="email"
          type="email"
          autoComplete="email"
          value={values.email}
          onChange={handleChange}
          error={errors.email}
        />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          value={values.password}
          onChange={handleChange}
          error={errors.password}
        />
        <Field
          label="Confirm password"
          name="confirm"
          type="password"
          autoComplete="new-password"
          value={values.confirm}
          onChange={handleChange}
          error={errors.confirm}
        />
        <button type="submit" disabled={busy} className="btn-primary mt-2 min-h-11">
          {busy ? "Please wait…" : mode === "business" ? "Create business" : "Create account"}
        </button>
        <p className="border-t border-line pt-4 text-center text-sm text-muted">
          Already have an account?{" "}
          <Link to="/login" className="link">
            Sign in
          </Link>
        </p>
      </form>
    </section>
  );
}
