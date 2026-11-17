import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import Field from "../components/Field";

export default function LoginPage() {
  const { signIn, sessionExpired } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [values, setValues] = useState({ email: location.state?.email || "", password: "" });
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState(
    location.state?.message ||
      (sessionExpired ? "Your session has expired. Please sign in again." : ""),
  );
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const found = {};
    if (!/^\S+@\S+\.\S+$/.test(values.email)) found.email = "Enter your email address.";
    if (!values.password) found.password = "Enter your password.";
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    setMessage("");
    setFormError("");
    try {
      await signIn(values.email, values.password);
      navigate(location.state?.from || "/", { replace: true });
    } catch (error) {
      setFormError(error.message);
      setBusy(false);
    }
  };

  return (
    <section className="flex flex-col gap-4">
      <h1 className="page-title">Sign in</h1>
      {message && (
        <p role="status" className="rounded-lg bg-mint p-3 text-sm">
          {message}
        </p>
      )}
      {formError && (
        <p role="alert" className="rounded-lg bg-danger-soft p-3 text-sm text-danger">
          {formError}
        </p>
      )}
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <Field
          label="Email"
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
          autoComplete="current-password"
          value={values.password}
          onChange={handleChange}
          error={errors.password}
        />
        <button type="submit" disabled={busy} className="btn-primary">
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="text-sm">
          New here?{" "}
          <Link to="/register" className="text-brand-dark underline">
            Create an account
          </Link>
        </p>
      </form>
    </section>
  );
}
