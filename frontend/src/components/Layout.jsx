import { Link, NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { PROCUREMENT, ROLE_NAMES, STOCK_MANAGERS } from "../auth/roles";

const links = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/products", label: "Products" },
  { to: "/categories", label: "Categories" },
  { to: "/suppliers", label: "Suppliers", roles: PROCUREMENT },
  { to: "/requests", label: "My requests" },
  { to: "/approvals", label: "Approvals", roles: PROCUREMENT },
  { to: "/assets", label: "Assets", roles: STOCK_MANAGERS },
  { to: "/assets", label: "My assets", roles: ["procurement", "sales", "employee"] },
  { to: "/users", label: "Users", roles: ["admin"] },
  { to: "/status", label: "System status" },
];

export default function Layout() {
  const { user, signOut, hasRole } = useAuth();
  const visible = links.filter((link) => !link.roles || hasRole(...link.roles));

  return (
    <div className="min-h-screen md:flex">
      <aside className="flex flex-col gap-4 bg-evergreen p-4 md:min-h-screen md:w-56">
        <div className="flex items-center gap-2 text-lg font-bold text-white">
          <span className="rounded-md bg-brand px-2 py-1 text-sm">SP</span> StockPilot
        </div>
        {user && (
          <nav aria-label="Main" className="flex flex-wrap gap-1 md:flex-col">
            {visible.map((link) => (
              <NavLink
                key={link.label}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-2 text-sm ${isActive ? "bg-brand text-white" : "text-white/80 hover:text-white"}`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        )}
        <div className="text-sm text-white/80 md:mt-auto">
          {user ? (
            <div className="flex flex-col gap-2">
              <span>
                <span className="block font-semibold text-white">{user.full_name}</span>
                {ROLE_NAMES[user.role] || user.role}
              </span>
              <button
                type="button"
                onClick={signOut}
                className="self-start rounded-md border border-white/40 px-3 py-1 text-white"
              >
                Sign out
              </button>
            </div>
          ) : (
            <Link to="/login" className="text-white underline">
              Sign in
            </Link>
          )}
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}
