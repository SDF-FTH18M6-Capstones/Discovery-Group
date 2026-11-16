import { Link, Navigate, Route, Routes } from "react-router-dom";

import RequireAuth from "./auth/RequireAuth";
import Layout from "./components/Layout";
import ProductsPage from "./features/products/ProductsPage";
import SuppliersPage from "./features/suppliers/SuppliersPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import StatusPage from "./pages/StatusPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";

function NotFound() {
  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-2xl font-bold">Page not found</h1>
      <Link to="/products" className="text-brand-dark underline">
        Go to products
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
        <Route path="verify-email" element={<VerifyEmailPage />} />
        <Route path="status" element={<StatusPage />} />

        {/* Signed-in users only */}
        <Route element={<RequireAuth />}>
          <Route index element={<Navigate to="/products" replace />} />
          <Route path="products" element={<ProductsPage />} />
        </Route>

        {/* Signed-in Administrator or Procurement Manager only */}
        <Route element={<RequireAuth roles={["admin", "procurement"]} />}>
          <Route path="suppliers" element={<SuppliersPage />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}