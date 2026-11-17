import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { useAuth } from "../../auth/AuthContext";
import { STOCK_MANAGERS } from "../../auth/roles";
import Pagination from "../../components/Pagination";
import StatusBadge from "../../components/StatusBadge";
import { assets } from "../../store";
import AssetForm from "./AssetForm";

const FILTERS = [
  { value: "", label: "All" },
  { value: "available", label: "Available" },
  { value: "assigned", label: "Assigned" },
  { value: "in_repair", label: "In repair" },
];

export default function AssetsPage() {
  const dispatch = useDispatch();
  const { hasRole } = useAuth();
  const manager = hasRole(...STOCK_MANAGERS);
  const list = useSelector((state) => state.assets);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);

  const load = () => dispatch(assets.fetchList({ search, status, page, per_page: 10 }));

  useEffect(() => {
    dispatch(assets.fetchList({ search, status, page, per_page: 10 }));
  }, [dispatch, search, status, page]);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">{manager ? "Assets" : "My assets"}</h1>
          <p className="text-muted">
            {manager
              ? "Equipment the business owns, and who holds it."
              : "Equipment the business has given you."}
          </p>
        </div>
        {manager && (
          <button type="button" onClick={() => setEditing({})} className="btn-primary">
            Add asset
          </button>
        )}
      </div>

      {editing && (
        <AssetForm
          key={editing.id || "new"}
          asset={editing.id ? editing : null}
          onCancel={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}

      {list.error && (
        <p role="alert" className="text-danger">
          {list.error}
        </p>
      )}

      {manager && (
        <div className="flex flex-wrap items-center gap-3">
          <label htmlFor="asset-search" className="sr-only">
            Search assets
          </label>
          <input
            id="asset-search"
            type="search"
            placeholder="Search by name or code"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            className="input w-full max-w-sm"
          />
          <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
            {FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                aria-pressed={status === filter.value}
                onClick={() => {
                  setStatus(filter.value);
                  setPage(1);
                }}
                className="chip"
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="card relative overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="table-head">
            <tr>
              <th className="p-3">Code</th>
              <th className="p-3">Asset</th>
              <th className="p-3">Status</th>
              {manager && <th className="p-3">Held by</th>}
              {manager && (
                <th className="p-3">
                  <span className="sr-only">Actions</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {list.status === "ready" && list.items.length === 0 && (
              <tr>
                <td colSpan={manager ? 5 : 3} className="p-3 text-muted">
                  {manager ? "No assets found." : "No assets are assigned to you."}
                </td>
              </tr>
            )}
            {list.items.map((asset) => (
              <tr key={asset.id} className="border-t border-line">
                <td className="p-3 font-mono text-xs">{asset.asset_code}</td>
                <td className="p-3 font-semibold">{asset.name}</td>
                <td className="p-3">
                  <StatusBadge value={asset.status} />
                </td>
                {manager && <td className="p-3">{asset.holder_name || "—"}</td>}
                {manager && (
                  <td className="p-3">
                    <div className="flex gap-3">
                      <button
                        type="button"
                        onClick={() => setEditing(asset)}
                        className="text-brand-dark"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={async () => {
                          const result = await dispatch(assets.deleteItem(asset.id));
                          if (assets.deleteItem.fulfilled.match(result)) load();
                        }}
                        className="text-danger"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
      </div>
    </section>
  );
}
