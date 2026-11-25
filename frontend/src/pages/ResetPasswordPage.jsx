import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import Field from "../components/Field";

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") || "";
  const [values, setValues] = useState({ password: "", confirm: "" });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);

  const change = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const found = {};
    if (
      values.password.length < 8 ||
      !/[A-Za-z]/.test(values.password) ||
      !/\d/.test(values.password)
    ) {
      found.password = "Use at least 8 characters with letters and numbers.";
    }
    if (values.confirm !== values.password) found.confirm = "The passwords do not match.";
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      const result = await api("/api/auth/reset-password", {
        method: "POST",
        body: { token, password: values.password },
        auth: false,
      });
      navigate("/login", { replace: true, state: { message: result.message } });
    } catch (problem) {
      setFormError(problem.message);
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <section className="flex flex-col gap-4">
        <h1 className="page-title">Link incomplete</h1>
        <p className="text-sm text-muted">
          Open the link from the email exactly as it was sent, or ask for a new one.
        </p>
        <Link to="/forgot-password" className="btn-primary">
          Ask for a new link
        </Link>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="page-title">Choose a new password</h1>
        <p className="text-sm text-muted">
          After this you will be signed out on every other device.
        </p>
      </div>
      {formError && (
        <div
          role="alert"
          className="flex flex-col gap-2 rounded-xl bg-danger-soft p-3 text-sm text-danger"
        >
          {formError}
          <Link to="/forgot-password" className="link font-semibold">
            Send me a new link
          </Link>
        </div>
      )}
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <Field
          label="New password"
          name="password"
          type="password"
          autoComplete="new-password"
          value={values.password}
          onChange={change}
          error={errors.password}
        />
        <Field
          label="Confirm new password"
          name="confirm"
          type="password"
          autoComplete="new-password"
          value={values.confirm}
          onChange={change}
          error={errors.confirm}
        />
        <button type="submit" disabled={busy} className="btn-primary min-h-11">
          {busy ? "Saving…" : "Save new password"}
        </button>
      </form>
    </section>
  );
}
