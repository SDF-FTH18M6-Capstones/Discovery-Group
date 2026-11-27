import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../api/client";
import Field from "../../components/Field";
import Icon from "../../components/Icon";
import PageHeader from "../../components/PageHeader";
import SearchPicker, { describeProduct } from "../../components/SearchPicker";
import { isoToday, money } from "../../format";
import { readOnDevice, shrink } from "./readPhoto";

const EXPENSE_IDEAS = ["Transport", "Fuel", "Repairs", "Rent", "Electricity", "Office supplies"];

let nextKey = 0;
const asLine = (item) => ({
  key: (nextKey += 1),
  description: item.description,
  product: item.product || null,
  quantity: String(Math.max(1, Math.round(Number(item.quantity) || 1))),
  unit_cost: item.unit_price ? Number(item.unit_price).toFixed(2) : "",
  include: Boolean(item.product),
});

function PhotoStep({ reader, onRead }) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const choose = async (event) => {
    const file = event.target.files[0];
    event.target.value = "";
    if (!file) return;
    setError("");
    const preview = URL.createObjectURL(file);
    try {
      if (reader.mode === "ai") {
        setBusy("Reading the receipt…");
        const form = new FormData();
        form.append("photo", await shrink(file), "receipt.jpg");
        onRead(await api("/api/receipts/photo", { method: "POST", body: form }), preview);
      } else {
        setBusy("Reading the receipt on this device…");
        const text = await readOnDevice(await shrink(file, { grey: true }), (percent) =>
          setBusy(`Reading the receipt on this device… ${percent}%`),
        );
        onRead(await api("/api/receipts/text", { method: "POST", body: { text } }), preview);
      }
    } catch (err) {
      setError(err.message || "The photo could not be read. Try again in better light.");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="card flex flex-col items-start gap-4 p-6">
      <div>
        <h2 className="text-lg font-bold">Photograph the receipt</h2>
        <p className="text-sm text-muted">
          Lay it flat in good light and fill the frame. You can check and correct everything before
          it is saved.
        </p>
      </div>
      <label
        htmlFor="receipt-photo"
        className={`btn-primary cursor-pointer ${busy ? "pointer-events-none opacity-60" : ""}`}
      >
        <Icon name="camera" size={16} />
        {busy ? "Reading…" : "Take or choose a photo"}
      </label>
      <input
        id="receipt-photo"
        type="file"
        accept="image/*"
        capture="environment"
        onChange={choose}
        disabled={Boolean(busy)}
        className="sr-only"
      />
      {busy && (
        <p role="status" className="text-sm text-muted">
          {busy}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <p className="text-xs text-muted">
        {reader.mode === "ai"
          ? "Photos are read online and are not kept."
          : "The photo is read on this device and is not uploaded."}
      </p>
    </div>
  );
}

function ExpenseForm({ reading, onSaved }) {
  const [values, setValues] = useState({
    spent_on: reading.date || isoToday(),
    category: "",
    description: [reading.supplier, reading.number && `receipt ${reading.number}`]
      .filter(Boolean)
      .join(", "),
    amount: reading.total ? Number(reading.total).toFixed(2) : "",
  });
  const [error, setError] = useState("");
  const set = (name) => (event) => setValues((c) => ({ ...c, [name]: event.target.value }));

  const save = async (event) => {
    event.preventDefault();
    if (values.category.trim().length < 2 || !(Number(values.amount) > 0)) {
      setError("Give a category and an amount above 0.");
      return;
    }
    try {
      await api("/api/expenses/", {
        method: "POST",
        body: {
          spent_on: values.spent_on,
          category: values.category.trim(),
          description: values.description.trim() || null,
          amount: Number(values.amount).toFixed(2),
        },
      });
      onSaved({ kind: "expense", amount: values.amount });
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <form onSubmit={save} noValidate className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Category"
          name="expense-category"
          list="expense-ideas"
          value={values.category}
          onChange={set("category")}
        />
        <datalist id="expense-ideas">
          {EXPENSE_IDEAS.map((idea) => (
            <option key={idea} value={idea} />
          ))}
        </datalist>
        <Field
          label="Amount"
          name="expense-amount"
          type="number"
          min="0"
          step="0.01"
          value={values.amount}
          onChange={set("amount")}
        />
        <Field
          label="Date"
          name="expense-date"
          type="date"
          value={values.spent_on}
          onChange={set("spent_on")}
        />
        <Field
          label="Description"
          name="expense-description"
          value={values.description}
          onChange={set("description")}
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button type="submit" className="btn-primary self-start">
        Save expense
      </button>
    </form>
  );
}

function StockForm({ reading, onSaved }) {
  const [supplier, setSupplier] = useState(reading.supplier || "");
  const [lines, setLines] = useState(() =>
    reading.items.length ? reading.items.map(asLine) : [asLine({ description: "" })],
  );
  const [error, setError] = useState("");

  const change = (key, name, value) =>
    setLines((current) =>
      current.map((line) =>
        line.key === key
          ? { ...line, [name]: value, ...(name === "product" ? { include: Boolean(value) } : {}) }
          : line,
      ),
    );
  const chosen = lines.filter((line) => line.include && line.product);
  const total = chosen.reduce(
    (sum, line) => sum + Number(line.quantity || 0) * Number(line.unit_cost || 0),
    0,
  );

  const save = async (event) => {
    event.preventDefault();
    if (!chosen.length) {
      setError("Match at least one line to a product.");
      return;
    }
    if (chosen.some((line) => !(Number(line.quantity) >= 1) || line.unit_cost === "")) {
      setError("Every ticked line needs a quantity and a cost.");
      return;
    }
    const sameSupplier = reading.supplier_id && supplier === reading.supplier;
    try {
      const result = await api("/api/receipts/stock", {
        method: "POST",
        body: {
          supplier_id: sameSupplier ? reading.supplier_id : null,
          supplier_name: sameSupplier ? null : supplier.trim(),
          number: reading.number,
          lines: chosen.map((line) => ({
            product_id: line.product.id,
            quantity: Number(line.quantity),
            unit_cost: Number(line.unit_cost).toFixed(2),
          })),
        },
      });
      onSaved({ kind: "stock", ...result });
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <form onSubmit={save} noValidate className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <Field
          label="Bought from"
          name="stock-supplier"
          value={supplier}
          onChange={(event) => setSupplier(event.target.value)}
        />
        <p className="text-xs text-muted">
          {reading.supplier_id && supplier === reading.supplier
            ? "One of your suppliers."
            : "A new name is added to your suppliers."}
        </p>
      </div>
      <ul className="flex flex-col gap-3">
        {lines.map((line, index) => (
          <li
            key={line.key}
            className="grid grid-cols-[auto_minmax(0,1fr)_5rem_7rem] items-end gap-2 rounded-xl border border-line p-3"
          >
            <input
              type="checkbox"
              aria-label={`Add line ${index + 1} to stock`}
              checked={line.include}
              disabled={!line.product}
              onChange={(event) => change(line.key, "include", event.target.checked)}
              className="mb-3 size-4"
            />
            <div className="flex flex-col gap-1">
              {line.description && (
                <span className="text-xs text-muted">On the receipt: {line.description}</span>
              )}
              <SearchPicker
                id={`receipt-line-${line.key}`}
                label={`Product ${index + 1}`}
                path="/api/products/"
                placeholder="Name or SKU"
                value={line.product}
                describe={describeProduct}
                onPick={(picked) => change(line.key, "product", picked)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor={`receipt-qty-${line.key}`} className="text-xs text-muted">
                Qty {index + 1}
              </label>
              <input
                id={`receipt-qty-${line.key}`}
                type="number"
                min="1"
                value={line.quantity}
                onChange={(event) => change(line.key, "quantity", event.target.value)}
                className="input w-full text-sm"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor={`receipt-cost-${line.key}`} className="text-xs text-muted">
                Unit cost {index + 1}
              </label>
              <input
                id={`receipt-cost-${line.key}`}
                type="number"
                min="0"
                step="0.01"
                value={line.unit_cost}
                onChange={(event) => change(line.key, "unit_cost", event.target.value)}
                className="input w-full text-sm"
              />
            </div>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setLines((current) => [...current, asLine({ description: "" })])}
          className="btn-secondary"
        >
          Add a line
        </button>
        <span className="text-sm text-muted">
          {chosen.length} product{chosen.length === 1 ? "" : "s"} · {money(total)}
          {reading.total ? ` (receipt total ${money(reading.total)})` : ""}
        </span>
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button type="submit" className="btn-primary self-start">
        Add to stock
      </button>
    </form>
  );
}

function Review({ reader, reading, preview, onSaved, onRestart }) {
  const [kind, setKind] = useState(
    reader.can_stock && reading.items.some((item) => item.product)
      ? "stock"
      : reader.can_expense
        ? "expense"
        : "stock",
  );
  const choices = [
    reader.can_expense && ["expense", "An expense", "Fuel, repairs, transport, rent…"],
    reader.can_stock && ["stock", "Stock I bought", "The items go into inventory"],
  ].filter(Boolean);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <figure className="card overflow-hidden p-2">
        <img src={preview} alt="The receipt you photographed" className="w-full rounded-lg" />
      </figure>
      <div className="card flex flex-col gap-5 p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold">{reading.supplier || "Receipt"}</h2>
            <p className="text-sm text-muted">
              {[
                reading.date,
                reading.number && `No. ${reading.number}`,
                reading.total && money(reading.total),
              ]
                .filter(Boolean)
                .join(" · ") || "Check the details against the photo."}
            </p>
          </div>
          <button type="button" onClick={onRestart} className="btn-ghost">
            Use another photo
          </button>
        </div>
        {choices.length > 1 && (
          <fieldset className="flex flex-wrap gap-3">
            <legend className="mb-2 text-sm font-medium text-ink-2">
              What is this receipt for?
            </legend>
            {choices.map(([value, label, hint]) => (
              <label
                key={value}
                className={`flex cursor-pointer flex-col rounded-xl border px-4 py-2 ${kind === value ? "border-brand bg-mint" : "border-line"}`}
              >
                <span className="flex items-center gap-2 font-semibold">
                  <input
                    type="radio"
                    name="receipt-kind"
                    value={value}
                    checked={kind === value}
                    onChange={() => setKind(value)}
                  />
                  {label}
                </span>
                <span className="text-xs text-muted">{hint}</span>
              </label>
            ))}
          </fieldset>
        )}
        {kind === "expense" ? (
          <ExpenseForm reading={reading} onSaved={onSaved} />
        ) : (
          <StockForm reading={reading} onSaved={onSaved} />
        )}
      </div>
    </div>
  );
}

export default function ScanPage() {
  const [reader, setReader] = useState(null);
  const [reading, setReading] = useState(null);
  const [preview, setPreview] = useState("");
  const [saved, setSaved] = useState(null);

  useEffect(() => {
    api("/api/receipts/reader").then(setReader);
  }, []);

  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  const restart = () => {
    setReading(null);
    setPreview("");
    setSaved(null);
  };

  return (
    <section className="flex flex-col gap-6">
      <PageHeader
        title="Scan a receipt"
        subtitle="Turn a paper receipt into an expense or a stock purchase without typing it all in."
      />
      {saved && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-brand/30 bg-mint p-4 text-sm"
        >
          {saved.kind === "expense" ? (
            <span>
              Expense of {money(saved.amount)} saved. It shows in{" "}
              <Link to="/reports" className="font-semibold underline">
                Reports
              </Link>
              .
            </span>
          ) : (
            <span>
              Stock added as{" "}
              <Link to={`/purchases?open=${saved.purchase_id}`} className="font-semibold underline">
                {saved.reference}
              </Link>{" "}
              ({money(saved.total)}).
            </span>
          )}
          <button type="button" onClick={restart} className="btn-secondary ml-auto">
            Scan another
          </button>
        </div>
      )}
      {!reader ? (
        <p className="text-muted">Loading…</p>
      ) : reading && !saved ? (
        <Review
          reader={reader}
          reading={reading}
          preview={preview}
          onSaved={setSaved}
          onRestart={restart}
        />
      ) : (
        !saved && (
          <PhotoStep
            reader={reader}
            onRead={(result, photo) => {
              setPreview(photo);
              setReading(result);
            }}
          />
        )
      )}
    </section>
  );
}
