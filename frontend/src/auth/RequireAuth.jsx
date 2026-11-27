import { Link, Navigate, Outlet, useLocation } from "react-router-dom";

import Icon from "../components/Icon";
import { useAuth } from "./AuthContext";

export default function RequireAuth({ roles, jobs }) {
  const { user, signedOut, canDo } = useAuth();
  const location = useLocation();

  if (!user) {
    return (
      <Navigate
        to="/login"
        replace
        state={signedOut ? undefined : { from: location.pathname + location.search }}
      />
    );
  }
  if ((roles && !roles.includes(user.role)) || (jobs && !canDo(...jobs))) {
    return (
      <section className="flex flex-col items-start gap-3 py-10">
        <span className="grid size-14 place-items-center rounded-2xl bg-saffron-soft text-saffron-ink">
          <Icon name="lock" size={26} />
        </span>
        <h1 className="page-title">No access</h1>
        <p className="text-muted">
          {user.role === "admin"
            ? "Your staff do this job. As Administrator you can follow their work, but not do it."
            : `Your role (${user.role}) cannot open this page.`}
        </p>
        <Link to="/" className="btn-secondary">
          Go to the dashboard
        </Link>
      </section>
    );
  }
  return <Outlet />;
}
