import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { STOCK_MANAGERS } from "../../auth/roles";
import Field from "../../components/Field";
import Icon from "../../components/Icon";
import Modal from "../../components/Modal";
import PageHeader from "../../components/PageHeader";
import { SkeletonCards } from "../../components/Skeleton";
import StatusBadge from "../../components/StatusBadge";
import { Avatar, EmptyState } from "../../components/ui";
import { currencyCode, money, shortDate } from "../../format";
import { repairs } from "../../store";

// US-38: Submitted → In progress → Completed, or Submitted → Rejected (with a reason).
const COLUMNS = [
  { status: ["submitted"], title: "Submitted", key: "submitted" },
  { status: ["in_progress"], title: "In progress", key: "in_progress" },
  { status: ["done", "rejected"], title: "Closed", key: "closed" },
];
const URGENCIES = ["low", "normal", "high", "urgent"];

// Completing needs what was done (and an optional cost); rejecting needs why not.
function CloseDialog({ repair, outcome, onClose, onDone }) {
  const [resolution, setResolution] = useState("");
  const [cost, setCost] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const completing = outcome === "done";

  const submit = async () => {
    if (!resolution.trim()) {
      setError(completing ? "Say what was done." : "Say why it is rejected.");
      return;
    }
    if (cost && !(Number(cost) >= 0)) {
      setError("Enter a cost of 0 or more, or leave it empty.");
      return;
    }
    setBusy(true);
    try {
      const saved = await api(`/api/repairs/${repair.id}/status`, {
        method: "PUT",
        body: {
          status: outcome,
          resolution: resolution.trim(),
          cost: completing && cost ? Number(cost).toFixed(2) : null,
        },
      });
      onDone(saved);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <Modal
      size="sm"
      title={`${completing ? "Complete" : "Reject"} ${repair.reference}`}
      subtitle={`${repair.asset_name}: ${repair.description}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className={completing ? "btn-primary" : "btn-danger"}
            disabled={busy}
            onClick={submit}
          >
            {completing ? "Mark completed" : "Reject repair"}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label={completing ? "What was done" : "Why it is rejected"} name="resolution">
          {(id) => (
            <textarea
              id={id}
              rows={3}
              className="input h-auto py-2"
              value={resolution}
              onChange={(event) => {
                setResolution(event.target.value);
                setError("");
              }}
            />
          )}
        </Field>
        {completing && (
          <Field
            label={`Cost (${currencyCode()}, optional)`}
            name="cost"
            inputMode="decimal"
            value={cost}
            onChange={(event) => setCost(event.target.value)}
          />
        )}
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}

function ReportForm({ onSaved, onCancel }) {
  const [assets, setAssets] = useState(null);
  const [values, setValues] = useState({ asset_id: "", description: "", urgency: "normal" });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/assets/?mine=true&per_page=100")
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
        body: {
          asset_id: Number(values.asset_id),
          description: values.description.trim(),
          urgency: values.urgency,
        },
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
      <Field label="How urgent?" name="urgency">
        {(id) => (
          <select id={id} name="urgency" value={values.urgency} onChange={update} className="input">
            {URGENCIES.map((u) => (
              <option key={u} value={u}>
                {u[0].toUpperCase() + u.slice(1)}
              </option>
            ))}
          </select>
        )}
      </Field>
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

function RepairCard({ repair, onMove, onClose, busy }) {
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
      <div className="flex flex-wrap gap-1">
        <StatusBadge value={repair.urgency || "normal"} />
        {["done", "rejected"].includes(repair.status) && <StatusBadge value={repair.status} />}
      </div>
      <p className="text-sm text-ink-2">{repair.description}</p>
      {repair.resolution && (
        <p className="rounded-lg bg-surface-2 p-2 text-xs">
          {repair.status === "rejected" ? "Not repaired: " : "Done: "}
          {repair.resolution}
          {repair.cost && ` · ${money(repair.cost)}`}
        </p>
      )}
      <div className="flex items-center justify-between gap-2 border-t border-line pt-3">
        <span className="flex min-w-0 items-center gap-2 text-xs text-muted">
          <Avatar name={repair.reporter_name} size={22} />
          <span className="truncate">{repair.reporter_name}</span>
          <span>{shortDate(repair.created_at)}</span>
        </span>
        {repair.status === "submitted" && (
          <span className="flex shrink-0 gap-1">
            <button
              type="button"
              disabled={busy}
              onClick={() => onClose(repair, "rejected")}
              className="btn-ghost min-h-0 px-2 py-1.5 text-xs text-danger"
              aria-label={`Reject: ${repair.reference}`}
            >
              Reject
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => onMove(repair, "in_progress")}
              className="btn-secondary min-h-0 px-2.5 py-1.5 text-xs"
              aria-label={`Start repair: ${repair.reference}`}
            >
              Start repair
            </button>
          </span>
        )}
        {repair.status === "in_progress" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => onClose(repair, "done")}
            className="btn-secondary min-h-0 shrink-0 px-2.5 py-1.5 text-xs"
            aria-label={`Mark done: ${repair.reference}`}
          >
            Mark done
          </button>
        )}
      </div>
    </li>
  );
}

const COLUMN_DOTS = { submitted: "bg-saffron", in_progress: "bg-info", closed: "bg-brand" };

export default function RepairsPage() {
  const dispatch = useDispatch();
  const { hasRole } = useAuth();
  const manager = hasRole(...STOCK_MANAGERS);
  const list = useSelector((state) => state.repairs);
  const [reporting, setReporting] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [closing, setClosing] = useState(null); // {repair, outcome}

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
      setNotice(`${repair.reference} is now in progress. The asset is marked In repair.`);
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
            const cards = list.items.filter((repair) => column.status.includes(repair.status));
            return (
              <section
                key={column.key}
                aria-label={column.title}
                className="flex min-h-48 flex-col gap-3 rounded-2xl border border-line bg-surface-2 p-3"
              >
                <h2 className="flex items-center justify-between px-1 pt-1 text-sm font-semibold">
                  <span className="flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      className={`size-2 rounded-full ${COLUMN_DOTS[column.key]}`}
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
                      onMove={move}
                      onClose={(target, outcome) => setClosing({ repair: target, outcome })}
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
            const rejected = repair.status === "rejected";
            const stage = rejected
              ? 0
              : ["submitted", "in_progress", "done"].indexOf(repair.status);
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
                {repair.resolution && (
                  <p
                    className={`rounded-lg p-3 text-sm ${rejected ? "bg-danger-soft text-danger" : "bg-mint"}`}
                  >
                    {rejected ? "Not repaired: " : "What was done: "}
                    {repair.resolution}
                  </p>
                )}
                <ol className="grid grid-cols-3 gap-2 text-xs" aria-label="Progress">
                  {["Submitted", "In progress", rejected ? "Rejected" : "Completed"].map(
                    (step, i) => (
                      <li key={step} className="flex flex-col gap-1.5">
                        <span
                          className={`h-1.5 rounded-full ${i <= stage ? "bg-brand" : "bg-surface-2 ring-1 ring-line"}`}
                        />
                        <span className={i <= stage ? "font-medium" : "text-muted"}>{step}</span>
                      </li>
                    ),
                  )}
                </ol>
                <span className="text-xs text-muted">Reported {shortDate(repair.created_at)}</span>
              </li>
            );
          })}
        </ul>
      )}
      {closing && (
        <CloseDialog
          repair={closing.repair}
          outcome={closing.outcome}
          onClose={() => setClosing(null)}
          onDone={(saved) => {
            setClosing(null);
            setNotice(
              saved.status === "done"
                ? `${saved.reference} completed. The asset is back in use.`
                : `${saved.reference} rejected. The reporter has been told why.`,
            );
            reload();
          }}
        />
      )}
    </section>
  );
}
