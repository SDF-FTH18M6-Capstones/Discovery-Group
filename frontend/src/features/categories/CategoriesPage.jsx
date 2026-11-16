import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { useAuth } from "../../auth/AuthContext";
import { STOCK_MANAGERS } from "../../auth/roles";
import Field from "../../components/Field";
import Pagination from "../../components/Pagination";
import { categories } from "../../store";

export default function CategoriesPage() {
  const dispatch = useDispatch();
  const { hasRole } = useAuth();
  const canEdit = hasRole(...STOCK_MANAGERS);
  const list = useSelector((state) => state.categories);
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);
  const [name, setName] = useState("");
  const [fieldError, setFieldError] = useState("");

  useEffect(() => {
    dispatch(categories.fetchList({ page, per_page: 20 }));
  }, [dispatch, page]);

  const reload = () => dispatch(categories.fetchList({ page, per_page: 20 }));

  const open = (category) => {
    setEditing(category);
    setName(category.name || "");
    setFieldError("");
  };

  const handleSave = async (event) => {
    event.preventDefault();
    if (!name.trim()) {
      setFieldError("Name is required.");
      return;
    }
    const result = await dispatch(
      categories.saveItem({ id: editing.id, data: { name: name.trim() } }),
    );
    if (categories.saveItem.fulfilled.match(result)) {
      setEditing(null);
      reload();
    } else {
      setFieldError(result.payload.details?.name?.[0] || result.payload.message);
    }
  };

  // On failure (for example a category still used by products) the server's message
  // stays on screen; reload only after a successful delete.
  const handleDelete = async (category) => {
    const result = await dispatch(categories.deleteItem(category.id));
    if (categories.deleteItem.fulfilled.match(result)) reload();
  };

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Categories</h1>
          <p className="text-muted">Groups of products, such as Beverages or Packaging.</p>
        </div>
        {canEdit && (
          <button
            type="button"
            onClick={() => open({})}
            className="rounded-lg bg-brand px-4 py-2 font-semibold text-white"
          >
            Add category
          </button>
        )}
      </div>

      {editing && (
        <form
          onSubmit={handleSave}
          noValidate
          aria-label={editing.id ? "Rename category" : "Add category"}
          className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white p-5"
        >
          <div className="min-w-0 flex-1">
            <Field
              label="Category name"
              name="name"
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                setFieldError("");
              }}
              error={fieldError}
            />
          </div>
          <button type="submit" className="rounded-lg bg-brand px-4 py-2 font-semibold text-white">
            Save category
          </button>
          <button
            type="button"
            onClick={() => setEditing(null)}
            className="rounded-lg border border-line px-4 py-2"
          >
            Cancel
          </button>
        </form>
      )}

      {list.error && (
        <p role="alert" className="text-danger">
          {list.error}
        </p>
      )}

      <div className="relative overflow-x-auto rounded-xl border border-line bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-canvas text-muted">
            <tr>
              <th className="p-3">Name</th>
              <th className="p-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {list.status === "ready" && list.items.length === 0 && (
              <tr>
                <td colSpan="2" className="p-3 text-muted">
                  No categories yet.
                </td>
              </tr>
            )}
            {list.items.map((category) => (
              <tr key={category.id} className="border-t border-line">
                <td className="p-3 font-semibold">{category.name}</td>
                <td className="p-3">
                  {canEdit && (
                    <div className="flex gap-3">
                      <button
                        type="button"
                        onClick={() => open(category)}
                        className="text-brand-dark"
                      >
                        Rename
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(category)}
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
