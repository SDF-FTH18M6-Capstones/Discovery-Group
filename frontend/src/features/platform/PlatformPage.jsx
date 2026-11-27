import { useEffect, useState } from "react";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import Field from "../../components/Field";
import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { longDate, shortDate } from "../../format";

const STATUS = {
  trial: ["Trial", "bg-surface-2 text-ink-2"],
  active: ["Active", "bg-mint text-brand-dark"],
  grace: ["Payment due", "bg-warn-soft text-warn"],
  expired: ["Ended", "bg-danger-soft text-danger"],
  suspended: ["Suspended", "bg-danger-soft text-danger"],
};

const PAYBILL = {
  off: "Not connected: businesses cannot pay online yet.",
  simulate: "Test mode: payments are simulated and no money moves.",
  sandbox: "Safaricom sandbox: real prompts, test money.",
  live: "Live: payments go to StockPilot's Paybill.",
};

const kes = (amount) => `KES ${Number(amount).toLocaleString("en-KE")}`;

function Status({ value }) {
  const [label, tone] = STATUS[value];
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>{label}</span>;
}

function Tile({ label, value, hint }) {
  return (
    <div className="card flex flex-col gap-1 p-5">
      <span className="text-sm text-muted">{label}</span>
      <span className="figure text-2xl">{value}</span>
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </div>
  );
}

function PriceForm({ price, onSaved }) {
  const [value, setValue] = useState(String(price));
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    try {
      onSaved(await api("/api/platform/price", { method: "PUT", body: { price: Number(value) } }));
      setSaved(true);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="card flex flex-col gap-3 p-5">
      <Field
        label="Monthly price (KES)"
        name="price"
        inputMode="numeric"
        value={value}
        onChange={(event) => {
          setValue(event.target.value);
          setSaved(false);
        }}
        error={error}
      />
      <button type="submit" className="btn-secondary self-start">
        Save price
      </button>
      {saved && (
        <p role="status" className="text-sm text-brand-dark">
          New payments use the new price.
        </p>
      )}
    </form>
  );
}

function Actions({ business, onChanged }) {
  const [mode, setMode] = useState(null);
  const [months, setMonths] = useState("1");
  const [text, setText] = useState("");
  const [error, setError] = useState("");

  const run = async (path, body) => {
    setError("");
    try {
      onChanged(
        await api(`/api/platform/businesses/${business.id}/${path}`, { method: "POST", body }),
      );
      setMode(null);
      setText("");
    } catch (err) {
      setError(err.message);
    }
  };

  if (mode === "extend") {
    return (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          run("extend", { months: Number(months), note: text });
        }}
        className="flex flex-wrap items-end gap-2"
      >
        <label className="flex flex-col gap-1 text-xs">
          Months
          <select
            value={months}
            onChange={(event) => setMonths(event.target.value)}
            className="input w-20 px-2"
          >
            {[1, 2, 3, 6, 12].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          Why
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Paid in cash"
            className="input w-44"
          />
        </label>
        <button type="submit" className="btn-primary">
          Add months
        </button>
        <button type="button" onClick={() => setMode(null)} className="btn-ghost">
          Cancel
        </button>
        {error && <span className="w-full text-xs text-danger">{error}</span>}
      </form>
    );
  }

  if (mode === "suspend") {
    return (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          run("suspend", { reason: text });
        }}
        className="flex flex-wrap items-end gap-2"
      >
        <label className="flex flex-col gap-1 text-xs">
          Reason
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="input w-52"
          />
        </label>
        <button type="submit" className="btn-danger">
          Suspend
        </button>
        <button type="button" onClick={() => setMode(null)} className="btn-ghost">
          Cancel
        </button>
        {error && <span className="w-full text-xs text-danger">{error}</span>}
      </form>
    );
  }

  return (
    <span className="flex flex-wrap justify-end gap-2">
      <button type="button" onClick={() => setMode("extend")} className="btn-ghost">
        Add months
      </button>
      {business.is_active ? (
        <button type="button" onClick={() => setMode("suspend")} className="btn-ghost text-danger">
          Suspend
        </button>
      ) : (
        <button type="button" onClick={() => run("reactivate")} className="btn-ghost">
          Reactivate
        </button>
      )}
      {error && <span className="w-full text-right text-xs text-danger">{error}</span>}
    </span>
  );
}

