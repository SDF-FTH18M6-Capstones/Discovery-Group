import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { PROCUREMENT, PURCHASE_VIEWERS, ROLE_NAMES, SELLERS, STOCK_MANAGERS } from "../auth/roles";
import { NOTIFICATIONS_CHANGED } from "../events";
import { useTheme } from "../theme/ThemeContext";
import ErrorBoundary from "./ErrorBoundary";
import Icon from "./Icon";

// `roles` = who sees the link. No `roles` = every signed-in user.
const groups = [
  { title: "Overview", links: [{ to: "/", label: "Dashboard", icon: "dashboard", end: true }] },
  {
    title: "Selling",
    links: [
      { to: "/sales/new", label: "New sale", icon: "sale", roles: SELLERS },
      { to: "/sales", label: "Sales", icon: "receipt", roles: SELLERS, end: true },
    ],
  },
  {
    title: "Stock",
    links: [
      { to: "/products", label: "Products", icon: "box" },
      { to: "/categories", label: "Categories", icon: "tag" },
      { to: "/stock", label: "Stock ledger", icon: "ledger", roles: STOCK_MANAGERS },
      { to: "/purchases", label: "Purchases", icon: "truck", roles: PURCHASE_VIEWERS },
      { to: "/suppliers", label: "Suppliers", icon: "building", roles: PROCUREMENT },
    ],
  },
  {
    title: "Requests",
    links: [
      { to: "/requests", label: "My requests", icon: "inbox" },
      { to: "/approvals", label: "Approvals", icon: "check", roles: PROCUREMENT },
    ],
  },
  {
    title: "Assets",
    links: [
      { to: "/assets", label: "Assets", icon: "laptop", roles: STOCK_MANAGERS },
      {
        to: "/assets",
        label: "My assets",
        icon: "laptop",
        roles: ["procurement", "sales", "employee"],
      },
      { to: "/repairs", label: "Repairs", icon: "wrench" },
    ],
  },
  {
    title: "Admin",
    links: [
      { to: "/reports", label: "Reports", icon: "chart", roles: ["admin"] },
      { to: "/users", label: "Users", icon: "users", roles: ["admin"] },
    ],
  },
  {
    title: "Account",
    links: [
      { to: "/settings", label: "Settings", icon: "settings" },
      { to: "/status", label: "System status", icon: "pulse" },
    ],
  },
];

function ThemeSwitch({ className = "" }) {
  const { dark, toggle } = useTheme();
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode" : "Dark mode"}
      className={`grid size-10 place-items-center rounded-lg border border-line bg-surface text-ink hover:border-brand ${className}`}
    >
      <Icon name={dark ? "sun" : "moon"} />
    </button>
  );
}

function Bell() {
  const { pathname } = useLocation();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      api("/api/notifications/?unread=true&per_page=1")
        .then((data) => !cancelled && setUnread(data?.count || 0))
        .catch(() => {});
    load();
    window.addEventListener(NOTIFICATIONS_CHANGED, load);
    return () => {
      cancelled = true;
      window.removeEventListener(NOTIFICATIONS_CHANGED, load);
    };
  }, [pathname]);

  return (
    <Link
      to="/notifications"
      aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
      className="relative grid size-10 place-items-center rounded-lg border border-line bg-surface text-ink hover:border-brand"
    >
      <Icon name="bell" />
      {unread > 0 && (
        <span
          aria-hidden="true"
          className="absolute -top-1.5 -right-1.5 min-w-5 rounded-full bg-danger px-1 text-center text-[11px] leading-5 font-bold text-white dark:text-canvas"
        >
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}

function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <span className="grid size-9 place-items-center rounded-lg bg-brand font-display text-sm font-bold text-on-brand shadow-[0_0_0_4px_rgb(8_168_117/0.18)]">
        SP
      </span>
      <span className="font-display text-lg font-bold tracking-tight text-white">StockPilot</span>
    </Link>
  );
}

const initials = (name = "") =>
  name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");

