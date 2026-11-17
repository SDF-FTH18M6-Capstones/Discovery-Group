// Home page after sign-in: the counts that matter to the signed-in role, each linking to its
// page, quick buttons for the role's everyday jobs, and (Administrator) the last 7 days of sales.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import {
  PROCUREMENT,
  PURCHASE_VIEWERS,
  ROLE_NAMES,
  SELLERS,
  STOCK_MANAGERS,
} from "../../auth/roles";
import Icon from "../../components/Icon";
import { money } from "../../format";

const todayUtc = () => new Date().toISOString().slice(0, 10);

function cardsFor(hasRole) {
  const seesAllRequests = hasRole(...PROCUREMENT);
  const managesAssets = hasRole(...STOCK_MANAGERS);
  const cards = [];
  if (hasRole(...SELLERS)) {
    cards.push({
      key: "sales",
      label: hasRole("admin") ? "Sales today" : "Your sales today",
      path: `/api/sales/?day=${todayUtc()}&per_page=1`,
      to: "/sales",
      icon: "receipt",
    });
  }
  cards.push(
    {
      key: "low",
      label: "Products low on stock",
      path: "/api/products/?low_stock=true&per_page=1",
      to: "/products",
      icon: "box",
      alert: true,
    },
    seesAllRequests
      ? {
          key: "pending",
          label: "Requests waiting for a decision",
          path: "/api/requests/?status=pending&per_page=1",
          to: "/approvals",
          icon: "check",
        }
      : {
          key: "pending",
          label: "My requests still pending",
          path: "/api/requests/?status=pending&mine=true&per_page=1",
          to: "/requests",
          icon: "inbox",
        },
    {
      key: "assets",
      label: managesAssets ? "Assets in the register" : "Assets you hold",
      path: "/api/assets/?per_page=1",
      to: "/assets",
      icon: "laptop",
    },
  );
  if (hasRole(...PURCHASE_VIEWERS)) {
    cards.push({
      key: "orders",
      label: "Orders waiting for delivery",
      path: "/api/purchases/?status=ordered&per_page=1",
      to: "/purchases",
      icon: "truck",
    });
  }
  if (managesAssets) {
    cards.push({
      key: "repairs",
      label: "New repair reports",
      path: "/api/repairs/?status=submitted&per_page=1",
      to: "/repairs",
      icon: "wrench",
      alert: true,
    });
  }
  if (seesAllRequests) {
    cards.push({
      key: "suppliers",
      label: "Suppliers",
      path: "/api/suppliers/?per_page=1",
      to: "/suppliers",
      icon: "building",
    });
  }
  return cards;
}

function WeekStrip() {
  const [report, setReport] = useState(null);
  useEffect(() => {
    api("/api/reports/summary?days=7")
      .then(setReport)
      .catch(() => {});
  }, []);
  if (!report) return null;
  const highest = Math.max(...report.by_day.map((day) => Number(day.total)), 1);
  return (
    <Link
      to="/reports"
      className="card relative flex flex-col gap-4 overflow-hidden p-5 hover:border-brand sm:flex-row sm:items-end"
    >
      <div className="flex flex-1 flex-col gap-1">
        <span className="text-sm text-muted">Sales, last 7 days</span>
        <span className="font-display text-3xl font-bold" data-testid="week-sales">
          {money(report.sales_total)}
        </span>
        <span className="text-sm text-muted">
          {report.sales_count} sales · estimated profit {money(report.estimated_profit)}
        </span>
      </div>
      <div aria-hidden="true" className="flex h-16 items-end gap-1.5 sm:w-56">
        {report.by_day.map((day) => (
          <span
            key={day.day}
            className="flex-1 rounded-t-[3px] bg-brand"
            style={{ height: `${Math.max((Number(day.total) / highest) * 100, 4)}%` }}
          />
        ))}
      </div>
    </Link>
  );
}

export default function DashboardPage() {
  const { user, hasRole } = useAuth();
  const [counts, setCounts] = useState({});
  const cards = cardsFor(hasRole);
  const paths = cards.map((card) => card.path).join("|");

  useEffect(() => {
    let cancelled = false;
    // Each card loads on its own, so one failing count does not blank the others.
    Promise.allSettled(paths.split("|").map((path) => api(path))).then((results) => {
      if (cancelled) return;
      setCounts(
        Object.fromEntries(
          results.map((result, i) => [i, result.status === "fulfilled" ? result.value.count : "—"]),
        ),
      );
    });
    return () => {
      cancelled = true;
    };
  }, [paths]);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted">{greeting}</p>
          <h1 className="page-title">Welcome, {user.full_name.split(" ")[0]}</h1>
          <p className="text-muted">Signed in as {ROLE_NAMES[user.role] || user.role}.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {hasRole(...SELLERS) && (
            <Link to="/sales/new" className="btn-primary">
              <Icon name="sale" size={16} /> New sale
            </Link>
          )}
          <Link to="/requests" className={hasRole(...SELLERS) ? "btn-secondary" : "btn-primary"}>
            New request
          </Link>
          <Link to="/products" className="btn-secondary">
            Browse products
          </Link>
        </div>
      </div>

      {hasRole("admin") && <WeekStrip />}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card, i) => {
          const value = counts[i];
          const flagged = card.alert && typeof value === "number" && value > 0;
          return (
            <Link
              key={card.key}
              to={card.to}
              className="card group flex flex-col gap-3 p-4 transition hover:-translate-y-0.5 hover:border-brand"
            >
              <span
                className={`grid size-10 place-items-center rounded-xl ${flagged ? "bg-danger-soft text-danger" : "bg-mint text-brand-dark"}`}
              >
                <Icon name={card.icon} />
              </span>
              <span className="font-display text-3xl font-bold" data-testid={`count-${card.key}`}>
                {value ?? "…"}
              </span>
              <span className="text-sm text-muted">{card.label}</span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}