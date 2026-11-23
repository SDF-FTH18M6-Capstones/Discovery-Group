import { useEffect, useId, useRef, useState } from "react";

import { api } from "../api/client";

// Type to search the API and pick one result. Replaces dropdowns that could only list the
// first 100 records. `path` is a list endpoint that accepts ?search=…; `describe(item)` gives
// the main and secondary text of each option.
export default function SearchPicker({
  label,
  path,
  extra = "",
  value,
  onPick,
  describe,
  placeholder = "Type to search",
  error,
  id: givenId,
}) {
  const autoId = useId();
  const id = givenId || autoId;
  const listId = `${id}-options`;
  const [text, setText] = useState(value ? describe(value).title : "");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const timer = useRef(null);

  useEffect(() => {
    setText(value ? describe(value).title : "");
  }, [value]);

  const search = (term) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      api(`${path}?per_page=8&search=${encodeURIComponent(term)}${extra}`)
        .then((data) => {
          setResults(data.results || data);
          setActive(0);
          setOpen(true);
        })
        .catch(() => setResults([]));
    }, 200);
  };

  useEffect(() => () => clearTimeout(timer.current), []);

  const pick = (item) => {
    onPick(item);
    setText(item ? describe(item).title : "");
    setOpen(false);
  };

  return (
    <div className="relative flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-ink-2">
        {label}
      </label>
      <input
        id={id}
        type="search"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-invalid={Boolean(error)}
        autoComplete="off"
        placeholder={placeholder}
        className={`input ${error ? "border-danger" : ""}`}
        value={text}
        onFocus={() => search(text && value ? "" : text)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(event) => {
          setText(event.target.value);
          if (value) onPick(null);
          search(event.target.value);
        }}
        onKeyDown={(event) => {
          if (!open || !results.length) return;
          if (event.key === "ArrowDown") {
            event.preventDefault();
            setActive((i) => Math.min(i + 1, results.length - 1));
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (event.key === "Enter") {
            event.preventDefault();
            pick(results[active]);
          } else if (event.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {open && results.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute top-full right-0 left-0 z-30 mt-1 max-h-72 overflow-y-auto rounded-xl border border-line bg-raised p-1 shadow-[var(--sp-shadow-lg)]"
        >
          {results.map((item, index) => {
            const { title, detail } = describe(item);
            return (
              <li
                key={item.id}
                role="option"
                aria-selected={index === active}
                onMouseDown={(event) => {
                  event.preventDefault();
                  pick(item);
                }}
                className={`flex cursor-pointer items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm ${index === active ? "bg-mint text-brand-dark" : "hover:bg-surface-2"}`}
              >
                <span className="truncate font-medium">{title}</span>
                {detail && <span className="shrink-0 text-xs text-muted">{detail}</span>}
              </li>
            );
          })}
        </ul>
      )}
      {open && results.length === 0 && text && (
        <p className="absolute top-full right-0 left-0 z-30 mt-1 rounded-xl border border-line bg-raised p-3 text-sm text-muted shadow-[var(--sp-shadow-lg)]">
          Nothing matches “{text}”.
        </p>
      )}
      {error && <span className="text-sm text-danger">{error}</span>}
    </div>
  );
}

export const describeProduct = (product) => ({
  title: product.name,
  detail: `${product.sku} · ${product.quantity} in stock`,
});
