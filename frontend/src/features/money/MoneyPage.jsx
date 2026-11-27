import { useEffect, useState } from "react";

import { api } from "../../api/client";
import Field from "../../components/Field";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import Pagination from "../../components/Pagination";
import { dateTime, money, shortDate } from "../../format";
import { CATEGORY_NAMES, MONEY_IN, MONEY_OUT } from "./categories";

const SOURCES = { statement: "Statement (PDF)", csv: "Statement (CSV)", sms: "Pasted messages" };

function summary(batch) {
  const parts = [`Added ${batch.added} transaction${batch.added === 1 ? "" : "s"}`];
  if (batch.duplicates) parts.push(`${batch.duplicates} were already here`);
  if (batch.skipped) parts.push(`${batch.skipped} failed or unreadable rows were skipped`);
  return `${parts.join("; ")}.`;
}

function StatementUpload({ onImported }) {
  const [file, setFile] = useState(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    if (!file) {
      setError("Choose your M-Pesa statement first.");
      return;
    }
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append("file", file);
    form.append("password", password);
    try {
      onImported(await api("/api/money/statement", { method: "POST", body: form }));
      setFile(null);
      setPassword("");
      event.target.reset();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="card flex flex-col gap-4 p-6">
      <div>
        <h2 className="text-lg font-bold">Upload a statement</h2>
        <p className="text-sm text-muted">
          Get a full statement from the M-Pesa app or *334#. Safaricom sends its password by SMS.
        </p>
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="statement-file" className="text-sm font-medium text-ink-2">
          Statement file (PDF or CSV)
        </label>
        <input
          id="statement-file"
          type="file"
          accept=".pdf,.csv,application/pdf,text/csv"
          onChange={(event) => setFile(event.target.files[0] || null)}
          className="input py-2"
        />
      </div>
      <Field
        label="Statement password"
        name="statement-password"
        type="password"
        autoComplete="off"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button type="submit" disabled={busy} className="btn-primary self-start">
        <Icon name="up" size={16} />
        {busy ? "Reading…" : "Read statement"}
      </button>
    </form>
  );
}

function PasteMessages({ onImported }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onImported(await api("/api/money/sms", { method: "POST", body: { text } }));
      setText("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="card flex flex-col gap-4 p-6">
      <div>
        <h2 className="text-lg font-bold">Paste M-Pesa messages</h2>
        <p className="text-sm text-muted">
          Copy confirmation messages from your phone and paste them here, as many as you like.
        </p>
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="sms-text" className="text-sm font-medium text-ink-2">
          Messages
        </label>
        <textarea
          id="sms-text"
          rows={6}
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="QK71ZP3X12 Confirmed. You have received Ksh1,500.00 from …"
          className="input min-h-32 py-2"
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button type="submit" disabled={busy || !text.trim()} className="btn-primary self-start">
        Read messages
      </button>
    </form>
  );
}

function Imports({ version, onUndone }) {
  const [list, setList] = useState(null);

  useEffect(() => {
    api("/api/money/imports?per_page=5").then(setList);
  }, [version]);

  if (!list?.count) return null;

  const undo = async (batch) => {
    await api(`/api/money/imports/${batch.id}`, { method: "DELETE" });
    onUndone(`Removed the ${batch.added} transactions from that import.`);
  };

  return (
    <section aria-labelledby="imports-title" className="panel overflow-hidden">
      <h2 id="imports-title" className="border-b border-line p-4 text-lg font-bold">
        Recent imports
      </h2>
      <ul className="divide-y divide-line text-sm">
        {list.results.map((batch) => (
          <li key={batch.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
            <span className="font-semibold">{SOURCES[batch.source]}</span>
            {batch.filename && <span className="text-muted">{batch.filename}</span>}
            <span className="text-muted">{summary(batch)}</span>
            <button
              type="button"
              onClick={() => undo(batch)}
              className="btn-ghost ml-auto text-danger"
              aria-label={`Undo import from ${dateTime(batch.created_at)}`}
            >
              Undo
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function CategoryPicker({ row, onSaved }) {
  const choices = row.direction === "in" ? MONEY_IN : MONEY_OUT;
  const change = async (event) => {
    const result = await api(`/api/money/transactions/${row.id}`, {
      method: "PUT",
      body: { category: event.target.value, remember: true },
    });
    onSaved(result, row);
  };
  return (
    <>
      <label htmlFor={`category-${row.id}`} className="sr-only">
        Category for {row.receipt}
      </label>
      <select
        id={`category-${row.id}`}
        value={row.category}
        onChange={change}
        className="input w-auto px-2 py-1 text-sm"
      >
        {choices.map((key) => (
          <option key={key} value={key}>
            {CATEGORY_NAMES[key]}
          </option>
        ))}
      </select>
    </>
  );
}

function Totals({ totals, category, onPick }) {
  if (!totals?.count) return null;
  const spending = totals.by_category.filter((group) => group.direction === "out").slice(0, 6);
  const top = spending[0]?.total || 1;
  return (
    <div className="flex flex-col gap-4 border-b border-line p-4">
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <dt className="text-xs text-muted">Money in</dt>
          <dd className="figure text-lg text-brand-dark">{money(totals.money_in)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Money out</dt>
          <dd className="figure text-lg">{money(totals.money_out)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Difference</dt>
          <dd className={`figure text-lg ${Number(totals.net) < 0 ? "text-danger" : ""}`}>
            {money(totals.net)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted">M-Pesa charges</dt>
          <dd className="figure text-lg">{money(totals.charges)}</dd>
        </div>
      </dl>
      <p className="text-xs text-muted">
        {totals.count} transaction{totals.count === 1 ? "" : "s"} from {shortDate(totals.first_at)}{" "}
        to {shortDate(totals.last_at)}
      </p>
      {!category && spending.length > 1 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold">Where the money went</h3>
          <ul className="flex flex-col gap-1.5 text-sm">
            {spending.map((group) => (
              <li key={group.category}>
                <button
                  type="button"
                  onClick={() => onPick(group.category)}
                  className="grid w-full grid-cols-[10rem_1fr_7rem] items-center gap-3 text-left hover:opacity-80"
                >
                  <span className="truncate">{CATEGORY_NAMES[group.category]}</span>
                  <span className="h-2 rounded-full bg-line">
                    <span
                      className="block h-2 rounded-full bg-[var(--sp-chart)]"
                      style={{ width: `${(Number(group.total) / Number(top)) * 100}%` }}
                    />
                  </span>
                  <span className="figure text-right">{money(group.total)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Transactions({ version, onNotice }) {
  const [direction, setDirection] = useState("");
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [list, setList] = useState(null);
  const [totals, setTotals] = useState(null);

  const load = () => {
    const filters = new URLSearchParams();
    if (direction) filters.set("direction", direction);
    if (category) filters.set("category", category);
    if (search) filters.set("search", search);
    api(`/api/money/totals?${filters}`).then(setTotals);
    return api(`/api/money/transactions?${filters}&page=${page}&per_page=20`).then(setList);
  };

  useEffect(() => {
    const timer = setTimeout(load, 200);
    return () => clearTimeout(timer);
  }, [direction, category, search, page, version]);

  const saved = (result, row) => {
    const who = row.counterparty || "this sender";
    onNotice(
      result.also_changed
        ? `Saved. ${result.also_changed} earlier payment${result.also_changed === 1 ? "" : "s"} with ${who} changed too, and future ones will follow.`
        : `Saved. Future payments with ${who} will be sorted the same way.`,
    );
    load();
  };

  return (
    <section aria-labelledby="transactions-title" className="panel overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
        <h2 id="transactions-title" className="mr-auto text-lg font-bold">
          Transactions
        </h2>
        <label htmlFor="money-direction" className="sr-only">
          Direction
        </label>
        <select
          id="money-direction"
          value={direction}
          onChange={(event) => {
            setDirection(event.target.value);
            setCategory("");
            setPage(1);
          }}
          className="input w-auto px-2"
        >
          <option value="">Money in and out</option>
          <option value="in">Money in</option>
          <option value="out">Money out</option>
        </select>
        <label htmlFor="money-category" className="sr-only">
          Category
        </label>
        <select
          id="money-category"
          value={category}
          onChange={(event) => {
            setCategory(event.target.value);
            setPage(1);
          }}
          className="input w-auto px-2"
        >
          <option value="">Every category</option>
          {(direction === "out"
            ? MONEY_OUT
            : direction === "in"
              ? MONEY_IN
              : Object.keys(CATEGORY_NAMES)
          ).map((key) => (
            <option key={key} value={key}>
              {CATEGORY_NAMES[key]}
            </option>
          ))}
        </select>
        <label htmlFor="money-search" className="sr-only">
          Search
        </label>
        <input
          id="money-search"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Name, number or code"
          className="input w-52"
        />
      </div>
      <Totals
        totals={totals}
        category={category}
        onPick={(picked) => {
          setDirection("out");
          setCategory(picked);
          setPage(1);
        }}
      />
      {list?.count === 0 ? (
        <p className="p-8 text-center text-muted">
          Nothing yet. Upload a statement or paste messages to see your money here.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted uppercase">
              <tr>
                <th className="px-4 py-3">When</th>
                <th className="px-4 py-3">Who</th>
                <th className="px-4 py-3 text-right">Amount</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3">Code</th>
              </tr>
            </thead>
            <tbody>
              {list?.results.map((row) => (
                <tr key={row.id} className="border-t border-line">
                  <td className="px-4 py-2 whitespace-nowrap">{dateTime(row.occurred_at)}</td>
                  <td className="px-4 py-2">
                    {row.counterparty || "—"}
                    {row.sale_id && (
                      <span className="ml-2 rounded-full bg-mint px-2 py-0.5 text-xs text-brand-dark">
                        Till sale
                      </span>
                    )}
                  </td>
                  <td
                    className={`figure px-4 py-2 text-right ${row.direction === "in" ? "text-brand-dark" : ""}`}
                  >
                    {row.direction === "in" ? "+" : "−"}
                    {money(row.amount)}
                  </td>
                  <td className="px-4 py-2">
                    <CategoryPicker row={row} onSaved={saved} />
                  </td>
                  <td className="code px-4 py-2">{row.receipt}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {list && (
        <Pagination page={list.page} pages={list.pages} count={list.count} onChange={setPage} />
      )}
    </section>
  );
}

export default function MoneyPage() {
  const [version, setVersion] = useState(0);
  const [notice, setNotice] = useState("");

  const imported = (batch) => {
    setNotice(summary(batch));
    setVersion((current) => current + 1);
  };

  return (
    <section className="flex flex-col gap-6">
      <PageHeader
        title="M-Pesa money"
        subtitle="Bring in your M-Pesa history so StockPilot can sort your money and forecast what is coming."
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <StatementUpload onImported={imported} />
        <PasteMessages onImported={imported} />
      </div>
      {notice && (
        <p role="status" className="rounded-xl border border-brand/30 bg-mint p-3 text-sm">
          {notice}
        </p>
      )}
      <Imports
        version={version}
        onUndone={(message) => {
          setNotice(message);
          setVersion((current) => current + 1);
        }}
      />
      <Transactions version={version} onNotice={setNotice} />
    </section>
  );
}
