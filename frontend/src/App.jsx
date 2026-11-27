import { Link, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";

import RequireAuth from "./auth/RequireAuth";
import { PROCUREMENT_VIEWERS, PURCHASE_VIEWERS, SALES_VIEWERS, STOCK_VIEWERS } from "./auth/roles";
import Layout from "./components/Layout";
import AssetsPage from "./features/assets/AssetsPage";
import AuditPage from "./features/audit/AuditPage";
import BillingPage from "./features/billing/BillingPage";
import PlatformPage from "./features/platform/PlatformPage";
import CategoriesPage from "./features/categories/CategoriesPage";
import DashboardPage from "./features/dashboard/DashboardPage";
import NotificationsPage from "./features/notifications/NotificationsPage";
import ProductDetailPage from "./features/products/ProductDetailPage";
import ProductsPage from "./features/products/ProductsPage";
import PurchasesPage from "./features/purchases/PurchasesPage";
import RepairsPage from "./features/repairs/RepairsPage";
import ReportsPage from "./features/reports/ReportsPage";
import ApprovalsPage from "./features/requests/ApprovalsPage";
import RequestsPage from "./features/requests/RequestsPage";
import PosPage from "./features/sales/PosPage";
import SalesPage from "./features/sales/SalesPage";
import SettingsPage from "./features/settings/SettingsPage";
import StockPage from "./features/stock/StockPage";
import SuppliersPage from "./features/suppliers/SuppliersPage";
import UsersPage from "./features/users/UsersPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";
import StatusPage from "./pages/StatusPage";

function NotFound() {
  return (
    <section className="flex flex-col items-start gap-3 py-10">
      <p className="figure text-6xl text-line-strong">404</p>
      <h1 className="page-title">Page not found</h1>
      <p className="text-muted">The address is wrong, or the page has moved.</p>
      <Link to="/" className="btn-primary">
        Go to the dashboard
      </Link>
    </section>
  );
}

function Home() {
  const { user } = useAuth();
  return user ? <DashboardPage /> : <LandingPage />;
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="forgot-password" element={<ForgotPasswordPage />} />
        <Route path="reset-password" element={<ResetPasswordPage />} />
        <Route path="verify-email" element={<VerifyEmailPage />} />
        <Route path="status" element={<StatusPage />} />
        <Route index element={<Home />} />

        <Route element={<RequireAuth />}>
          <Route path="products" element={<ProductsPage />} />
          <Route path="categories" element={<CategoriesPage />} />
          <Route path="requests" element={<RequestsPage />} />
          <Route path="products/:id" element={<ProductDetailPage />} />
          <Route path="assets" element={<AssetsPage />} />
          <Route path="repairs" element={<RepairsPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="platform" element={<PlatformPage />} />
        </Route>

        <Route element={<RequireAuth roles={SALES_VIEWERS} />}>
          <Route path="sales" element={<SalesPage />} />
        </Route>
        <Route element={<RequireAuth jobs={["sales"]} />}>
          <Route path="sales/new" element={<PosPage />} />
        </Route>

        <Route element={<RequireAuth roles={STOCK_VIEWERS} />}>
          <Route path="stock" element={<StockPage />} />
        </Route>

        <Route element={<RequireAuth roles={PURCHASE_VIEWERS} />}>
          <Route path="purchases" element={<PurchasesPage />} />
        </Route>

        <Route element={<RequireAuth roles={PROCUREMENT_VIEWERS} />}>
          <Route path="suppliers" element={<SuppliersPage />} />
          <Route path="approvals" element={<ApprovalsPage />} />
        </Route>

        <Route element={<RequireAuth roles={["admin"]} />}>
          <Route path="users" element={<UsersPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="billing" element={<BillingPage />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
