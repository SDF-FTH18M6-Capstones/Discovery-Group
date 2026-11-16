
import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

// `roles` = who sees the link. No `roles` = every signed-in user.
const links = [
  { to: "/products", label: "Products" },
  { to: "/suppliers", label: "Suppliers", roles: ["admin", "procurement"] },
  { to: "/status", label: "System status" },
];

const ROLE_NAMES = {
  admin: "Administrator",
  procurement: "Procurement Manager",
  inventory: "Inventory Manager",
  sales: "Sales Attendant",
  employee: "Employee",
};

export default function Layout() {
  const { user, signOut, hasRole } = useAuth();
  const visible = links.filter(
    (link) => !link.roles || hasRole(...link.roles)
  );

  return (
    <div className="min-h-screen md:flex">
      <aside className="flex flex-col gap-4 bg-evergreen p-4 md:min-h-screen md:w-56">

        {/* StockPilot Logo */}
        <Link to="/products" className="flex items-center gap-3 py-2">
          <img
            src="/stockpilotlogo.png"
            alt="StockPilot Logo"
            className="h-12 w-12 rounded-lg bg-white object-contain"
          />
          <span className="text-lg font-bold text-white">
            StockPilot
          </span>
        </Link>

        {user && (
          <nav aria-label="Main" className="flex flex-wrap gap-1 md:flex-col">
            {visible.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-2 text-sm ${
                    isActive
                      ? "bg-brand text-white"
                      : "text-white/80 hover:text-white"
                  }`
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
                <span className="block font-semibold text-white">
                  {user.full_name}
                </span>
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
