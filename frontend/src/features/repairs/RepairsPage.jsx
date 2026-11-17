import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { STOCK_MANAGERS } from "../../auth/roles";
import Field from "../../components/Field";
import PageHeader from "../../components/PageHeader";
import { SkeletonCards } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { shortDate } from "../../format";
import { repairs } from "../../store";

const COLUMNS = [
  { status: "submitted", title: "Submitted", next: "in_progress", action: "Start repair" },
  { status: "in_progress", title: "In progress", next: "done", action: "Mark done" },
  { status: "done", title: "Done" },
];

function ReportForm({ onSaved, onCancel }) {
  const [assets, setAssets] = useState(null);
  const [values, setValues] = useState({ asset_id: "", description: "" });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/assets/?per_page=100")
      .then((data) => setAssets(data.results))
      .catch(() => setAssets([]));
  }, []);

  const update = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors({});
  };

  const submit = async (event) => {
    event.preventDefault();
    const found = {};
    if (!values.asset_id) found.asset_id = "Choose the asset.";
    if (values.description.trim().length < 5)
      found.description = "Describe the problem (5+ characters).";
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      const saved = await api("/api/repairs/", {
        method: "POST",
        body: { asset_id: Number(values.asset_id), description: values.description.trim() },
      });
      onSaved(saved);
    } catch (err) {
      setErrors({ form: err.message });
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-label="Report a fault"
      className="card flex flex-col gap-4 p-5"
    >
      <h2 className="text-lg font-bold">Report a fault</h2>
      {assets?.length === 0 ? (
        <p className="text-sm text-muted">
          You do not hold any assets, so there is nothing to report.
        </p>
      ) : (
        <Field label="Asset" name="asset_id" error={errors.asset_id}>
          {(id) => (
            <select
              id={id}
              name="asset_id"
              value={values.asset_id}
              onChange={update}
              className="input"
            >
              <option value="">Choose…</option>
              {assets?.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.asset_code} · {asset.name}
                </option>
              ))}
            </select>
          )}
        </Field>
      )}
      <Field label="What is wrong?" name="description" error={errors.description}>
        {(id) => (
          <textarea
            id={id}
            name="description"
            rows="3"
            value={values.description}
            onChange={update}
            className="input h-auto py-2"
          />
        )}
      </Field>
      {errors.form && (
        <p role="alert" className="text-sm text-danger">
          {errors.form}
        </p>
      )}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="btn-primary">
          Send report
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>
    </form>
  );
}

function RepairCard({ repair, column, onMove, busy }) {
  return (
    <li className="card flex flex-col gap-2 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold">{repair.asset_name}</span>
        <span className="text-xs text-muted">{repair.reference}</span>
      </div>
      <span className="text-sm">{repair.description}</span>
      <span className="text-xs text-muted">
        {repair.asset_code} · {repair.reporter_name} · {shortDate(repair.created_at)}
      </span>
      {column?.next && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onMove(repair, column.next)}
          className="btn-secondary self-start text-sm"
          aria-label={`${column.action}: ${repair.reference}`}
        >
          {column.action}
        </button>
      )}
    </li>
  );
}

export default function RepairsPage() {
  const dispatch = useDispatch();
  const { hasRole } = useAuth();
  const manager = hasRole(...STOCK_MANAGERS);
  const list = useSelector((state) => state.repairs);
  const [reporting, setReporting] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const reload = () => dispatch(repairs.fetchList({ per_page: 100 }));

  useEffect(() => {
    dispatch(repairs.fetchList({ per_page: 100 }));
  }, [dispatch]);

  // Optimistic: the card moves column at once; it moves back if the server refuses.
  const move = async (repair, status) => {
    const before = { items: list.items, count: list.count };
    dispatch(repairs.actions.patchItem({ id: repair.id, changes: { status } }));
    setBusyId(repair.id);
    setError("");
    try {
      await api(`/api/repairs/${repair.id}/status`, { method: "PUT", body: { status } });
      setNotice(`${repair.reference} is now ${status === "done" ? "done" : "in progress"}.`);
    } catch (err) {
      dispatch(repairs.actions.restoreItems(before));
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="flex flex-col gap-4">
      <PageHeader
        title="Repairs"
        subtitle={
          manager
            ? "Every fault reported on an asset. Move each one along as it is fixed."
            : "Report a fault on an asset you hold and follow its progress."
        }
      >
        {!reporting && (
          <button type="button" onClick={() => setReporting(true)} className="btn-primary">
            Report a fault
          </button>
        )}
      </PageHeader>

      {reporting && (
        <ReportForm
          onCancel={() => setReporting(false)}
          onSaved={(saved) => {
            setReporting(false);
            setNotice(`${saved.reference} sent. You will get a notification when it moves.`);
            reload();
          }}
        />
      )}
      {notice && (
        <p role="status" className="rounded-lg bg-mint p-3 text-sm">
          {notice}
        </p>
      )}
      {(error || list.error) && (
        <p role="alert" className="rounded-lg bg-danger-soft p-3 text-sm text-danger">
          {error || list.error}
        </p>
      )}

      {list.status === "loading" && list.items.length === 0 && <SkeletonCards count={3} />}

      {manager ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {COLUMNS.map((column) => {
            const cards = list.items.filter((repair) => repair.status === column.status);
            return (
              <section
                key={column.status}
                aria-label={column.title}
                className="flex flex-col gap-3 rounded-2xl bg-surface-2 p-3"
              >
                <h2 className="flex items-center justify-between px-1 text-sm font-semibold">
                  {column.title}
                  <span className="rounded-full bg-surface px-2 text-xs text-muted">
                    {cards.length}
                  </span>
                </h2>
                <ul className="flex flex-col gap-3">
                  {cards.map((repair) => (
                    <RepairCard
                      key={repair.id}
                      repair={repair}
                      column={column}
                      onMove={move}
                      busy={busyId === repair.id}
                    />
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {list.status === "ready" && list.items.length === 0 && (
            <li className="card p-4 text-muted">You have not reported any faults.</li>
          )}
          {list.items.map((repair) => (
            <li key={repair.id} className="card flex flex-col gap-1 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">
                  {repair.asset_name}{" "}
                  <span className="text-sm text-muted">· {repair.reference}</span>
                </span>
                <StatusBadge value={repair.status} />
              </div>
              <span className="text-sm">{repair.description}</span>
              <span className="text-xs text-muted">Reported {shortDate(repair.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}