import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { STOCK_MANAGERS } from "../../auth/roles";
import Field from "../../components/Field";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import { SkeletonCards } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { Avatar, EmptyState } from "../../components/ui";
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
      className="card flex flex-col gap-5 p-6"
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
    <li className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4 shadow-[var(--sp-shadow)]">
      <div className="flex items-start justify-between gap-2">
        <span className="flex flex-col">
          <span className="font-semibold">{repair.asset_name}</span>
          <span className="code text-muted">{repair.asset_code}</span>
        </span>
        <span className="code rounded-md bg-surface-2 px-1.5 py-0.5 text-muted">
          {repair.reference}
        </span>
      </div>
      <p className="text-sm text-ink-2">{repair.description}</p>
      <div className="flex items-center justify-between gap-2 border-t border-line pt-3">
        <span className="flex min-w-0 items-center gap-2 text-xs text-muted">
          <Avatar name={repair.reporter_name} size={22} />
          <span className="truncate">{repair.reporter_name}</span>
          <span>{shortDate(repair.created_at)}</span>
        </span>
        {column?.next && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onMove(repair, column.next)}
            className="btn-secondary min-h-0 shrink-0 px-2.5 py-1.5 text-xs"
            aria-label={`${column.action}: ${repair.reference}`}
          >
            {column.action}
          </button>
        )}
      </div>
    </li>
  );
}

const COLUMN_DOTS = { submitted: "bg-saffron", in_progress: "bg-info", done: "bg-brand" };

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
    <section className="flex flex-col gap-6">
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
            <Icon name="wrench" size={16} />
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
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {notice}
        </p>
      )}
      {(error || list.error) && (
        <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm text-danger">
          {error || list.error}
        </p>
      )}

      {list.status === "loading" && list.items.length === 0 && <SkeletonCards count={3} />}

      {manager ? (
        <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-3">
          {COLUMNS.map((column) => {
            const cards = list.items.filter((repair) => repair.status === column.status);
            return (
              <section
                key={column.status}
                aria-label={column.title}
                className="flex min-h-48 flex-col gap-3 rounded-2xl border border-line bg-surface-2 p-3"
              >
                <h2 className="flex items-center justify-between px-1 pt-1 text-sm font-semibold">
                  <span className="flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      className={`size-2 rounded-full ${COLUMN_DOTS[column.status]}`}
                    />
                    {column.title}
                  </span>
                  <span className="figure rounded-full bg-surface px-2.5 py-0.5 text-xs text-muted ring-1 ring-line">
                    {cards.length}
                  </span>
                </h2>
                {cards.length === 0 && (
                  <p className="rounded-xl border border-dashed border-line-strong p-4 text-center text-xs text-muted">
                    Nothing here
                  </p>
                )}
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
            <li className="panel">
              <EmptyState icon="wrench" title="No faults reported">
                If something you hold stops working, report it here and follow the repair.
              </EmptyState>
            </li>
          )}
          {list.items.map((repair) => {
            const stage = ["submitted", "in_progress", "done"].indexOf(repair.status);
            return (
              <li key={repair.id} className="panel flex flex-col gap-4 p-5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <span className="flex flex-col">
                    <span className="font-display text-lg font-semibold">{repair.asset_name}</span>
                    <span className="code text-muted">{repair.reference}</span>
                  </span>
                  <StatusBadge value={repair.status} />
                </div>
                <p className="text-sm text-ink-2">{repair.description}</p>
                <ol className="grid grid-cols-3 gap-2 text-xs" aria-label="Progress">
                  {["Submitted", "In progress", "Done"].map((step, i) => (
                    <li key={step} className="flex flex-col gap-1.5">
                      <span
                        className={`h-1.5 rounded-full ${i <= stage ? "bg-brand" : "bg-surface-2 ring-1 ring-line"}`}
                      />
                      <span className={i <= stage ? "font-medium" : "text-muted"}>{step}</span>
                    </li>
                  ))}
                </ol>
                <span className="text-xs text-muted">Reported {shortDate(repair.created_at)}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}