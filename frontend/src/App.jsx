import { Link, Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import ProductsPage from "./features/products/ProductsPage";
import SuppliersPage from "./features/suppliers/SuppliersPage";
import StatusPage from "./pages/StatusPage";

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
        <Route index element={<Navigate to="/products" replace />} />
        <Route path="products" element={<ProductsPage />} />
        <Route path="suppliers" element={<SuppliersPage />} />
        <Route path="status" element={<StatusPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}