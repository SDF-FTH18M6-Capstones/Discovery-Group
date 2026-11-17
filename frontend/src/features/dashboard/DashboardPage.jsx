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
import { BarChart, EmptyState, Panel, StatStrip, StockMeter } from "../../components/ui";
import { money, shortDate, timeAgo } from "../../format";

// Today on this computer's calendar (YYYY-MM-DD); the API reads days on the shop's clock too.
const today = () => new Date().toLocaleDateString("en-CA");

function cardsFor(hasRole) {
  const seesAllRequests = hasRole(...PROCUREMENT);
  const managesAssets = hasRole(...STOCK_MANAGERS);
  const cards = [];
  if (hasRole(...SELLERS)) {
    cards.push({
      key: "sales",
      label: hasRole("admin") ? "Sales today" : "Your sales today",
      path: `/api/sales/?day=${today()}&per_page=1`,
      to: "/sales",
      icon: "receipt",
      tone: "brand",
    });
  }
  cards.push(
    {
      key: "low",
      label: "Products low on stock",
      path: "/api/products/?low_stock=true&per_page=1",
      to: "/products",
      icon: "box",
      tone: "saffron",
    },
    seesAllRequests
      ? {
          key: "pending",
          label: "Requests waiting for a decision",
          path: "/api/requests/?status=pending&per_page=1",
          to: "/approvals",
          icon: "check",
          tone: "info",
        }
      : {
          key: "pending",
          label: "My requests still pending",
          path: "/api/requests/?status=pending&mine=true&per_page=1",
          to: "/requests",
          icon: "inbox",
          tone: "info",
        },
    {
      key: "assets",
      label: managesAssets ? "Assets in the register" : "Assets you hold",
      path: "/api/assets/?per_page=1",
      to: "/assets",
      icon: "laptop",
      tone: "muted",
    },
  );
  if (hasRole(...PURCHASE_VIEWERS)) {
    cards.push({
      key: "orders",
      label: "Orders waiting for delivery",
      path: "/api/purchases/?status=ordered&per_page=1",
      to: "/purchases",
      icon: "truck",
      tone: "brand",
    });
  }
  if (managesAssets) {
    cards.push({
      key: "repairs",
      label: "New repair reports",
      path: "/api/repairs/?status=submitted&per_page=1",
      to: "/repairs",
      icon: "wrench",
      tone: "danger",
    });
  }
  if (seesAllRequests) {
    cards.push({
      key: "suppliers",
      label: "Suppliers",
      path: "/api/suppliers/?per_page=1",
      to: "/suppliers",
      icon: "building",
      tone: "muted",
    });
  }
  return cards;
}

function WeekSales() {
  const [report, setReport] = useState(null);
  useEffect(() => {
    api("/api/reports/summary?days=7")
      .then(setReport)
      .catch(() => setReport(false));
  }, []);
  if (report === false) return null;
  const days = (report?.by_day || []).map((day) => ({
    label: shortDate(day.day),
    short: new Date(day.day).toLocaleDateString("en-GB", { weekday: "short" }),
    value: Number(day.total),
    detail: `${day.count} sales`,
  }));
  return (
    <Panel
      title="Sales, last 7 days"
      actions={
        <Link to="/reports" className="btn-ghost text-sm">
          Open reports
        </Link>
      }
      bodyClassName="flex flex-col gap-6 p-5"
    >
      {!report ? (
        <div className="skeleton h-56" />
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-x-10 gap-y-3">
            <div>
              <p className="text-sm text-muted">Takings</p>
              <p className="figure text-4xl" data-testid="week-sales">
                {money(report.sales_total)}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted">Receipts</p>
              <p className="figure text-2xl">{report.sales_count}</p>
            </div>
            <div>
              <p className="text-sm text-muted">Estimated profit</p>
              <p className="figure text-2xl text-brand-dark">{money(report.estimated_profit)}</p>
            </div>
          </div>
          <BarChart data={days} height={240} label="Sales per day, last 7 days" format={money} />
        </>
      )}
    </Panel>
  );
}

