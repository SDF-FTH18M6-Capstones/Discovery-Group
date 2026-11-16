import { useState } from "react";
import { Link } from "react-router-dom";

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
  const [values, setValues] = useState({ full_name: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [done, setDone] = useState("");

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
      setDone(result.message);
    } catch (error) {
      setFormError(error.message);
      const flat = Object.fromEntries(
        Object.entries(error.details || {}).map(([key, list]) => [key, [].concat(list)[0]]),
      );
      setErrors(flat);
    }
  };

  if (done) {
    return (
      <section className="mx-auto flex max-w-sm flex-col gap-4 py-10">
        <h1 className="text-2xl font-bold">Check your email</h1>
        <p role="status" className="rounded-lg bg-mint p-3 text-sm">
          {done}
        </p>
        <Link to="/login" className="text-brand-dark underline">
          Go to sign in
        </Link>
      </section>
    );
  }

  return (
    <section className="mx-auto flex max-w-sm flex-col gap-4 py-10">
      <h1 className="text-2xl font-bold">Create an account</h1>
      {formError && (
        <p role="alert" className="rounded-lg bg-orange-50 p-3 text-sm text-danger">
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
        <button type="submit" className="rounded-lg bg-brand px-4 py-2 font-semibold text-white">
          Create account
        </button>
        <p className="text-sm">
          Already have an account?{" "}
          <Link to="/login" className="text-brand-dark underline">
            Sign in
          </Link>
        </p>
      </form>
    </section>
  );
}