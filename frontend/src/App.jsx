import { Link, Route, Routes } from "react-router-dom";

import RequireAuth from "./auth/RequireAuth";
import { PROCUREMENT } from "./auth/roles";
import Layout from "./components/Layout";
import AssetsPage from "./features/assets/AssetsPage";
import CategoriesPage from "./features/categories/CategoriesPage";
import DashboardPage from "./features/dashboard/DashboardPage";
import ProductsPage from "./features/products/ProductsPage";
import ApprovalsPage from "./features/requests/ApprovalsPage";
import RequestsPage from "./features/requests/RequestsPage";
import SuppliersPage from "./features/suppliers/SuppliersPage";
import UsersPage from "./features/users/UsersPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import StatusPage from "./pages/StatusPage";

function NotFound() {
  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-2xl font-bold">Page not found</h1>
      <Link to="/" className="text-brand-dark underline">
        Go to the dashboard
      </Link>
    </section>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Open to everyone */}
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="status" element={<StatusPage />} />

        {/* Signed-in users only (the page itself hides what the role cannot do) */}
        <Route element={<RequireAuth />}>
          <Route index element={<DashboardPage />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="categories" element={<CategoriesPage />} />
          <Route path="requests" element={<RequestsPage />} />
          <Route path="assets" element={<AssetsPage />} />
        </Route>

        {/* Administrator or Procurement Manager only */}
        <Route element={<RequireAuth roles={PROCUREMENT} />}>
          <Route path="suppliers" element={<SuppliersPage />} />
          <Route path="approvals" element={<ApprovalsPage />} />
        </Route>

        {/* Administrator only */}
        <Route element={<RequireAuth roles={["admin"]} />}>
          <Route path="users" element={<UsersPage />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
