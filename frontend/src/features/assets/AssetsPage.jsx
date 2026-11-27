import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Link, useSearchParams } from "react-router-dom";

import { api, mediaUrl } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { ROLE_NAMES, STOCK_VIEWERS } from "../../auth/roles";
import Barcode from "../../components/Barcode";
import Field from "../../components/Field";
import Icon from "../../components/Icon";
import Modal from "../../components/Modal";
import Pagination from "../../components/Pagination";
import StatusBadge from "../../components/StatusBadge";
import Timeline from "../../components/Timeline";
import { EmptyState } from "../../components/ui";
import { isoToday, money, shortDate } from "../../format";
import { assets } from "../../store";
import AssetForm, { CONDITIONS, conditionLabel } from "./AssetForm";

const FILTERS = [
  { value: "", label: "All" },
  { value: "available", label: "Available" },
  { value: "assigned", label: "Assigned" },
  { value: "overdue", label: "Overdue" },
  { value: "in_repair", label: "In repair" },
  { value: "retired", label: "Retired" },
];

function ConditionSelect({ id, value, onChange }) {
  return (
    <select id={id} value={value} onChange={onChange} className="input px-2">
      {CONDITIONS.map((condition) => (
        <option key={condition} value={condition}>
          {conditionLabel(condition)}
        </option>
      ))}
    </select>
  );
}

