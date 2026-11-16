import { Link, Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";
export default function RequireAuth({ roles }) {
  const { user } = useAuth();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (roles && !roles.includes(user.role)) {
    return (
      <section className="flex flex-col gap-3">
        <h1 className="text-2xl font-bold">No access</h1>
        <p className="text-muted">Your role ({user.role}) cannot open this page.</p>
        <Link to="/products" className="text-brand-dark underline">
          Go to products
        </Link>
      </section>
    );
  }
  return <Outlet />;
}
