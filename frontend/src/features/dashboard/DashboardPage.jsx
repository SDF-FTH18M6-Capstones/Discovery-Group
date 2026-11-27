import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { ROLE_NAMES } from "../../auth/roles";
import Icon from "../../components/Icon";
import { BarChart, EmptyState, Panel, StatStrip, StockMeter } from "../../components/ui";
import { money, shortDate, timeAgo } from "../../format";

const TILE_ICONS = {
  low_stock: "box",
  approvals: "check",
  awaiting_receipt: "truck",
  open_repairs: "wrench",
  overdue_assets: "clock",
  sales_today: "receipt",
  my_sales_today: "receipt",
  my_requests: "inbox",
  my_assets: "laptop",
  my_repairs: "wrench",
};
const TILE_TONES = { ok: "brand", warn: "saffron", danger: "danger" };

function usePulse() {
  const [tiles, setTiles] = useState(null);
  useEffect(() => {
    let cancelled = false;
    api("/api/dashboard/pulse")
      .then((data) => !cancelled && setTiles(data?.tiles || []))
      .catch(() => !cancelled && setTiles([]));
    return () => {
      cancelled = true;
    };
  }, []);
  return tiles;
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
              <p className="text-sm text-muted">Gross profit</p>
              <p className="figure text-2xl text-brand-dark">{money(report.gross_profit)}</p>
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
              {note.link ? (
                <Link to={note.link} className="block text-sm hover:underline">
                  {note.message}
                </Link>
              ) : (
                <span className="block text-sm">{note.message}</span>
              )}
              <span className="text-xs text-muted">{timeAgo(note.created_at)}</span>
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Shortcuts({ canDo }) {
  const links = [
    canDo("sales") && { to: "/sales/new", icon: "sale", label: "Ring up a sale" },
    canDo("inventory") && { to: "/stock", icon: "ledger", label: "Adjust stock" },
    canDo("procurement") && { to: "/purchases", icon: "truck", label: "Place an order" },
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
  const { user, hasRole, canDo } = useAuth();
  const location = useLocation();
  const tiles = usePulse();

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
          {user.business?.name && <p className="text-sm text-muted">{user.business.name}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          {canDo("sales") && (
            <Link to="/sales/new" className="btn-primary">
              <Icon name="sale" size={16} /> New sale
            </Link>
          )}
          <Link to="/requests?new=1" className={canDo("sales") ? "btn-secondary" : "btn-primary"}>
            New request
          </Link>
          <Link to="/products" className="btn-secondary">
            Browse products
          </Link>
        </div>
      </div>

      {location.state?.welcome && (
        <div className="panel flex flex-col gap-3 border-brand/40 bg-mint p-5">
          <h2 className="text-lg font-bold">Your business is ready</h2>
          <ol className="list-decimal pl-5 text-sm">
            <li>
              Check your name, currency and VAT under{" "}
              <Link to="/settings" className="link">
                Settings
              </Link>
              , and copy the join code to invite your staff.
            </li>
            <li>
              Add{" "}
              <Link to="/categories" className="link">
                categories
              </Link>{" "}
              and{" "}
              <Link to="/products" className="link">
                products
              </Link>
              , then start selling.
            </li>
          </ol>
        </div>
      )}

      <section aria-label="StockPilot Pulse">
        {tiles === null ? (
          <div className="skeleton h-28" />
        ) : (
          <StatStrip
            items={tiles.map((tile) => ({
              label: tile.label,
              value: tile.amount != null ? money(tile.amount) : tile.count,
              hint:
                tile.amount != null
                  ? `${tile.count} ${tile.count === 1 ? "sale" : "sales"}`
                  : tile.detail || undefined,
              to: tile.link,
              icon: TILE_ICONS[tile.key] || "pulse",
              tone: TILE_TONES[tile.tone] || "muted",
              testId: `count-${tile.key}`,
            }))}
          />
        )}
      </section>

      <div className="grid grid-cols-1 items-start gap-6 xl:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-6 xl:col-span-2">
          {hasRole("admin") && <WeekSales />}
          <RunningLow />
        </div>
        <div className="flex min-w-0 flex-col gap-6">
          <Latest />
          <Shortcuts canDo={canDo} />
        </div>
      </div>
    </section>
  );
}
