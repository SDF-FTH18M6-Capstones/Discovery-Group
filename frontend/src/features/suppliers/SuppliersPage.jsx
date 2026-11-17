import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
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
    <section className="flex flex-col gap-6">
      <PageHeader title="Suppliers" subtitle="Who the shop buys from, and how to reach them.">
        <button type="button" onClick={() => setEditing({})} className="btn-primary">
          <Icon name="plus" size={16} />
          Add supplier
        </button>
      </PageHeader>

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

      <div className="panel relative overflow-x-auto">
        <table className="data-table w-full text-left text-sm">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Phone</th>
              <th className="px-4 py-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {list.items.map((supplier) => (
              <tr key={supplier.id} className="border-t border-line">
                <td className="px-4 py-3 font-semibold">
                  <span className="mr-3 inline-grid size-8 place-items-center rounded-lg bg-surface-2 align-middle text-brand-dark">
                    <Icon name="building" size={16} />
                  </span>
                  {supplier.name}
                </td>
                <td className="px-4 py-3">{supplier.email || "—"}</td>
                <td className="px-4 py-3">{supplier.phone || "—"}</td>
                <td className="flex justify-end gap-2 px-4 py-3">
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