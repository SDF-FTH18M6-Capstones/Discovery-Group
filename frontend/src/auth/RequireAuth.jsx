import { Link, Navigate, Outlet, useLocation } from "react-router-dom";

import Icon from "../components/Icon";
import { useAuth } from "./AuthContext";

// Wrap routes that need a signed-in user. With `roles`, only those roles get in.
export default function RequireAuth({ roles }) {
  const { user, signedOut } = useAuth();
  const location = useLocation();

  if (!user) {
    // After an expired session, come back to this page once signed in again (US-04);
    // after a deliberate sign-out, start the next person on the dashboard.
    return (
      <Navigate
        to="/login"
        replace
        state={signedOut ? undefined : { from: location.pathname + location.search }}
      />
    );
  }
  if (roles && !roles.includes(user.role)) {
    return (
      <section className="flex flex-col items-start gap-3 py-10">
        <span className="grid size-14 place-items-center rounded-2xl bg-saffron-soft text-saffron-ink">
          <Icon name="lock" size={26} />
        </span>
        <h1 className="page-title">No access</h1>
        <p className="text-muted">Your role ({user.role}) cannot open this page.</p>
        <Link to="/" className="btn-secondary">
          Go to the dashboard
        </Link>
      </section>
    );
  }
  return <Outlet />;
}
