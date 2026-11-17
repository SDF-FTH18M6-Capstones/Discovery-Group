import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { STOCK_MANAGERS } from "../../auth/roles";
import { SkeletonCards } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { dateTime, money } from "../../format";

export default function ProductDetailPage() {
  const { id } = useParams();
  const { hasRole } = useAuth();
  const canTrace = hasRole(...STOCK_MANAGERS);
  const [product, setProduct] = useState(null);
  const [trace, setTrace] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/api/products/${id}`)
      .then(setProduct)
      .catch((err) => setError(err.status === 404 ? "This product does not exist." : err.message));
    if (canTrace) {
      api(`/api/stock/movements?product_id=${id}&per_page=20`)
        .then((data) => setTrace(data.results))
        .catch(() => setTrace([]));
    }
  }, [id, canTrace]);

  if (error) {
    return (
      <section className="flex flex-col gap-3">
        <h1 className="page-title">Product not found</h1>
        <p className="text-muted">{error}</p>
        <Link to="/products" className="link">
          Back to products
        </Link>
      </section>
    );
  }
  if (!product) return <SkeletonCards count={2} />;

  const margin = Number(product.selling_price) - Number(product.cost_price);
  const facts = [
    ["In stock", product.quantity],
    ["Reorder at", product.reorder_level],
    ["Selling price", money(product.selling_price)],
    ["Cost price", money(product.cost_price)],
    ["Margin per unit", money(margin)],
  ];

  return (
    <section className="flex flex-col gap-5">
      <Link to="/products" className="link text-sm">
        ← Products
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="page-title">{product.name}</h1>
        {product.quantity === 0 ? (
          <StatusBadge value="out_of_stock" />
        ) : (
          product.is_low_stock && <StatusBadge value="low_stock" />
        )}
      </div>
      <p className="-mt-3 text-muted">
        {product.sku} · {product.category_name}
      </p>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        {facts.map(([label, value]) => (
          <div key={label} className="card flex flex-col gap-1 p-4">
            <dt className="text-xs tracking-wide text-muted uppercase">{label}</dt>
            <dd className="font-display text-xl font-bold">{value}</dd>
          </div>
        ))}
      </dl>

      {canTrace && (
        <div className="card overflow-x-auto">
          <h2 className="p-4 pb-2 text-lg font-bold">Stock trace</h2>
          <table className="w-full text-left text-sm">
            <thead className="table-head">
              <tr>
                <th className="p-3">When</th>
                <th className="p-3">Type</th>
                <th className="p-3 text-right">Change</th>
                <th className="p-3">Reason</th>
                <th className="p-3">By</th>
              </tr>
            </thead>
            <tbody>
              {trace?.length === 0 && (
                <tr>
                  <td colSpan="5" className="p-3 text-muted">
                    No stock changes yet.
                  </td>
                </tr>
              )}
              {trace?.map((movement) => (
                <tr key={movement.id} className="border-t border-line">
                  <td className="p-3 whitespace-nowrap text-muted">
                    {dateTime(movement.created_at)}
                  </td>
                  <td className="p-3">
                    <StatusBadge value={movement.type} />
                  </td>
                  <td
                    className={`p-3 text-right font-semibold tabular-nums ${movement.change < 0 ? "text-danger" : "text-brand-dark"}`}
                  >
                    {movement.change > 0 ? `+${movement.change}` : movement.change}
                  </td>
                  <td className="p-3">{movement.reason}</td>
                  <td className="p-3 text-muted">{movement.user_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}