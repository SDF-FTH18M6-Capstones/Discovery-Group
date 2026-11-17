import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { useAuth } from "../../auth/AuthContext";
import Pagination from "../../components/Pagination";
import { categories, products } from "../../store";
import ProductForm from "./ProductForm";

export default function ProductsPage() {
  const dispatch = useDispatch();
  const { hasRole } = useAuth();
  const canEdit = hasRole("admin", "inventory");
  const list = useSelector((state) => state.products);
  const categoryOptions = useSelector((state) => state.categories.items);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null); // null = closed, {} = new, product = edit

  const load = () => dispatch(products.fetchList({ page, per_page: 10, search }));

  useEffect(() => {
    dispatch(categories.fetchList({ per_page: 100 }));
  }, [dispatch]);

  useEffect(() => {
    dispatch(products.fetchList({ page, per_page: 10, search }));
  }, [dispatch, page, search]);

  const handleDelete = async (product) => {
    await dispatch(products.deleteItem(product.id));
    load();
  };

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Products</h1>
        {canEdit && (
          <button
            type="button"
            onClick={() => setEditing({})}
            className="rounded-lg bg-brand px-4 py-2 font-semibold text-white"
          >
            Add product
          </button>
        )}
      </div>

      {editing && (
        <ProductForm
          key={editing.id || "new"}
          product={editing.id ? editing : null}
          categoryOptions={categoryOptions}
          onCancel={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}

      <label htmlFor="product-search" className="sr-only">
        Search products
      </label>
      <input
        id="product-search"
        type="search"
        placeholder="Search by name or CODE"
        value={search}
        onChange={(event) => {
          setSearch(event.target.value);
          setPage(1);
        }}
        className="h-10 max-w-sm rounded-lg border border-line bg-gray-600 px-3"
      />

      {list.error && (
        <p role="alert" className="text-danger">
          {list.error}
        </p>
      )}

      <div className="relative overflow-x-auto rounded-xl border border-line bg-gray-600">
        <table className="w-full text-left text-sm">
          <thead className="bg-canvas text-muted">
            <tr>
              <th className="p-3">Product</th>
              <th className="p-3">CODE</th>
              <th className="p-3">Category</th>
              <th className="p-3 text-right">In stock</th>
              <th className="p-3 text-right">Price (KES)</th>
              <th className="p-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {list.status === "loading" && (
              <tr>
                <td colSpan="6" className="p-3 text-muted">
                  Loading…
                </td>
              </tr>
            )}
            {list.status === "ready" && list.items.length === 0 && (
              <tr>
                <td colSpan="6" className="p-3 text-muted">
                  No products found.
                </td>
              </tr>
            )}
            {list.status === "ready" &&
              list.items.map((product) => (
                <tr key={product.id} className="border-t border-line">
                  <td className="p-3 font-semibold">{product.name}</td>
                  <td className="p-3 text-muted">{product.sku}</td>
                  <td className="p-3">{product.category_name}</td>
                  <td className="p-3 text-right">
                    {product.quantity}
                    {product.is_low_stock && (
                      <span className="ml-2 rounded-full bg-orange-100 px-2 text-xs text-danger">
                        low
                      </span>
                    )}
                  </td>
                  <td className="p-3 text-right">{product.selling_price}</td>
                  <td className="p-3">
                    {canEdit && (
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setEditing(product)}
                          className="text-brand-dark"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(product)}
                          className="text-danger"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
        <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
      </div>
    </section>
  );
}
