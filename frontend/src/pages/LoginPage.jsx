import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import Field from "../components/Field";

// Two steps on one page: email + password, then the 6-digit code from the email.
export default function LoginPage() {
  const { signIn, verifyCode, sessionExpired } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [step, setStep] = useState("password");
  const [values, setValues] = useState({ email: "", password: "", code: "" });
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState(
    sessionExpired ? "Your session has expired. Please sign in again." : "",
  );
  const [busy, setBusy] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const submitPassword = async (event) => {
    event.preventDefault();
    const found = {};
    if (!/^\S+@\S+\.\S+$/.test(values.email)) found.email = "Enter your email address.";
    if (!values.password) found.password = "Enter your password.";
    setErrors(found);
    if (Object.keys(found).length) return;

    setBusy(true);
    setMessage("");
    try {
      const result = await signIn(values.email, values.password);
      setStep("code");
      // dev_code only comes back when the backend runs with DEV_SHOW_OTP=true (local only).
      setValues((current) => ({ ...current, code: result.dev_code || "" }));
      setMessage(result.message);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const submitCode = async (event) => {
    event.preventDefault();
    if (!/^\d{6}$/.test(values.code)) {
      setErrors({ code: "Enter the 6-digit code from the email." });
      return;
    }
    setBusy(true);
    try {
      await verifyCode(values.email, values.code);
      navigate(location.state?.from || "/products", { replace: true });
    } catch (error) {
      setMessage(error.message);
      setBusy(false);
    }
  };

  return (
    <section className="mx-auto flex max-w-sm flex-col gap-4 py-10">
      <h1 className="text-2xl font-bold">Sign in</h1>
      <p className="text-sm text-muted">
        {step === "password" ? "Step 1 of 2" : "Step 2 of 2: check your email"}
      </p>
      {message && (
        <p role="status" className="rounded-lg bg-mint p-3 text-sm">
          {message}
        </p>
      )}

      {step === "password" ? (
        <form onSubmit={submitPassword} noValidate className="flex flex-col gap-4">
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
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-brand px-4 py-2 font-semibold text-white disabled:opacity-60"
          >
            {busy ? "Checking…" : "Continue"}
          </button>
          <p className="text-sm">
            New here?{" "}
            <Link to="/register" className="text-brand-dark underline">
              Create an account
            </Link>
          </p>
        </form>
      ) : (
        <form onSubmit={submitCode} noValidate className="flex flex-col gap-4">
          <Field
            label="6-digit code"
            name="code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={values.code}
            onChange={handleChange}
            error={errors.code}
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-brand px-4 py-2 font-semibold text-white disabled:opacity-60"
          >
            {busy ? "Signing in…" : "Verify and sign in"}
          </button>
          <button
            type="button"
            onClick={() => {
              setStep("password");
              setMessage("");
            }}
            className="text-sm text-brand-dark underline"
          >
            Use a different account
          </button>
        </form>
      )}
    </section>
  );
}