function AssignDialog({ asset, onClose, onDone }) {
  const [people, setPeople] = useState([]);
  const [values, setValues] = useState({
    user_id: "",
    expected_return: "",
    condition: asset.condition || "good",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/users/choices")
      .then(setPeople)
      .catch(() => {});
  }, []);

  const submit = async () => {
    if (!values.user_id) {
      setError("Choose who receives it.");
      return;
    }
    setBusy(true);
    try {
      const saved = await api(`/api/assets/${asset.id}/assign`, {
        method: "POST",
        body: {
          user_id: Number(values.user_id),
          condition: values.condition,
          expected_return: values.expected_return || null,
        },
      });
      onDone(`${saved.name} is now with ${saved.holder_name}.`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  const set = (name) => (event) => {
    setValues((current) => ({ ...current, [name]: event.target.value }));
    setError("");
  };

  return (
    <Modal
      size="sm"
      title={`Assign ${asset.asset_code}`}
      subtitle={asset.name}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={submit}>
            Assign
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Give it to" name="assign-user">
          {(id) => (
            <select id={id} value={values.user_id} onChange={set("user_id")} className="input">
              <option value="">Choose…</option>
              {people.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.full_name} · {ROLE_NAMES[person.role] || person.role}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Condition at hand-over" name="assign-condition">
          {(id) => <ConditionSelect id={id} value={values.condition} onChange={set("condition")} />}
        </Field>
        <Field
          label="Expected back (optional)"
          name="assign-return"
          type="date"
          min={isoToday()}
          value={values.expected_return}
          onChange={set("expected_return")}
        />
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}

function ReturnDialog({ asset, onClose, onDone }) {
  const [condition, setCondition] = useState(asset.condition || "good");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const saved = await api(`/api/assets/${asset.id}/return`, {
        method: "POST",
        body: { condition, notes: notes.trim() || null },
      });
      onDone(`${saved.name} returned (${conditionLabel(condition)}) and available again.`);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <Modal
      size="sm"
      title={`Return ${asset.asset_code}`}
      subtitle={`${asset.name}, held by ${asset.holder_name}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={submit}>
            Record return
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Condition now" name="return-condition">
          {(id) => (
            <ConditionSelect
              id={id}
              value={condition}
              onChange={(event) => setCondition(event.target.value)}
            />
          )}
        </Field>
        <Field
          label="Notes (optional)"
          name="return-notes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Scratched lid, charger missing…"
        />
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}

function AssetDetails({ asset, manager, onClose }) {
  const [history, setHistory] = useState(null);

  useEffect(() => {
    api(`/api/assets/${asset.id}/assignments?per_page=20`)
      .then((data) => setHistory(data.results))
      .catch(() => setHistory([]));
  }, [asset.id]);

  const details = [
    ["Category", asset.category_name || "—"],
    ["Serial number", asset.serial_number || "—"],
    ["Condition", conditionLabel(asset.condition)],
    ["Bought", asset.purchase_date ? shortDate(asset.purchase_date) : "—"],
    ["Cost", asset.purchase_cost ? money(asset.purchase_cost) : "—"],
    ["Held by", asset.holder_name || "Nobody"],
  ];

  return (
    <Modal
      size="lg"
      title={asset.name}
      subtitle={
        <span className="flex items-center gap-2">
          <span className="code">{asset.asset_code}</span>
          <StatusBadge value={asset.status} />
        </span>
      }
      onClose={onClose}
    >
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-start gap-6">
          <div className="print-area flex flex-col items-center gap-2 rounded-xl border border-line p-4">
            <span className="text-xs font-semibold">{asset.name}</span>
            <Barcode value={asset.barcode} />
            <span className="code text-xs">{asset.asset_code}</span>
          </div>
          {asset.image_url && (
            <img
              src={mediaUrl(asset.image_url)}
              alt={asset.name}
              className="size-32 rounded-xl border border-line object-cover"
            />
          )}
          <dl className="grid flex-1 grid-cols-2 gap-x-4 gap-y-2 text-sm">
            {details.map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs text-muted">{label}</dt>
                <dd className="font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
        <button type="button" onClick={() => window.print()} className="btn-secondary self-start">
          <Icon name="printer" size={16} /> Print label
        </button>

        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold">Who has held it</h3>
          {history === null ? (
            <p className="text-sm text-muted">Loading…</p>
          ) : history.length === 0 ? (
            <p className="text-sm text-muted">Never assigned.</p>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-line">
              <table className="w-full text-left text-sm">
                <thead className="table-head">
                  <tr>
                    <th className="px-3 py-2">Holder</th>
                    <th className="px-3 py-2">From</th>
                    <th className="px-3 py-2">Due</th>
                    <th className="px-3 py-2">Returned</th>
                    <th className="px-3 py-2">Condition</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((row) => (
                    <tr key={row.id} className="border-t border-line">
                      <td className="px-3 py-2 font-medium">{row.user_name}</td>
                      <td className="px-3 py-2">{shortDate(row.assigned_at)}</td>
                      <td className={`px-3 py-2 ${row.is_overdue ? "text-danger" : ""}`}>
                        {row.expected_return ? shortDate(row.expected_return) : "—"}
                        {row.is_overdue && " (overdue)"}
                      </td>
                      <td className="px-3 py-2">
                        {row.returned_at
                          ? `${shortDate(row.returned_at)} to ${row.received_by_name}`
                          : "Still out"}
                      </td>
                      <td className="px-3 py-2">
                        {conditionLabel(row.condition_out)}
                        {row.condition_in && ` → ${conditionLabel(row.condition_in)}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {manager && (
          <section className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold">Trace timeline</h3>
            <div className="overflow-hidden rounded-xl border border-line">
              <Timeline url={`/api/assets/${asset.id}/timeline`} />
            </div>
          </section>
        )}
      </div>
    </Modal>
  );
}

function CategoriesDialog({ categories, onClose, onChanged }) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  const add = async (event) => {
    event.preventDefault();
    if (!name.trim()) return;
    try {
      await api("/api/asset-categories/", { method: "POST", body: { name: name.trim() } });
      setName("");
      setError("");
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (category) => {
    try {
      await api(`/api/asset-categories/${category.id}`, { method: "DELETE" });
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Modal size="sm" title="Asset categories" onClose={onClose}>
      <form onSubmit={add} className="flex gap-2">
        <label htmlFor="new-asset-category" className="sr-only">
          New category
        </label>
        <input
          id="new-asset-category"
          className="input flex-1"
          placeholder="e.g. Computers"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <button type="submit" className="btn-primary">
          Add
        </button>
      </form>
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
      <ul className="mt-4 flex flex-col divide-y divide-line">
        {categories.map((category) => (
          <li key={category.id} className="flex items-center justify-between py-2">
            {category.name}
            <button
              type="button"
              className="btn-ghost text-danger"
              onClick={() => remove(category)}
              aria-label={`Delete ${category.name}`}
            >
              Delete
            </button>
          </li>
        ))}
        {categories.length === 0 && <li className="py-2 text-sm text-muted">None yet.</li>}
      </ul>
    </Modal>
  );
}

export default function AssetsPage() {
  const dispatch = useDispatch();
  const { hasRole, canDo } = useAuth();
  const seesAll = hasRole(...STOCK_VIEWERS);
  const manager = canDo("inventory");
  const list = useSelector((state) => state.assets);
  const [params] = useSearchParams();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState(params.get("overdue") ? "overdue" : "");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);
  const [dialog, setDialog] = useState(null);
  const [categories, setCategories] = useState([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const query = {
    search,
    status: status === "overdue" ? "" : status,
    overdue: status === "overdue" ? "true" : "",
    page,
    per_page: 10,
  };
  const load = () => dispatch(assets.fetchList(query));
  const loadCategories = () =>
    api("/api/asset-categories/?per_page=100")
      .then((data) => setCategories(data.results))
      .catch(() => {});

  useEffect(() => {
    if (seesAll) loadCategories();
  }, [seesAll]);

  useEffect(() => {
    dispatch(
      assets.fetchList({
        search,
        status: status === "overdue" ? "" : status,
        overdue: status === "overdue" ? "true" : "",
        page,
        per_page: 10,
      }),
    );
  }, [dispatch, search, status, page]);

  const done = (message) => {
    setDialog(null);
    setError("");
    setNotice(message);
    load();
  };

  const retire = async (asset) => {
    if (!window.confirm(`Retire ${asset.name}? It stays on record but cannot be assigned.`)) return;
    try {
      await api(`/api/assets/${asset.id}/retire`, { method: "POST" });
      done(`${asset.name} retired.`);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="flex flex-col gap-1.5">
          <h1 className="page-title">{seesAll ? "Assets" : "Assets with me"}</h1>
          <p className="text-muted">
            {seesAll
              ? "Equipment the business owns, its barcode, and who holds it."
              : "Equipment the business has given you. Report a fault under Repairs."}
          </p>
        </div>
        {manager && (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setDialog({ kind: "categories" })}
              className="btn-secondary"
            >
              <Icon name="tag" size={16} /> Categories
            </button>
            <button type="button" onClick={() => setEditing({})} className="btn-primary">
              <Icon name="plus" size={16} /> Add asset
            </button>
          </div>
        )}
      </div>

      {editing && (
        <AssetForm
          key={editing.id || "new"}
          asset={editing.id ? editing : null}
          categories={categories}
          onCancel={() => setEditing(null)}
          onSaved={(saved) => {
            setEditing(null);
            setNotice(`${saved.asset_code} ${saved.name} saved.`);
            load();
          }}
        />
      )}

      {notice && (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {notice}
        </p>
      )}
      {(error || list.error) && (
        <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {error || list.error}
        </p>
      )}

      {seesAll && (
        <div className="flex flex-wrap items-center gap-3">
          <label htmlFor="asset-search" className="sr-only">
            Search assets
          </label>
          <input
            id="asset-search"
            type="search"
            placeholder="Name, code, serial or scan a barcode"
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

      <div className="panel relative overflow-x-auto">
        <table className="data-table w-full text-left text-sm">
          <thead className="table-head">
            <tr>
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3">Asset</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">{seesAll ? "Held by" : "Since"}</th>
              <th className="px-4 py-3">{seesAll ? "Due back" : "Condition"}</th>
              <th className="px-4 py-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {list.items.map((asset) => {
              const current = asset.current_assignment;
              return (
                <tr key={asset.id} className="border-t border-line">
                  <td className="px-4 py-3">
                    <span className="code rounded-md bg-surface-2 px-1.5 py-0.5">
                      {asset.asset_code}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="block font-semibold">{asset.name}</span>
                    <span className="text-xs text-muted">
                      {[asset.category_name, asset.serial_number].filter(Boolean).join(" · ")}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex flex-wrap gap-1">
                      <StatusBadge value={asset.status} />
                      {current?.is_overdue && <StatusBadge value="overdue" />}
                      {asset.open_repair && asset.status !== "in_repair" && (
                        <Link to="/repairs" className="text-xs text-saffron-ink underline">
                          {asset.open_repair.reference}
                        </Link>
                      )}
                    </span>
                  </td>
                  {seesAll ? (
                    <>
                      <td className="px-4 py-3">{asset.holder_name || "—"}</td>
                      <td className={`px-4 py-3 ${current?.is_overdue ? "text-danger" : ""}`}>
                        {current?.expected_return ? shortDate(current.expected_return) : "—"}
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-4 py-3">
                        {current ? shortDate(current.assigned_at) : "—"}
                      </td>
                      <td className="px-4 py-3">{conditionLabel(asset.condition)}</td>
                    </>
                  )}
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap justify-end gap-1">
                      <button
                        type="button"
                        onClick={() => setDialog({ kind: "view", asset })}
                        className="btn-ghost min-h-0 px-2.5 py-1.5"
                        aria-label={`View ${asset.name}`}
                      >
                        View
                      </button>
                      {manager && asset.status === "available" && (
                        <button
                          type="button"
                          onClick={() => setDialog({ kind: "assign", asset })}
                          className="btn-secondary min-h-0 px-2.5 py-1.5"
                        >
                          Assign
                        </button>
                      )}
                      {manager && asset.status === "assigned" && (
                        <button
                          type="button"
                          onClick={() => setDialog({ kind: "return", asset })}
                          className="btn-secondary min-h-0 px-2.5 py-1.5"
                        >
                          Return
                        </button>
                      )}
                      {manager && (
                        <button
                          type="button"
                          onClick={() => setEditing(asset)}
                          className="btn-ghost min-h-0 px-2.5 py-1.5"
                        >
                          Edit
                        </button>
                      )}
                      {manager && asset.status === "available" && (
                        <button
                          type="button"
                          onClick={() => retire(asset)}
                          className="btn-ghost min-h-0 px-2.5 py-1.5 hover:text-danger"
                        >
                          Retire
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {list.status === "ready" && list.items.length === 0 && (
          <EmptyState icon="laptop" title={seesAll ? "No assets found" : "Nothing assigned to you"}>
            {seesAll
              ? "Register equipment with Add asset; each gets a code and a barcode."
              : "When equipment is handed to you, it shows up here."}
          </EmptyState>
        )}
        <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
      </div>

      {dialog?.kind === "view" && (
        <AssetDetails asset={dialog.asset} manager={seesAll} onClose={() => setDialog(null)} />
      )}
      {dialog?.kind === "assign" && (
        <AssignDialog asset={dialog.asset} onClose={() => setDialog(null)} onDone={done} />
      )}
      {dialog?.kind === "return" && (
        <ReturnDialog asset={dialog.asset} onClose={() => setDialog(null)} onDone={done} />
      )}
      {dialog?.kind === "categories" && (
        <CategoriesDialog
          categories={categories}
          onClose={() => setDialog(null)}
          onChanged={loadCategories}
        />
      )}
    </section>
  );
}
