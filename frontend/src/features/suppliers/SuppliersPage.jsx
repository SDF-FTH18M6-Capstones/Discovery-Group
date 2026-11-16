import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import Pagination from "../../components/Pagination";
import { suppliers } from "../../store";
import SupplierForm from "./SupplierForm";

export default function SuppliersPage() {
  const dispatch = useDispatch();
  const list = useSelector((state) => state.suppliers);
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);

  useEffect(() => {
    dispatch(suppliers.fetchList({ page, per_page: 10 }));
  }, [dispatch, page]);

  const reload = () => dispatch(suppliers.fetchList({ page, per_page: 10 }));

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Suppliers</h1>
        <button
          type="button"
          onClick={() => setEditing({})}
          className="rounded-lg bg-brand px-4 py-2 font-semibold text-white"
        >
          Add supplier
        </button>
      </div>

      {editing && (
        <SupplierForm
          key={editing.id || "new"}
          supplier={editing.id ? editing : null}
          onCancel={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
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
              <th className="p-3">Email</th>
              <th className="p-3">Phone</th>
              <th className="p-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {list.items.map((supplier) => (
              <tr key={supplier.id} className="border-t border-line">
                <td className="p-3 font-semibold">{supplier.name}</td>
                <td className="p-3">{supplier.email || "—"}</td>
                <td className="p-3">{supplier.phone || "—"}</td>
                <td className="flex gap-2 p-3">
                  <button
                    type="button"
                    onClick={() => setEditing(supplier)}
                    className="text-brand-dark"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      const result = await dispatch(suppliers.deleteItem(supplier.id));
                      if (suppliers.deleteItem.fulfilled.match(result)) reload();
                    }}
                    className="text-danger"
                  >
                    Delete
                  </button>
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