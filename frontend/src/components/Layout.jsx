import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/products", label: "Products" },
  { to: "/suppliers", label: "Suppliers" },
  { to: "/status", label: "System status" },
];

export default function Layout() {
  return (
    <div className="min-h-screen md:flex">
      <aside className="bg-evergreen p-4 md:min-h-screen md:w-56">
        <div className="mb-4 flex items-center gap-2 text-lg font-bold text-white">
          <span className="rounded-md bg-brand px-2 py-1 text-sm">SP</span> StockPilot
        </div>
        <nav aria-label="Main" className="flex gap-1 md:flex-col">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm ${isActive ? "bg-brand text-white" : "text-white/80 hover:text-white"}`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}