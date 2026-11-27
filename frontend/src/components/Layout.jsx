import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import {
  PROCUREMENT_VIEWERS,
  PURCHASE_VIEWERS,
  ROLE_NAMES,
  SALES_VIEWERS,
  STOCK_VIEWERS,
} from "../auth/roles";
import { NOTIFICATIONS_CHANGED } from "../events";
import { longDate } from "../format";
import ErrorBoundary from "./ErrorBoundary";
import Icon from "./Icon";
import Logo from "./Logo";
import ThemeSwitch from "./ThemeSwitch";
import { Avatar } from "./ui";

const groups = [
  {
    title: "Overview",
    links: [
      { to: "/", label: "Dashboard", icon: "dashboard", end: true },
      { to: "/insights", label: "Insights", icon: "pulse", roles: ["admin"] },
      { to: "/money", label: "M-Pesa money", icon: "cash", roles: ["admin"] },
    ],
  },
  {
    title: "Selling",
    links: [
      { to: "/sales/new", label: "New sale", icon: "sale", jobs: ["sales"] },
      { to: "/sales", label: "Sales", icon: "receipt", roles: SALES_VIEWERS, end: true },
    ],
  },
  {
    title: "Stock",
    links: [
      { to: "/products", label: "Products", icon: "box" },
      { to: "/categories", label: "Categories", icon: "tag" },
      { to: "/stock", label: "Stock ledger", icon: "ledger", roles: STOCK_VIEWERS },
      { to: "/purchases", label: "Purchases", icon: "truck", roles: PURCHASE_VIEWERS },
      { to: "/suppliers", label: "Suppliers", icon: "building", roles: PROCUREMENT_VIEWERS },
    ],
  },
  {
    title: "Requests",
    links: [
      { to: "/requests", label: "My requests", icon: "inbox" },
      { to: "/approvals", label: "Approvals", icon: "check", roles: PROCUREMENT_VIEWERS },
    ],
  },
  {
    title: "Assets",
    links: [
      { to: "/assets", label: "Assets", icon: "laptop", roles: STOCK_VIEWERS },
      {
        to: "/assets",
        label: "Assets with me",
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
      { to: "/audit", label: "Audit log", icon: "shield", roles: ["admin"] },
      { to: "/billing", label: "Billing", icon: "card", roles: ["admin"] },
    ],
  },
  {
    title: "StockPilot",
    links: [{ to: "/platform", label: "Platform", icon: "layers", owners: true }],
  },
  {
    title: "Account",
    links: [
      { to: "/settings", label: "Settings", icon: "settings" },
      { to: "/status", label: "System status", icon: "pulse" },
    ],
  },
];

function whereAmI(pathname) {
  let best = null;
  for (const group of groups) {
    for (const link of group.links) {
      const hit =
        link.to === "/"
          ? pathname === "/"
          : pathname === link.to || pathname.startsWith(`${link.to}/`);
      if (hit && (!best || link.to.length > best.link.to.length)) best = { group, link };
    }
  }
  if (pathname === "/notifications") return { section: "Account", page: "Notifications" };
  return best ? { section: best.group.title, page: best.link.label } : null;
}

function OfflineBanner() {
  const [online, setOnline] = useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine !== false,
  );
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  if (online) return null;
  return (
    <p
      role="status"
      className="sticky top-0 z-50 bg-saffron px-4 py-2 text-center text-sm font-semibold text-[#2a1a00]"
    >
      You are offline. Sales and stock need a connection; your work is safe once you are back.
    </p>
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
      className="relative grid size-10 place-items-center rounded-xl border border-line bg-surface text-ink-2 transition-colors hover:border-brand hover:text-brand-dark"
    >
      <Icon name="bell" />
      {unread > 0 && (
        <span
          aria-hidden="true"
          className="absolute -top-1.5 -right-1.5 min-w-5 rounded-full border-2 border-canvas bg-saffron px-1 text-center text-[10px] leading-4 font-bold text-[#2a1a00]"
        >
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}

function LedgerPreview() {
  const rows = [
    ["Sale S-0041", "Water Bottle 1L", "−2", "118"],
    ["PO-0007 received", "Coffee Beans 250g", "+40", "54"],
    ["Damaged in store", "Kraft Bag Medium", "−1", "7"],
  ];
  return (
    <div className="w-full max-w-md rounded-2xl border border-white/10 bg-white/[0.04] p-5 backdrop-blur">
      <div className="flex items-center justify-between text-sm text-sidebar-ink">
        <span>Stock ledger, today</span>
        <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs">live</span>
      </div>
      <ul className="mt-4 flex flex-col divide-y divide-white/10">
        {rows.map(([why, what, change, left]) => (
          <li key={why} className="flex items-center gap-3 py-3 text-sm">
            <span className="min-w-0 flex-1">
              <span className="block truncate text-white">{what}</span>
              <span className="block truncate text-xs text-sidebar-ink">{why}</span>
            </span>
            <span
              className={`figure text-base ${change.startsWith("+") ? "text-[#3ccb95]" : "text-[#f2b655]"}`}
            >
              {change}
            </span>
            <span className="w-14 text-right text-xs text-sidebar-ink tabular">{left} left</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SignedOutShell() {
  return (
    <div className="grid min-h-screen bg-canvas lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <aside className="relative hidden overflow-hidden bg-evergreen p-10 text-white lg:flex lg:flex-col lg:justify-between xl:p-14">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:linear-gradient(rgb(255_255_255)_1px,transparent_1px),linear-gradient(90deg,rgb(255_255_255)_1px,transparent_1px)] [background-size:44px_44px]"
        />
        <Link to="/" className="relative self-start">
          <Logo />
        </Link>
        <div className="relative flex flex-col gap-8">
          <p className="max-w-md font-display text-[2.4rem] leading-[1.05] font-bold tracking-[-0.03em] text-balance">
            Every sale, delivery and count lands in one ledger.
          </p>
          <LedgerPreview />
        </div>
        <p className="relative text-sm text-sidebar-ink">StockPilot by Discovery</p>
      </aside>
      <div className="flex min-w-0 flex-col">
        <div className="flex items-center justify-between gap-3 p-4 sm:p-6">
          <Link to="/" className="rounded-xl bg-evergreen px-3 py-2 lg:invisible">
            <Logo size={28} />
          </Link>
          <div className="flex items-center gap-2">
            <Link to="/" className="btn-ghost hidden sm:inline-flex">
              About StockPilot
            </Link>
            <ThemeSwitch />
          </div>
        </div>
        <main className="flex flex-1 items-start justify-center px-4 pb-12 sm:items-center">
          <div className="card w-full max-w-[26rem] p-6 sm:p-9">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

function SubscriptionBanner({ user }) {
  const plan = user?.business?.subscription;
  if (!plan?.required) return null;
  const soon = plan.days_left <= 3 && (plan.status === "trial" || plan.status === "active");
  if (!soon && plan.status !== "grace" && plan.status !== "expired") return null;
  const text = {
    trial: `Your free trial ends in ${plan.days_left} day${plan.days_left === 1 ? "" : "s"}.`,
    active: `Your subscription ends in ${plan.days_left} day${plan.days_left === 1 ? "" : "s"}.`,
    grace: `Your subscription has ended. Everything keeps working until ${longDate(plan.grace_until)}.`,
    expired: "Your subscription has ended, so changes are paused. Your data is safe.",
  }[plan.status];
  return (
    <div
      role="status"
      className={`mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl p-4 text-sm ${
        plan.status === "expired" ? "bg-danger-soft text-danger" : "bg-warn-soft text-warn"
      }`}
    >
      <span className="font-medium">{text}</span>
      {user.role === "admin" ? (
        <Link to="/billing" className="btn-secondary">
          Renew now
        </Link>
      ) : (
        <span>Ask your administrator to renew it.</span>
      )}
    </div>
  );
}

export default function Layout() {
  const { user, signOut, hasRole, canDo } = useAuth();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => setMenuOpen(false), [pathname]);

  if (!user) {
    return (
      <ErrorBoundary key={pathname}>
        {pathname === "/" ? <Outlet /> : <SignedOutShell />}
      </ErrorBoundary>
    );
  }

  const visible = groups
    .map((group) => ({
      ...group,
      links: group.links.filter(
        (link) =>
          (!link.roles || hasRole(...link.roles)) &&
          (!link.jobs || canDo(...link.jobs)) &&
          (!link.owners || user?.platform_owner),
      ),
    }))
    .filter((group) => group.links.length);
  const here = whereAmI(pathname);

  return (
    <>
      <OfflineBanner />
      <div className="min-h-screen bg-canvas text-ink lg:flex">
        <aside
          id="sidebar"
          className={`fixed inset-y-0 left-0 z-40 flex w-[17rem] flex-col bg-evergreen text-white transition-[transform,visibility] duration-200 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
            menuOpen ? "translate-x-0 shadow-2xl" : "max-lg:invisible max-lg:-translate-x-full"
          }`}
        >
          <div className="flex items-center justify-between px-5 pt-5 pb-4">
            <Link to="/" aria-label="StockPilot, dashboard">
              <Logo size={34} />
            </Link>
            <button
              type="button"
              onClick={() => setMenuOpen(false)}
              aria-label="Close menu"
              className="grid size-9 place-items-center rounded-lg text-sidebar-ink hover:bg-white/10 hover:text-white lg:hidden"
            >
              <Icon name="close" />
            </button>
          </div>

          <nav
            aria-label="Main"
            className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 pb-4 [scrollbar-width:thin]"
          >
            {visible.map((group) => (
              <div key={group.title} className="flex flex-col gap-0.5">
                <p className="px-3 pb-1 text-xs font-medium text-sidebar-ink/60">{group.title}</p>
                {group.links.map((link) => (
                  <NavLink
                    key={link.label}
                    to={link.to}
                    end={link.end}
                    className={({ isActive }) =>
                      `relative flex items-center gap-3 rounded-xl px-3 py-2 text-[0.9rem] transition-colors ${
                        isActive
                          ? "bg-evergreen-2 font-semibold text-white shadow-[inset_0_0_0_1px_rgb(255_255_255/0.06)] before:absolute before:top-2 before:bottom-2 before:-left-3 before:w-1 before:rounded-r-full before:bg-saffron"
                          : "text-sidebar-ink hover:bg-white/5 hover:text-white"
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon name={link.icon} className={isActive ? "text-saffron" : ""} />
                        {link.label}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>

          <div className="m-3 flex items-center gap-3 rounded-2xl bg-black/15 p-3 ring-1 ring-white/5">
            <Avatar name={user.full_name} size={38} />
            <span className="min-w-0 flex-1 text-sm leading-tight">
              <span className="block truncate font-semibold">{user.full_name}</span>
              <span className="block truncate text-xs text-sidebar-ink">
                {ROLE_NAMES[user.role] || user.role}
                {user.business?.name ? ` · ${user.business.name}` : ""}
              </span>
            </span>
            <button
              type="button"
              onClick={signOut}
              title="Sign out"
              className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs text-sidebar-ink hover:bg-white/10 hover:text-white"
            >
              <Icon name="logout" size={16} />
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
            className="fixed inset-0 z-30 bg-[#06201b]/50 backdrop-blur-[2px] lg:hidden"
          />
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line bg-canvas/80 px-4 backdrop-blur-md md:px-8">
            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              aria-label="Open menu"
              aria-controls="sidebar"
              aria-expanded={menuOpen}
              className="grid size-10 place-items-center rounded-xl border border-line bg-surface lg:hidden"
            >
              <Icon name="menu" />
            </button>
            {here && (
              <p className="flex min-w-0 items-center gap-1.5 text-sm">
                <span className="hidden text-muted sm:inline">{here.section}</span>
                <Icon name="chevron" size={14} className="hidden text-line-strong sm:block" />
                <span className="truncate font-medium">{here.page}</span>
              </p>
            )}
            <div className="ml-auto flex items-center gap-2">
              <span className="mr-2 hidden items-center gap-2 text-sm text-muted xl:flex">
                <Icon name="clock" size={16} />
                {new Date().toLocaleDateString("en-GB", {
                  weekday: "long",
                  day: "numeric",
                  month: "long",
                })}
              </span>
              <ThemeSwitch />
              <Bell />
            </div>
          </header>
          <main className="mx-auto w-full max-w-[90rem] min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
            <SubscriptionBanner user={user} />
            <ErrorBoundary key={pathname}>
              <Outlet />
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </>
  );
}
