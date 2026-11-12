import { Link, Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import StatusPage from "./pages/StatusPage";

function NotFound() {
  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-2xl font-bold">Page not found</h1>
      <Link to="/status" className="text-brand-dark underline">
        Go to system status
      </Link>
    </section>
  );
}

// Products and suppliers screens arrive in Sprint 2.
function ComingSoon({ title }) {
  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-2xl font-bold">{title}</h1>
      <p className="text-muted">This screen is built in Sprint 2.</p>
    </section>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/status" replace />} />
        <Route path="products" element={<ComingSoon title="Products" />} />
        <Route path="suppliers" element={<ComingSoon title="Suppliers" />} />
        <Route path="status" element={<StatusPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}