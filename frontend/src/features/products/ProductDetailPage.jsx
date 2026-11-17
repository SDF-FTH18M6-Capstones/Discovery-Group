import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { STOCK_MANAGERS } from "../../auth/roles";
import Icon from "../../components/Icon";
import { SkeletonCards } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { EmptyState, Panel } from "../../components/ui";
import { dateTime, money } from "../../format";

function ShelfCard({ product }) {
  const target = Math.max(product.reorder_level * 3, product.quantity, 1);
  const share = (product.quantity / target) * 100;
  const reorderAt = (product.reorder_level / target) * 100;
  const tone =
    product.quantity === 0 ? "bg-danger" : product.is_low_stock ? "bg-saffron" : "bg-brand";
  return (
    <div className="panel flex flex-col gap-5 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm text-muted">On the shelf</p>
          <p className="figure text-6xl leading-none">{product.quantity}</p>
        </div>
        <span className="grid size-12 place-items-center rounded-2xl bg-mint text-brand-dark">
          <Icon name="box" size={22} />
        </span>
      </div>
      <div className="flex flex-col gap-2">
        <div className="relative h-3 rounded-full bg-surface-2 ring-1 ring-line">
          <span
            className={`absolute inset-y-0 left-0 rounded-full ${tone}`}
            style={{ width: `${Math.max(share, product.quantity ? 2 : 0)}%` }}
          />
          <span
            aria-hidden="true"
            className="absolute -top-1 -bottom-1 w-0.5 rounded bg-ink"
            style={{ left: `${reorderAt}%` }}
          />
        </div>
        <p className="text-sm text-muted">
          Reorder when it reaches {product.reorder_level}.{" "}
          {product.quantity > product.reorder_level
            ? `${product.quantity - product.reorder_level} to go.`
            : "Time to order more."}
        </p>
      </div>
    </div>
  );
}

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
      <section className="flex flex-col items-start gap-3 py-10">
        <h1 className="page-title">Product not found</h1>
        <p className="text-muted">{error}</p>
        <Link to="/products" className="btn-secondary">
          Back to products
        </Link>
      </section>
    );
  }
  if (!product) return <SkeletonCards count={2} />;

  const margin = Number(product.selling_price) - Number(product.cost_price);
  const marginShare = Number(product.selling_price)
    ? Math.round((margin / Number(product.selling_price)) * 100)
    : 0;

  return (
    <section className="flex flex-col gap-6">
      <Link to="/products" className="link inline-flex items-center gap-1 self-start text-sm">
        <Icon name="chevron" size={14} className="rotate-180" />
        Products
      </Link>
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="page-title">{product.name}</h1>
          {product.quantity === 0 ? (
            <StatusBadge value="out_of_stock" />
          ) : (
            product.is_low_stock && <StatusBadge value="low_stock" />
          )}
        </div>
        <p className="flex flex-wrap items-center gap-3 text-muted">
          <span className="code rounded-md bg-surface-2 px-2 py-0.5">{product.sku}</span>
          <span>{product.category_name}</span>
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <ShelfCard product={product} />
        <dl className="panel grid grid-cols-2 xl:grid-cols-4">
          {[
            ["Selling price", money(product.selling_price)],
            ["Cost price", money(product.cost_price)],
            ["Margin per unit", money(margin)],
            ["Margin", `${marginShare}%`],
          ].map(([label, value]) => (
            <div
              key={label}
              className="flex flex-col justify-between gap-3 p-5 shadow-[1px_0_0_var(--sp-line),0_1px_0_var(--sp-line)]"
            >
              <dt className="text-sm text-muted">{label}</dt>
              <dd className="figure text-2xl whitespace-nowrap">{value}</dd>
            </div>
          ))}
          <div className="col-span-2 flex items-center gap-3 bg-surface-2 p-5 text-sm text-muted xl:col-span-4">
            <Icon name="ledger" size={18} className="text-brand-dark" />
            Prices on receipts always come from here, so a change applies to the next sale.
          </div>
        </dl>
      </div>

      {canTrace && (
        <Panel title="Stock trace" subtitle="Every change to this product, newest first">
          {trace?.length === 0 ? (
            <EmptyState icon="ledger" title="No stock changes yet" />
          ) : (
            <ol className="flex flex-col">
              {trace?.map((movement) => (
                <li
                  key={movement.id}
                  className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-4 border-t border-line px-5 py-3 first:border-t-0"
                >
                  <span
                    className={`figure grid size-11 place-items-center rounded-xl text-sm ${
                      movement.change < 0 ? "bg-danger-soft text-danger" : "bg-mint text-brand-dark"
                    }`}
                  >
                    {movement.change > 0 ? `+${movement.change}` : movement.change}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{movement.reason}</span>
                    <span className="text-xs text-muted">
                      {movement.user_name}, {dateTime(movement.created_at)}
                    </span>
                  </span>
                  <StatusBadge value={movement.type} />
                </li>
              ))}
            </ol>
          )}
        </Panel>
      )}
    </section>
  );
}
