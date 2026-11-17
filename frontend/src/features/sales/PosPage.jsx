import { useEffect, useMemo, useState } from "react";

import { api } from "../../api/client";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
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
          items: cart.map((line) => ({
            product_id: line.product.id,
            quantity: line.quantity,
          })),
        },
      });
      setSale(saved);
      setCart([]);
      setSearch("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (sale) {
    return (
      <section className="mx-auto flex w-full max-w-sm flex-col gap-4">
        <p role="status" className="rounded-lg bg-mint p-3 text-sm">
          Sale {sale.receipt_number} saved · {money(sale.total)}
        </p>
        <Receipt sale={sale}>
          <button type="button" onClick={() => setSale(null)} className="btn-primary">
            New sale
          </button>
        </Receipt>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-4">
      <PageHeader title="New sale" subtitle="Tap a product to add it to the sale." />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="flex min-w-0 flex-col gap-3">
          <label htmlFor="pos-search" className="sr-only">
            Search products
          </label>
          <input
            id="pos-search"
            type="search"
            placeholder="Search by name or SKU"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="input w-full"
          />
          {loadError && (
            <p role="alert" className="text-danger">
              {loadError}
            </p>
          )}
          {results === null && !loadError && <SkeletonCards count={3} />}
          {results?.length === 0 && <p className="text-muted">No products match.</p>}
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
            {results?.map((product) => {
              const out = product.quantity === 0;
              return (
                <li key={product.id}>
                  <button
                    type="button"
                    disabled={out}
                    onClick={() => add(product)}
                    aria-label={`Add ${product.name}`}
                    className="card flex h-full w-full flex-col gap-1 p-3 text-left transition hover:border-brand disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <span className="font-semibold">{product.name}</span>
                    <span className="text-xs text-muted">{product.sku}</span>
                    <span className="mt-auto flex items-end justify-between gap-2 pt-2">
                      <span className="font-display font-bold">{money(product.selling_price)}</span>
                      <span
                        className={`text-xs ${product.is_low_stock ? "text-danger" : "text-muted"}`}
                      >
                        {out ? "Out of stock" : `${product.quantity} left`}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <aside
          aria-label="Current sale"
          className="card flex flex-col gap-4 p-5 lg:sticky lg:top-20 lg:self-start"
        >
          <h2 className="text-lg font-bold">Current sale</h2>
          {cart.length === 0 ? (
            <p className="text-sm text-muted">Nothing added yet.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-line">
              {cart.map(({ product, quantity }) => (
                <li key={product.id} className="flex items-center gap-2 py-2">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{product.name}</span>
                    <span className="text-xs text-muted">{money(product.selling_price)} each</span>
                  </span>
                  <button
                    type="button"
                    aria-label={`One less ${product.name}`}
                    onClick={() => setQuantity(product, quantity - 1)}
                    className="grid size-8 place-items-center rounded-lg border border-line"
                  >
                    <Icon name="minus" size={14} />
                  </button>
                  <span className="w-7 text-center font-semibold" data-testid={`qty-${product.id}`}>
                    {quantity}
                  </span>
                  <button
                    type="button"
                    aria-label={`One more ${product.name}`}
                    onClick={() => add(product)}
                    className="grid size-8 place-items-center rounded-lg border border-line"
                  >
                    <Icon name="plus" size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-semibold">Payment</legend>
            <div className="grid grid-cols-3 gap-2">
              {Object.entries(PAYMENT_LABELS).map(([value, label]) => (
                <label
                  key={value}
                  className={`cursor-pointer rounded-lg border px-2 py-2 text-center text-sm ${
                    payment === value ? "border-brand bg-mint font-semibold" : "border-line"
                  }`}
                >
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

          <div className="flex items-baseline justify-between border-t border-line pt-3">
            <span className="text-muted">Total</span>
            <span className="font-display text-2xl font-bold" data-testid="cart-total">
              {money(total)}
            </span>
          </div>
          {error && (
            <p role="alert" className="rounded-lg bg-danger-soft p-3 text-sm text-danger">
              {error}
            </p>
          )}
          <button
            type="button"
            disabled={!cart.length || busy}
            onClick={complete}
            className="btn-primary py-3"
          >
            {busy ? "Saving…" : "Complete sale"}
          </button>
        </aside>
      </div>
    </section>
  );
}