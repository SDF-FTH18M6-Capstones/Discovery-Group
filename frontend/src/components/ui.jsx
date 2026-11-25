import { useState } from "react";
import { Link } from "react-router-dom";

import Icon from "./Icon";

const TONES = {
  brand: "bg-mint text-brand-dark",
  saffron: "bg-saffron-soft text-saffron-ink",
  danger: "bg-danger-soft text-danger",
  info: "bg-info-soft text-info",
  muted: "bg-surface-2 text-muted",
};

export function StatStrip({ items, className = "" }) {
  return (
    <dl
      style={{ "--cols": Math.min(items.length, 4) }}
      className={`panel grid grid-cols-2 sm:grid-cols-3 lg:[grid-template-columns:repeat(var(--cols),minmax(0,1fr))] ${className}`}
    >
      {items.map((item) => {
        const body = (
          <>
            <dt className="flex items-center gap-2 text-[0.8rem] text-muted">
              {item.icon && (
                <span
                  className={`grid size-6 place-items-center rounded-md ${TONES[item.tone || "muted"]}`}
                >
                  <Icon name={item.icon} size={14} />
                </span>
              )}
              {item.label}
            </dt>
            <dd
              className="figure text-[1.4rem] leading-none sm:text-[1.65rem]"
              data-testid={item.testId}
            >
              {item.value ?? "…"}
            </dd>
            {item.hint && <dd className="text-xs text-muted">{item.hint}</dd>}
          </>
        );
        const cell =
          "flex min-w-0 flex-col gap-2 p-4 shadow-[1px_0_0_var(--sp-line),0_1px_0_var(--sp-line)] sm:px-5";
        return item.to ? (
          <Link
            key={item.label}
            to={item.to}
            className={`${cell} transition-colors hover:bg-surface-2`}
          >
            {body}
          </Link>
        ) : (
          <div key={item.label} className={cell}>
            {body}
          </div>
        );
      })}
    </dl>
  );
}

