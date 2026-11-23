import { useEffect, useMemo, useState } from "react";

import { api, mediaUrl, newIdempotencyKey } from "../../api/client";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import { Avatar } from "../../components/ui";
import { SkeletonCards } from "../../components/Skeleton";
import { PAYMENT_LABELS, money } from "../../format";
import Receipt from "./Receipt";

export default function PosPage() {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [cart, setCart] = useState([]); // [{ product, quantity }]
  const [payment, setPayment] = useState("cash");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sale, setSale] = useState(null);
  // One key per sale: a double tap or a retry after a dropped connection saves one sale (US-26).
  const [saleKey, setSaleKey] = useState(newIdempotencyKey);

  useEffect(() => {
    let cancelled = false;
    const query = new URLSearchParams({ per_page: 24, search });
    const timer = setTimeout(() => {
      api(`/api/products/?${query}`)
        .then((data) => !cancelled && (setResults(data.results), setLoadError("")))
        .catch((err) => !cancelled && setLoadError(err.message));
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [search]);

  const total = useMemo(
    () => cart.reduce((sum, line) => sum + Number(line.product.selling_price) * line.quantity, 0),
    [cart],
  );

  const setQuantity = (product, quantity) => {
    setError("");
    setSaleKey(newIdempotencyKey()); // a different cart is a different sale
    setCart((current) => {
      const capped = Math.min(Math.max(quantity, 0), product.quantity);
      const rest = current.filter((line) => line.product.id !== product.id);
      if (!capped) return rest;
      const existing = current.find((line) => line.product.id === product.id);
      return existing
        ? current.map((line) =>
            line.product.id === product.id ? { ...line, quantity: capped } : line,
          )
        : [...current, { product, quantity: capped }];
    });
  };

  const add = (product) => {
    const inCart = cart.find((line) => line.product.id === product.id)?.quantity || 0;
    if (inCart >= product.quantity) {
      setError(`Only ${product.quantity} ${product.name} in stock.`);
      return;
    }
    setQuantity(product, inCart + 1);
  };

  const complete = async () => {
    setBusy(true);
    setError("");
    try {
      const saved = await api("/api/sales/", {
        method: "POST",
        body: {
          payment_method: payment,
          items: cart.map((line) => ({ product_id: line.product.id, quantity: line.quantity })),
          idempotency_key: saleKey,
        },
      });
      setSale(saved);
      setCart([]);
      setSearch("");
      setSaleKey(newIdempotencyKey());
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (sale) {
    return (
      <section className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="panel flex flex-col items-start gap-5 p-6 sm:p-8">
          <span className="grid size-14 place-items-center rounded-2xl bg-mint text-brand-dark">
            <Icon name="check" size={28} />
          </span>
          <div className="flex flex-col gap-1">
            <h1 className="page-title">Sale complete</h1>
            <p role="status" className="text-lg text-muted">
              Sale {sale.receipt_number} saved: {money(sale.total)} by{" "}
              {PAYMENT_LABELS[sale.payment_method] || sale.payment_method}.
            </p>
          </div>
          <p className="text-sm text-muted">
            The shelf counts have already gone down and the sale is in the stock ledger.
          </p>
          <button type="button" onClick={() => setSale(null)} className="btn-primary px-5 py-3">
            <Icon name="plus" size={16} />
            New sale
          </button>
        </div>
        <Receipt sale={sale} />
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-6 pb-20 lg:pb-0">
      <PageHeader
        title="New sale"
        subtitle="Tap a product to add it. Prices come from the catalogue."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_25rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <label htmlFor="pos-search" className="sr-only">
            Search products
          </label>
          <div className="relative">
            <Icon
              name="search"
              size={18}
              className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-muted"
            />
            <input
              id="pos-search"
              type="search"
              placeholder="Search by name or SKU"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="input min-h-12 w-full pl-11 text-base"
            />
          </div>
          {loadError && (
            <p role="alert" className="text-danger">
              {loadError}
            </p>
          )}
          {results === null && !loadError && <SkeletonCards count={3} />}
          {results?.length === 0 && <p className="text-muted">No products match.</p>}
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 2xl:grid-cols-4">
            {results?.map((product) => {
              const out = product.quantity === 0;
              const inCart = cart.find((line) => line.product.id === product.id)?.quantity;
              return (
                <li key={product.id}>
                  <button
                    type="button"
                    disabled={out}
                    onClick={() => add(product)}
                    aria-label={`Add ${product.name}`}
                    className={`group relative flex h-full w-full flex-col gap-3 rounded-2xl border bg-surface p-4 text-left transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 hover:shadow-[var(--sp-shadow)] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 ${
                      inCart
                        ? "border-brand ring-2 ring-brand/25"
                        : "border-line hover:border-line-strong"
                    }`}
                  >
                    <span className="flex items-start justify-between gap-2">
                      {product.image_url ? (
                        <img
                          src={mediaUrl(product.image_url)}
                          alt=""
                          loading="lazy"
                          className="size-10 rounded-xl object-cover"
                        />
                      ) : (
                        <Avatar name={product.name} size={40} className="rounded-xl" />
                      )}
                      {inCart && (
                        <span className="grid size-7 place-items-center rounded-full bg-brand text-xs font-bold text-on-brand">
                          {inCart}
                        </span>
                      )}
                    </span>
                    <span className="flex flex-col gap-0.5">
                      <span className="font-semibold leading-snug">{product.name}</span>
                      <span className="code text-muted">{product.sku}</span>
                    </span>
                    <span className="mt-auto flex flex-wrap items-end justify-between gap-x-2 gap-y-1">
                      <span className="figure text-lg whitespace-nowrap">
                        {money(product.selling_price)}
                      </span>
                      <span
                        className={`text-xs whitespace-nowrap ${out ? "text-danger" : product.is_low_stock ? "text-saffron-ink" : "text-muted"}`}
                      >
                        {out ? "Out of stock" : `Max ${product.quantity} available`}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <aside
          id="current-sale"
          aria-label="Current sale"
          className="panel flex flex-col lg:sticky lg:top-24 lg:self-start"
        >
          <div className="flex items-center justify-between bg-evergreen px-5 py-4 text-white">
            <h2 className="text-lg font-bold">Current sale</h2>
            <span className="rounded-full bg-white/10 px-2.5 py-0.5 text-xs">
              {cart.reduce((sum, line) => sum + line.quantity, 0)} items
            </span>
          </div>
          <div className="flex flex-col gap-5 p-5">
            {cart.length === 0 ? (
              <p className="rounded-xl border border-dashed border-line-strong px-4 py-8 text-center text-sm text-muted">
                Nothing added yet. Tap a product to start.
              </p>
            ) : (
              <ul className="flex flex-col divide-y divide-line">
                {cart.map(({ product, quantity }) => (
                  <li key={product.id} className="flex items-center gap-2 py-2">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold">{product.name}</span>
                      <span className="text-xs text-muted">
                        {money(Number(product.selling_price) * quantity)}
                      </span>
                    </span>
                    <span className="flex items-center rounded-full border border-line-strong">
                      <button
                        type="button"
                        aria-label={`One less ${product.name}`}
                        onClick={() => setQuantity(product, quantity - 1)}
                        className="grid size-8 place-items-center rounded-full hover:bg-surface-2"
                      >
                        <Icon name="minus" size={14} />
                      </button>
                      <span
                        className="w-7 text-center font-semibold"
                        data-testid={`qty-${product.id}`}
                      >
                        {quantity}
                      </span>
                      <button
                        type="button"
                        aria-label={`One more ${product.name}`}
                        onClick={() => add(product)}
                        className="grid size-8 place-items-center rounded-full hover:bg-surface-2"
                      >
                        <Icon name="plus" size={14} />
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            )}

            <fieldset className="flex flex-col gap-2">
              <legend className="mb-2 text-sm font-medium text-ink-2">Payment</legend>
              <div className="grid grid-cols-3 gap-2">
                {Object.entries(PAYMENT_LABELS).map(([value, label]) => (
                  <label
                    key={value}
                    className={`flex cursor-pointer flex-col items-center gap-1 rounded-xl border px-2 py-2.5 text-center text-sm transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-saffron ${
                      payment === value
                        ? "border-brand bg-mint font-semibold text-brand-dark"
                        : "border-line-strong hover:border-brand"
                    }`}
                  >
                    <Icon name={{ cash: "cash", mpesa: "phone", card: "card" }[value]} size={18} />
                    <input
                      type="radio"
                      name="payment"
                      value={value}
                      checked={payment === value}
                      onChange={() => setPayment(value)}
                      className="sr-only"
                    />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="flex items-baseline justify-between border-t border-dashed border-line-strong pt-4">
              <span className="text-muted">Total</span>
              <span className="figure text-3xl" data-testid="cart-total">
                {money(total)}
              </span>
            </div>
            {error && (
              <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
                {error}
              </p>
            )}
            <button
              type="button"
              disabled={!cart.length || busy}
              onClick={complete}
              className="btn-primary min-h-12 text-base"
            >
              {busy ? "Saving…" : "Complete sale"}
            </button>
          </div>
        </aside>
      </div>

      {cart.length > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-20 flex items-center justify-between gap-3 border-t border-line bg-surface/95 px-4 py-3 shadow-[0_-12px_30px_-20px_rgb(0_0_0/0.4)] backdrop-blur lg:hidden">
          <span className="text-sm">
            {cart.reduce((sum, line) => sum + line.quantity, 0)} items,{" "}
            <strong>{money(total)}</strong>
          </span>
          <a href="#current-sale" className="btn-primary">
            Review sale
          </a>
        </div>
      )}
    </section>
  );
}
