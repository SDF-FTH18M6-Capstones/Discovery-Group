import { useEffect, useState } from "react";

import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import Field from "../../components/Field";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import { longDate } from "../../format";

const STATUS_TEXT = {
  trial: "Free trial",
  active: "Active",
  grace: "Payment due",
  expired: "Ended",
};

const kes = (amount) => `KES ${Number(amount).toLocaleString("en-KE")}`;

function Plan({ months, price, chosen, onChoose }) {
  return (
    <label
      className={`flex cursor-pointer flex-col gap-1 rounded-xl border p-4 ${
        chosen ? "border-brand bg-mint" : "border-line-strong hover:border-brand"
      }`}
    >
      <input
        type="radio"
        name="months"
        value={months}
        checked={chosen}
        onChange={() => onChoose(months)}
        className="sr-only"
      />
      <span className="text-sm text-muted">
        {months} month{months === 1 ? "" : "s"}
      </span>
      <span className="figure text-xl">{kes(price * months)}</span>
    </label>
  );
}

export default function BillingPage() {
  const { reloadUser } = useAuth();
  const [overview, setOverview] = useState(null);
  const [months, setMonths] = useState(1);
  const [phone, setPhone] = useState("");
  const [prompt, setPrompt] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () =>
    api("/api/billing")
      .then(setOverview)
      .catch((err) => setError(err.message));

  useEffect(() => {
    load();
  }, []);

  const follow = async (payment) => {
    if (payment.status === "pending") {
      setPrompt(payment);
      return;
    }
    setPrompt(null);
    if (payment.status === "paid") {
      setMessage(`Paid. Thank you! M-Pesa receipt ${payment.receipt_number}.`);
      await Promise.all([load(), reloadUser()]);
    } else {
      setError(payment.result_desc || "The payment did not go through.");
    }
  };

  useEffect(() => {
    if (!prompt || prompt.status !== "pending") return undefined;
    const timer = setTimeout(() => {
      api(`/api/billing/payments/${prompt.id}`)
        .then(follow)
        .catch(() => setPrompt({ ...prompt }));
    }, 2000);
    return () => clearTimeout(timer);
  }, [prompt]);

  const pay = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await follow(await api("/api/billing/pay", { method: "POST", body: { months, phone } }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const simulate = async (outcome) => {
    try {
      await follow(
        await api(`/api/billing/payments/${prompt.id}/simulate`, {
          method: "POST",
          body: { outcome },
        }),
      );
    } catch (err) {
      setError(err.message);
    }
  };

  if (!overview) {
    return error ? (
      <p role="alert" className="text-danger">
        {error}
      </p>
    ) : null;
  }

  const until = overview.status === "trial" ? overview.trial_ends_on : overview.ends_on;

  return (
    <section className="flex flex-col gap-6">
      <PageHeader title="Billing" subtitle="Your StockPilot subscription, paid by M-Pesa." />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="flex flex-col gap-6">
          <div className="card flex flex-col gap-2 p-6">
            <span className="text-sm text-muted">Status</span>
            <span className="text-2xl font-bold" data-testid="billing-status">
              {STATUS_TEXT[overview.status]}
            </span>
            <p className="text-muted">
              {overview.status === "grace" || overview.status === "expired"
                ? `Ended on ${longDate(overview.ends_on)}. ${
                    overview.status === "grace"
                      ? `Everything keeps working until ${longDate(overview.grace_until)}.`
                      : "Your data is safe, but changes are paused until you renew."
                  }`
                : `Paid up to ${longDate(until)} (${overview.days_left} days left).`}
            </p>
          </div>

          <div className="card flex flex-col gap-3 p-6">
            <h2 className="text-lg font-bold">Payments</h2>
            {overview.payments.length === 0 ? (
              <p className="text-sm text-muted">No payments yet.</p>
            ) : (
              <ul className="divide-y divide-line text-sm">
                {overview.payments.map((payment) => (
                  <li key={payment.id} className="flex justify-between gap-3 py-2">
                    <span>
                      {longDate(payment.completed_at)} · {payment.months} month
                      {payment.months === 1 ? "" : "s"}
                    </span>
                    <span className="code">{payment.receipt_number}</span>
                    <span className="font-semibold">{kes(payment.amount)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <form onSubmit={pay} noValidate className="card flex flex-col gap-4 p-6">
          <h2 className="text-lg font-bold">Pay for StockPilot</h2>
          {!overview.online_payment ? (
            <p className="text-sm text-muted">
              Paying by M-Pesa is not available yet. Contact StockPilot to renew.
            </p>
          ) : prompt ? (
            <div role="status" className="flex flex-col gap-3 rounded-xl bg-mint p-4 text-sm">
              <p className="flex items-center gap-2 font-semibold text-brand-dark">
                <span className="size-2.5 animate-pulse rounded-full bg-brand" />
                Check your phone
              </p>
              <p>
                Enter your M-Pesa PIN to pay {kes(prompt.amount)} to StockPilot. This page updates
                by itself.
              </p>
              {prompt.simulated && (
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => simulate("paid")} className="btn-primary">
                    Pay (test mode)
                  </button>
                  <button
                    type="button"
                    onClick={() => simulate("cancelled")}
                    className="btn-secondary"
                  >
                    Cancel (test mode)
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              <fieldset className="grid grid-cols-2 gap-2">
                <legend className="mb-2 text-sm font-medium text-ink-2">
                  {kes(overview.price)} a month
                </legend>
                {overview.plans.map((plan) => (
                  <Plan
                    key={plan}
                    months={plan}
                    price={overview.price}
                    chosen={months === plan}
                    onChoose={setMonths}
                  />
                ))}
              </fieldset>
              <Field
                label="M-Pesa number to pay from"
                name="billing-phone"
                type="tel"
                inputMode="tel"
                placeholder="0712 345 678"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
              />
              <button type="submit" disabled={busy || !phone.trim()} className="btn-primary">
                <Icon name="phone" size={16} />
                Pay {kes(overview.price * months)}
              </button>
            </>
          )}
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          {message && (
            <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
              {message}
            </p>
          )}
        </form>
      </div>
    </section>
  );
}