export function Panel({ title, subtitle, actions, children, className = "", bodyClassName = "" }) {
  return (
    <section className={`panel flex min-w-0 flex-col ${className}`}>
      {(title || actions) && (
        <header className="panel-head">
          <div className="min-w-0">
            {title && <h2 className="panel-title">{title}</h2>}
            {subtitle && <p className="text-sm text-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={`min-w-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}

export function EmptyState({ icon = "inbox", title, children, action }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <span className="grid size-12 place-items-center rounded-2xl border border-dashed border-line-strong bg-surface-2 text-muted">
        <Icon name={icon} size={22} />
      </span>
      <p className="font-display text-lg font-semibold">{title}</p>
      {children && <p className="max-w-sm text-sm text-muted">{children}</p>}
      {action}
    </div>
  );
}

export function StockMeter({ quantity, reorder }) {
  const target = Math.max(reorder * 3, 1);
  const share = Math.min(quantity / target, 1);
  const colour = quantity === 0 ? "bg-danger" : quantity <= reorder ? "bg-saffron" : "bg-brand";
  return (
    <div className="meter w-20" aria-hidden="true">
      <span className={colour} style={{ width: `${Math.max(share * 100, quantity ? 6 : 0)}%` }} />
    </div>
  );
}

const AVATAR_TONES = [
  "bg-mint text-brand-dark",
  "bg-saffron-soft text-saffron-ink",
  "bg-info-soft text-info",
  "bg-danger-soft text-danger",
];

export const initials = (name = "") =>
  name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");

export function Avatar({ name, size = 32, className = "" }) {
  const tone = AVATAR_TONES[[...(name || "")].reduce((sum, c) => sum + c.charCodeAt(0), 0) % 4];
  return (
    <span
      aria-hidden="true"
      className={`avatar ${tone} ${className}`}
      style={{ width: size, height: size, fontSize: size * 0.38 }}
    >
      {initials(name)}
    </span>
  );
}

export function Sparkline({ values, className = "" }) {
  if (!values?.length) return null;
  const max = Math.max(...values, 1);
  const width = 120;
  const height = 36;
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const points = values.map((v, i) => [i * step, height - 3 - (v / max) * (height - 6)]);
  const line = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  return (
    <svg
      aria-hidden="true"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={`h-9 w-full overflow-visible ${className}`}
    >
      <polygon points={`0,${height} ${line} ${width},${height}`} fill="var(--sp-brand-soft)" />
      <polyline
        points={line}
        fill="none"
        stroke="var(--sp-chart)"
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const niceMax = (value) => {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  return [1, 2, 4, 8, 10].map((f) => f * power).find((n) => n >= value);
};

export const compact = (value) =>
  value >= 1e6
    ? `${+(value / 1e6).toFixed(1)}M`
    : value >= 1000
      ? `${+(value / 1000).toFixed(1)}k`
      : `${Math.round(value)}`;

export function BarChart({ data, format = String, label, height = 220 }) {
  const [active, setActive] = useState(null);
  const top = niceMax(Math.max(...data.map((d) => d.value), 0));
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * top);
  const shown = active === null ? null : data[active];
  const labelEvery = Math.ceil(data.length / 8);

  return (
    <figure className="flex flex-col gap-2">
      <div className="relative flex gap-3" style={{ height }}>
        <div
          aria-hidden="true"
          className="flex w-14 shrink-0 flex-col-reverse justify-between text-right text-[11px] text-muted tabular"
        >
          {ticks.map((tick) => (
            <span key={tick} className="-translate-y-1/2 first:translate-y-0">
              {compact(tick)}
            </span>
          ))}
        </div>
        <div className="relative min-w-0 flex-1">
          <div
            aria-hidden="true"
            className="absolute inset-0 flex flex-col-reverse justify-between"
          >
            {ticks.map((tick) => (
              <span key={tick} className="border-t border-grid first:border-line-strong" />
            ))}
          </div>
          <div
            className="relative flex h-full items-end gap-[2px]"
            onMouseLeave={() => setActive(null)}
          >
            {data.map((d, i) => (
              <button
                key={d.label}
                type="button"
                aria-label={`${d.label}: ${format(d.value)}${d.detail ? `, ${d.detail}` : ""}`}
                onMouseEnter={() => setActive(i)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
                className="group flex h-full min-w-0 flex-1 items-end focus-visible:outline-offset-0"
              >
                <span
                  className={`w-full rounded-t-[4px] transition-opacity ${active !== null && active !== i ? "opacity-45" : ""}`}
                  style={{
                    height: `${(d.value / top) * 100}%`,
                    minHeight: d.value ? 3 : 0,
                    background: "var(--sp-chart)",
                  }}
                />
              </button>
            ))}
          </div>
          {shown && (
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -top-2 z-10 -translate-x-1/2 -translate-y-full rounded-lg border border-line bg-raised px-3 py-2 text-xs shadow-[var(--sp-shadow-lg)]"
              style={{ left: `${((active + 0.5) / data.length) * 100}%` }}
            >
              <span className="block text-muted">{shown.label}</span>
              <span className="figure block text-sm">{format(shown.value)}</span>
              {shown.detail && <span className="block text-muted">{shown.detail}</span>}
            </div>
          )}
        </div>
      </div>
      <div aria-hidden="true" className="ml-[4.25rem] flex text-[11px] text-muted">
        {data.map((d, i) => (
          <span key={d.label} className="min-w-0 flex-1 truncate text-center">
            {i % labelEvery === 0 ? d.short || d.label : ""}
          </span>
        ))}
      </div>
      {label && (
        <table className="sr-only">
          <caption>{label}</caption>
          <tbody>
            {data.map((d) => (
              <tr key={d.label}>
                <th scope="row">{d.label}</th>
                <td>{format(d.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </figure>
  );
}