function RunningLow() {
  const [items, setItems] = useState(null);
  useEffect(() => {
    api("/api/products/?low_stock=true&per_page=6")
      .then((data) => setItems(data.results || []))
      .catch(() => setItems([]));
  }, []);
  return (
    <Panel
      title="Running low"
      subtitle="At or below the reorder level"
      actions={
        <Link to="/products" className="btn-ghost text-sm">
          All products
        </Link>
      }
    >
      {items === null && <div className="skeleton m-5 h-40" />}
      {items?.length === 0 && (
        <EmptyState icon="box" title="Shelves are full">
          Nothing is at its reorder level right now.
        </EmptyState>
      )}
      {items?.length > 0 && (
        <ul className="divide-y divide-line">
          {items.map((product) => (
            <li key={product.id} className="flex items-center gap-4 px-5 py-3">
              <span className="min-w-0 flex-1">
                <Link
                  to={`/products/${product.id}`}
                  className="block truncate font-medium hover:underline"
                >
                  {product.name}
                </Link>
                <span className="code text-muted">{product.sku}</span>
              </span>
              <StockMeter quantity={product.quantity} reorder={product.reorder_level} />
              <span
                className={`figure w-16 text-right ${product.quantity === 0 ? "text-danger" : "text-saffron-ink"}`}
              >
                {product.quantity}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Latest() {
  const [notes, setNotes] = useState(null);
  useEffect(() => {
    api("/api/notifications/?per_page=5")
      .then((data) => setNotes(data.results || []))
      .catch(() => setNotes([]));
  }, []);
  return (
    <Panel
      title="Latest for you"
      actions={
        <Link to="/notifications" className="btn-ghost text-sm">
          See all
        </Link>
      }
    >
      {notes === null && <div className="skeleton m-5 h-32" />}
      {notes?.length === 0 && (
        <p className="px-5 py-8 text-center text-sm text-muted">Nothing new. You are up to date.</p>
      )}
      <ul className="divide-y divide-line">
        {notes?.map((note) => (
          <li key={note.id} className="flex gap-3 px-5 py-3">
            <span
              aria-hidden="true"
              className={`mt-1.5 size-2 shrink-0 rounded-full ${note.is_read ? "bg-line-strong" : "bg-saffron"}`}
            />
            <span className="min-w-0 flex-1">
              <span className="block text-sm">{note.message}</span>
              <span className="text-xs text-muted">{timeAgo(note.created_at)}</span>
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Shortcuts({ hasRole }) {
  const links = [
    hasRole(...SELLERS) && { to: "/sales/new", icon: "sale", label: "Ring up a sale" },
    hasRole(...STOCK_MANAGERS) && { to: "/stock", icon: "ledger", label: "Adjust stock" },
    hasRole(...PROCUREMENT) && { to: "/purchases", icon: "truck", label: "Place an order" },
    { to: "/requests?new=1", icon: "inbox", label: "Ask for something" },
    { to: "/repairs", icon: "wrench", label: "Report a fault" },
  ].filter(Boolean);
  return (
    <Panel title="Shortcuts">
      <ul className="grid grid-cols-2">
        {links.map((link) => (
          <li key={link.to} className="shadow-[1px_0_0_var(--sp-line),0_1px_0_var(--sp-line)]">
            <Link
              to={link.to}
              className="flex h-full flex-col gap-2 p-4 text-sm font-medium transition-colors hover:bg-surface-2"
            >
              <Icon name={link.icon} className="text-brand-dark" />
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export default function DashboardPage() {
  const { user, hasRole } = useAuth();
  const [counts, setCounts] = useState({});
  const cards = cardsFor(hasRole);
  const paths = cards.map((card) => card.path).join("|");

  useEffect(() => {
    let cancelled = false;
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
        <div className="flex flex-col gap-1.5">
          <p className="text-sm text-muted">
            {greeting}. You are signed in as {ROLE_NAMES[user.role] || user.role}.
          </p>
          <h1 className="page-title">Welcome, {user.full_name.split(" ")[0]}</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          {hasRole(...SELLERS) && (
            <Link to="/sales/new" className="btn-primary">
              <Icon name="sale" size={16} /> New sale
            </Link>
          )}
          <Link
            to="/requests?new=1"
            className={hasRole(...SELLERS) ? "btn-secondary" : "btn-primary"}
          >
            New request
          </Link>
          <Link to="/products" className="btn-secondary">
            Browse products
          </Link>
        </div>
      </div>

      <StatStrip
        items={cards.map((card, i) => ({
          label: card.label,
          value: counts[i],
          to: card.to,
          icon: card.icon,
          tone: card.tone,
          testId: `count-${card.key}`,
        }))}
      />

      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-6 xl:col-span-2">
          {hasRole("admin") && <WeekSales />}
          <RunningLow />
        </div>
        <div className="flex min-w-0 flex-col gap-6">
          <Latest />
          <Shortcuts hasRole={hasRole} />
        </div>
      </div>
    </section>
  );
}
