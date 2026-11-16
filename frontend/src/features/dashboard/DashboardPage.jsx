import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { PROCUREMENT, ROLE_NAMES, STOCK_MANAGERS } from "../../auth/roles";

function cardsFor(hasRole) {
  const seesAllRequests = hasRole(...PROCUREMENT);
  const managesAssets = hasRole(...STOCK_MANAGERS);
  const cards = [
    {
      key: "low",
      label: "Products low on stock",
      path: "/api/products/?low_stock=true&per_page=1",
      to: "/products",
    },
    seesAllRequests
      ? {
          key: "pending",
          label: "Requests waiting for a decision",
          path: "/api/requests/?status=pending&per_page=1",
          to: "/approvals",
        }
      : {
          key: "pending",
          label: "My requests still pending",
          path: "/api/requests/?status=pending&mine=true&per_page=1",
          to: "/requests",
        },
    {
      key: "assets",
      label: managesAssets ? "Assets in the register" : "Assets you hold",
      path: "/api/assets/?per_page=1",
      to: "/assets",
    },
  ];
  if (seesAllRequests) {
    cards.push({
      key: "suppliers",
      label: "Suppliers",
      path: "/api/suppliers/?per_page=1",
      to: "/suppliers",
    });
  }
  return cards;
}

export default function DashboardPage() {
  const { user, hasRole } = useAuth();
  const [counts, setCounts] = useState({});
  const [error, setError] = useState("");
  const cards = cardsFor(hasRole);
  const paths = cards.map((card) => card.path).join("|");

  useEffect(() => {
    let cancelled = false;
    Promise.all(paths.split("|").map((path) => api(path).then((data) => data.count)))
      .then((values) => {
        if (!cancelled) setCounts(Object.fromEntries(values.map((value, i) => [i, value])));
      })
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [paths]);

  return (
    <section className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">Welcome, {user.full_name.split(" ")[0]}</h1>
        <p className="text-muted">Signed in as {ROLE_NAMES[user.role] || user.role}.</p>
      </div>

      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card, i) => (
          <Link
            key={card.key}
            to={card.to}
            className="flex flex-col gap-1 rounded-xl border border-line bg-white p-4 hover:border-brand"
          >
            <span className="text-sm text-muted">{card.label}</span>
            <span className="text-3xl font-bold" data-testid={`count-${card.key}`}>
              {counts[i] ?? "…"}
            </span>
          </Link>
        ))}
      </div>

      <div className="flex flex-wrap gap-3">
        <Link to="/requests" className="rounded-lg bg-brand px-4 py-2 font-semibold text-white">
          New request
        </Link>
        <Link to="/products" className="rounded-lg border border-line bg-white px-4 py-2">
          Browse products
        </Link>
      </div>
    </section>
  );
}
