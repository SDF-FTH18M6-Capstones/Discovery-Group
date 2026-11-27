import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { useAuth } from "../../auth/AuthContext";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { suppliers } from "../../store";
import SupplierForm from "./SupplierForm";

export default function SuppliersPage() {
  const dispatch = useDispatch();
  const list = useSelector((state) => state.suppliers);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState(null);
  const { canDo } = useAuth();
  const canEdit = canDo("procurement");

  useEffect(() => {
    dispatch(suppliers.fetchList({ page, per_page: 10, search }));
  }, [dispatch, page, search]);

  const reload = () => dispatch(suppliers.fetchList({ page, per_page: 10, search }));

  return (
    <section className="flex flex-col gap-6">
      <PageHeader title="Suppliers" subtitle="Who the shop buys from, and how to reach them.">
        {canEdit && (
          <button type="button" onClick={() => setEditing({})} className="btn-primary">
            <Icon name="plus" size={16} />
            Add supplier
          </button>
        )}
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

      <div>
        <label htmlFor="supplier-search" className="sr-only">
          Search suppliers
        </label>
        <input
          id="supplier-search"
          type="search"
          placeholder="Name, email or code (SUP-001)"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          className="input w-full max-w-sm"
        />
      </div>

      <div className="panel relative overflow-x-auto">
        <table className="data-table w-full text-left text-sm">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Phone</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {list.items.map((supplier) => (
              <tr
                key={supplier.id}
                className={`border-t border-line ${supplier.is_active === false ? "opacity-70" : ""}`}
              >
                <td className="code px-4 py-3 text-muted">{supplier.code}</td>
                <td className="px-4 py-3 font-semibold">
                  <span className="mr-3 inline-grid size-8 place-items-center rounded-lg bg-surface-2 align-middle text-brand-dark">
                    <Icon name="building" size={16} />
                  </span>
                  {supplier.name}
                  {supplier.trusted && (
                    <span className="ml-2 rounded-full bg-mint px-2 py-0.5 text-xs font-semibold text-brand-dark">
                      Trusted
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">{supplier.email || "—"}</td>
                <td className="px-4 py-3">{supplier.phone || "—"}</td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${supplier.is_active === false ? "bg-surface-2 text-muted" : "bg-mint text-brand-dark"}`}
                  >
                    {supplier.is_active === false ? "Inactive" : "Active"}
                  </span>
                </td>
                <td className="flex justify-end gap-2 px-4 py-3">
                  {canEdit && (
                    <>
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
                    </>
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