function SignedOutShell() {
  return (
    <div className="grid min-h-screen bg-canvas lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <aside className="relative hidden overflow-hidden border-r border-white/5 bg-evergreen p-10 lg:flex lg:flex-col lg:justify-between">
        <Brand />
        <div className="relative z-10 flex max-w-md flex-col gap-4">
          <p className="font-display text-3xl leading-tight font-bold text-balance text-white">
            Stock, sales, purchases and assets in one place.
          </p>
          <p className="text-sidebar-ink">
            Every sale and delivery is written to the stock ledger, so the numbers always add up.
          </p>
        </div>
        <p className="relative z-10 text-sm text-sidebar-ink">Discovery Group · Capstone</p>
        <div
          aria-hidden="true"
          className="absolute -bottom-40 -left-24 size-[28rem] rounded-full border-[56px] border-brand/10"
        />
      </aside>
      <div className="flex min-w-0 flex-col">
        <div className="flex items-center justify-between gap-3 p-4">
          <span className="rounded-lg bg-evergreen px-3 py-2 lg:invisible">
            <Brand />
          </span>
          <ThemeSwitch />
        </div>
        <main className="flex flex-1 items-start justify-center px-4 pb-10 sm:items-center">
          <div className="card w-full max-w-md p-6 sm:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

export default function Layout() {
  const { user, signOut, hasRole } = useAuth();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => setMenuOpen(false), [pathname]);

  if (!user) {
    return (
      <ErrorBoundary key={pathname}>
        <SignedOutShell />
      </ErrorBoundary>
    );
  }

  const visible = groups
    .map((group) => ({
      ...group,
      links: group.links.filter((link) => !link.roles || hasRole(...link.roles)),
    }))
    .filter((group) => group.links.length);

  return (
    <div className="min-h-screen bg-canvas text-ink lg:flex">
      <aside
        id="sidebar"
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col gap-5 overflow-y-auto border-r border-white/5 bg-evergreen px-3 py-5 transition-[transform,visibility] duration-200 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
          menuOpen ? "translate-x-0" : "max-lg:invisible max-lg:-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-2">
          <Brand />
          <button
            type="button"
            onClick={() => setMenuOpen(false)}
            aria-label="Close menu"
            className="grid size-9 place-items-center rounded-lg text-sidebar-ink hover:text-white lg:hidden"
          >
            <Icon name="close" />
          </button>
        </div>

        <nav aria-label="Main" className="flex flex-col gap-4">
          {visible.map((group) => (
            <div key={group.title} className="flex flex-col gap-0.5">
              <p className="px-3 pb-1 text-[11px] font-semibold tracking-[0.12em] text-sidebar-ink/60 uppercase">
                {group.title}
              </p>
              {group.links.map((link) => (
                <NavLink
                  key={link.label}
                  to={link.to}
                  end={link.end}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                      isActive
                        ? "bg-brand font-semibold text-on-brand"
                        : "text-sidebar-ink hover:bg-white/5 hover:text-white"
                    }`
                  }
                >
                  <Icon name={link.icon} />
                  {link.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="mt-auto flex items-center gap-3 rounded-xl bg-white/5 p-3">
          <span
            aria-hidden="true"
            className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-soft font-semibold text-brand-dark"
          >
            {initials(user.full_name)}
          </span>
          <span className="min-w-0 flex-1 text-sm leading-tight">
            <span className="block truncate font-semibold text-white">{user.full_name}</span>
            <span className="block truncate text-xs text-sidebar-ink">
              {ROLE_NAMES[user.role] || user.role}
            </span>
          </span>
          <button
            type="button"
            onClick={signOut}
            className="rounded-md border border-white/20 px-2 py-1 text-xs text-white hover:border-white/50"
          >
            Sign out
          </button>
        </div>
      </aside>

      {menuOpen && (
        <button
          type="button"
          aria-label="Close menu"
          tabIndex={-1}
          onClick={() => setMenuOpen(false)}
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line bg-canvas/85 px-4 backdrop-blur md:px-8">
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label="Open menu"
            aria-controls="sidebar"
            aria-expanded={menuOpen}
            className="grid size-10 place-items-center rounded-lg border border-line bg-surface lg:hidden"
          >
            <Icon name="menu" />
          </button>
          <span className="truncate text-sm text-muted">
            {new Date().toLocaleDateString("en-GB", {
              weekday: "long",
              day: "numeric",
              month: "long",
            })}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <ThemeSwitch />
            <Bell />
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl min-w-0 flex-1 p-4 md:p-8">
          <ErrorBoundary key={pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}