function Businesses({ onChanged }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [list, setList] = useState(null);

  const load = () => {
    const query = new URLSearchParams({ page, per_page: 20 });
    if (search) query.set("search", search);
    if (status) query.set("status", status);
    return api(`/api/platform/businesses?${query}`).then(setList);
  };

  useEffect(() => {
    const timer = setTimeout(load, 200);
    return () => clearTimeout(timer);
  }, [search, status, page]);

  const changed = () => {
    load();
    onChanged();
  };

  return (
    <section aria-labelledby="businesses-title" className="panel overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
        <h2 id="businesses-title" className="mr-auto text-lg font-bold">
          Businesses
        </h2>
        <label htmlFor="business-search" className="sr-only">
          Search businesses
        </label>
        <input
          id="business-search"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Search by name"
          className="input w-52"
        />
        <label htmlFor="business-status" className="sr-only">
          Status
        </label>
        <select
          id="business-status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
          className="input w-auto px-2"
        >
          <option value="">Every status</option>
          {Object.entries(STATUS).map(([value, [label]]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted uppercase">
            <tr>
              <th className="px-4 py-3">Business</th>
              <th className="px-4 py-3">Owner</th>
              <th className="px-4 py-3">Staff</th>
              <th className="px-4 py-3">Last sale</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Paid until</th>
              <th className="px-4 py-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {list?.results.map((business) => (
              <tr key={business.id} className="border-t border-line">
                <td className="px-4 py-3">
                  <span className="font-semibold">{business.name}</span>
                  <span className="block text-xs text-muted">
                    Joined {longDate(business.created_at)}
                  </span>
                </td>
                <td className="px-4 py-3">{business.owner_email || "—"}</td>
                <td className="px-4 py-3">{business.staff}</td>
                <td className="px-4 py-3">
                  {business.last_sale_at ? shortDate(business.last_sale_at) : "—"}
                </td>
                <td className="px-4 py-3">
                  <Status value={business.status} />
                </td>
                <td className="px-4 py-3">{longDate(business.ends_on)}</td>
                <td className="px-4 py-3">
                  <Actions business={business} onChanged={changed} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {list && list.count === 0 && (
          <p className="p-6 text-center text-muted">No businesses match.</p>
        )}
      </div>
      {list && (
        <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
      )}
    </section>
  );
}

function Payments({ version }) {
  const [page, setPage] = useState(1);
  const [list, setList] = useState(null);

  useEffect(() => {
    api(`/api/platform/payments?page=${page}&per_page=10`).then(setList);
  }, [page, version]);

  return (
    <section aria-labelledby="payments-title" className="panel overflow-hidden">
      <h2 id="payments-title" className="border-b border-line p-4 text-lg font-bold">
        Subscription payments
      </h2>
      {list?.count === 0 ? (
        <p className="p-6 text-center text-muted">No payments yet.</p>
      ) : (
        <ul className="divide-y divide-line text-sm">
          {list?.results.map((payment) => (
            <li key={payment.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <span className="font-semibold">{payment.business_name}</span>
              <span className="text-muted">
                {payment.months} month{payment.months === 1 ? "" : "s"}
              </span>
              <span className="code">{payment.receipt_number}</span>
              {payment.simulated && <span className="text-xs text-muted">test</span>}
              <span className="ml-auto text-muted">{shortDate(payment.completed_at)}</span>
              <span className="figure">{kes(payment.amount)}</span>
            </li>
          ))}
        </ul>
      )}
      {list && (
        <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
      )}
    </section>
  );
}

export default function PlatformPage() {
  const { user } = useAuth();
  const [overview, setOverview] = useState(null);
  const [version, setVersion] = useState(0);

  const refresh = () => {
    api("/api/platform/overview").then(setOverview);
    setVersion((current) => current + 1);
  };

  useEffect(() => {
    if (user?.platform_owner) api("/api/platform/overview").then(setOverview);
  }, [user]);

  if (!user?.platform_owner) {
    return (
      <section className="panel p-8 text-center">
        <h1 className="page-title">Page not found</h1>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-6">
      <PageHeader
        title="StockPilot platform"
        subtitle="Every business on StockPilot, their subscriptions and what they have paid."
      />
      {overview && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Tile
              label="Businesses"
              value={overview.businesses}
              hint={`${overview.by_status.active} paying, ${overview.by_status.trial} on trial`}
            />
            <Tile
              label="Needs attention"
              value={overview.by_status.grace + overview.by_status.expired}
              hint={`${overview.by_status.grace} payment due, ${overview.by_status.expired} ended, ${overview.by_status.suspended} suspended`}
            />
            <Tile label="Received this month" value={kes(overview.revenue_this_month)} />
            <Tile label="Received in total" value={kes(overview.revenue_total)} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="card flex flex-col gap-2 p-5 text-sm">
              <span className="text-muted">StockPilot's Paybill</span>
              <span className="font-semibold" data-testid="paybill-status">
                {PAYBILL[overview.paybill_mode]}
              </span>
              <span className="text-muted">
                The Paybill and its keys are set on the server (the <code>MPESA_*</code> settings),
                so they never pass through the app.{" "}
                {overview.subscriptions_required
                  ? "Lapsed businesses become read-only after 7 days."
                  : "Lapsed businesses are not locked yet (SUBSCRIPTIONS_REQUIRED is off)."}
              </span>
            </div>
            <PriceForm price={overview.price} onSaved={setOverview} />
          </div>
        </>
      )}
      <Businesses onChanged={refresh} />
      <Payments version={version} />
    </section>
  );
}
