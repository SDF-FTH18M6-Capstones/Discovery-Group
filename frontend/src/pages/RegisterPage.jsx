import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import Field from "../components/Field";

export function validateRegistration(values) {
  const errors = {};
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

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [values, setValues] = useState({ full_name: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const found = validateRegistration(values);
    setErrors(found);
    setFormError("");
    if (Object.keys(found).length) return;
    try {
      const { full_name, email, password } = values;
      const result = await register({ full_name, email, password });
      navigate("/login", { state: { message: result.message, email } });
    } catch (error) {
      setFormError(error.message);
      const flat = Object.fromEntries(
        Object.entries(error.details || {}).map(([key, list]) => [key, [].concat(list)[0]]),
      );
      setErrors(flat);
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="page-title">Create an account</h1>
        <p className="text-sm text-muted">
          New accounts start as Employee. An administrator can change your role.
        </p>
      </div>
      {formError && (
        <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {formError}
        </p>
      )}
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <Field
          label="Full name"
          name="full_name"
          value={values.full_name}
          onChange={handleChange}
          error={errors.full_name}
        />
        <Field
          label="Email"
          name="email"
          type="email"
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
        <button type="submit" className="btn-primary mt-2 min-h-11">
          Create account
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
