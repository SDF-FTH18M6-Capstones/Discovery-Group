import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { SkeletonRows } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { EmptyState, StatStrip, StockMeter } from "../../components/ui";
import { amount } from "../../format";
import { categories, products } from "../../store";
import ProductForm from "./ProductForm";

export default function ProductsPage() {
  const dispatch = useDispatch();
  const { hasRole } = useAuth();
  const canEdit = hasRole("admin", "inventory");
  const list = useSelector((state) => state.products);
  const categoryOptions = useSelector((state) => state.categories.items);
  const [search, setSearch] = useState("");
  const [lowOnly, setLowOnly] = useState(false);
  const [categoryId, setCategoryId] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null); // null = closed, {} = new, product = edit
  const [totals, setTotals] = useState({});

  const params = {
    page,
    per_page: 10,
    search,
    low_stock: lowOnly ? "true" : "",
    category_id: categoryId,
  };
  const load = () => dispatch(products.fetchList(params));

  const loadTotals = () =>
    Promise.allSettled([
      api("/api/products/?per_page=1"),
      api("/api/products/?low_stock=true&per_page=1"),
    ]).then(([all, low]) =>
      setTotals({
        all: all.value?.count ?? "—",
        low: low.value?.count ?? "—",
      }),
    );

  useEffect(() => {
    dispatch(categories.fetchList({ per_page: 100 }));
    loadTotals();
  }, [dispatch]);

  useEffect(() => {
    dispatch(
      products.fetchList({
        page,
        per_page: 10,
        search,
        low_stock: lowOnly ? "true" : "",
        category_id: categoryId,
      }),
    );
  }, [dispatch, page, search, lowOnly, categoryId]);

  // On failure (for example a product that has sales) the server's message stays on
  // screen; reload only after a successful delete.
  const handleDelete = async (product) => {
    const result = await dispatch(products.deleteItem(product.id));
    if (products.deleteItem.fulfilled.match(result)) {
      load();
      loadTotals();
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <PageHeader
        title="Products"
        subtitle="Everything the shop sells, with what is on the shelf right now."
      >
        {canEdit && (
          <button type="button" onClick={() => setEditing({})} className="btn-primary">
            <Icon name="plus" size={16} />
            Add product
          </button>
        )}
      </PageHeader>

      <StatStrip
        items={[
          { label: "In the catalogue", value: totals.all, icon: "box", tone: "brand" },
          {
            label: "At or below reorder level",
            value: totals.low,
            icon: "alert",
            tone: "saffron",
          },
          {
            label: "Categories",
            value: categoryOptions.length,
            icon: "tag",
            tone: "muted",
            to: "/categories",
          },
        ]}
      />

      {editing && (
        <ProductForm
          key={editing.id || "new"}
          product={editing.id ? editing : null}
          categoryOptions={categoryOptions}
          onCancel={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
            loadTotals();
          }}
        />
      )}

      {list.error && (
        <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {list.error}
        </p>
      )}

      <div className="panel">
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
          <div className="relative min-w-0 flex-1 basis-64">
            <Icon
              name="search"
              size={16}
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted"
            />
            <label htmlFor="product-search" className="sr-only">
              Search products
            </label>
            <input
              id="product-search"
              type="search"
              placeholder="Search by name or SKU"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              className="input w-full pl-9"
            />
          </div>
          <div role="group" aria-label="Show" className="seg">
            <button
              type="button"
              aria-pressed={!lowOnly}
              onClick={() => {
                setLowOnly(false);
                setPage(1);
              }}
            >
              All
            </button>
            <button
              type="button"
              aria-pressed={lowOnly}
              onClick={() => {
                setLowOnly(true);
                setPage(1);
              }}
            >
              Running low
            </button>
          </div>
          <label htmlFor="product-category" className="sr-only">
            Filter by category
          </label>
          <select
            id="product-category"
            value={categoryId}
            onChange={(event) => {
              setCategoryId(event.target.value);
              setPage(1);
            }}
            className="input"
          >
            <option value="">All categories</option>
            {categoryOptions.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </div>

        <div className="relative overflow-x-auto">
          <table className="data-table w-full text-left text-sm">
            <thead className="table-head">
              <tr>
                <th className="px-5 py-3">Product</th>
                <th className="px-3 py-3">Category</th>
                <th className="px-3 py-3">Stock</th>
                <th className="px-3 py-3 text-right">Price (KES)</th>
                <th className="px-3 py-3 text-right">Margin</th>
                <th className="px-5 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.status === "loading" && <SkeletonRows cols={6} />}
              {list.status === "ready" &&
                list.items.map((product) => {
                  const margin = Number(product.selling_price) - Number(product.cost_price);
                  return (
                    <tr key={product.id} className="border-t border-line">
                      <td className="px-5 py-3">
                        <Link
                          to={`/products/${product.id}`}
                          className="font-semibold hover:text-brand-dark hover:underline"
                        >
                          {product.name}
                        </Link>
                        <span className="code block text-muted">{product.sku}</span>
                      </td>
                      <td className="px-3 py-3">
                        <span className="rounded-full bg-surface-2 px-2.5 py-1 text-xs text-ink-2">
                          {product.category_name}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <span className="flex items-center gap-3">
                          <span className="figure w-10 text-right">{product.quantity}</span>
                          <StockMeter quantity={product.quantity} reorder={product.reorder_level} />
                          {product.quantity === 0 ? (
                            <StatusBadge value="out_of_stock" />
                          ) : (
                            product.is_low_stock && <StatusBadge value="low_stock" />
                          )}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right font-medium">{product.selling_price}</td>
                      <td className="px-3 py-3 text-right text-muted">{amount(margin)}</td>
                      <td className="px-5 py-3">
                        {canEdit && (
                          <div className="flex justify-end gap-1">
                            <button
                              type="button"
                              onClick={() => setEditing(product)}
                              className="btn-ghost min-h-0 px-2.5 py-1.5"
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDelete(product)}
                              className="btn-ghost min-h-0 px-2.5 py-1.5 hover:text-danger"
                            >
                              Delete
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
          {list.status === "ready" && list.items.length === 0 && (
            <EmptyState
              icon="box"
              title="No products found"
              action={
                (search || lowOnly || categoryId) && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearch("");
                      setLowOnly(false);
                      setCategoryId("");
                    }}
                    className="btn-secondary"
                  >
                    Clear filters
                  </button>
                )
              }
            >
              {search || lowOnly || categoryId
                ? "Nothing matches these filters."
                : "Add the first product to start selling."}
            </EmptyState>
          )}
        </div>
        <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
      </div>
    </section>
  );
}
