const STYLES = {
  pending: "bg-amber-100 text-amber-900",
  approved: "bg-mint text-brand-dark",
  rejected: "bg-orange-100 text-orange-900",
  available: "bg-mint text-brand-dark",
  assigned: "bg-sky-100 text-sky-900",
  in_repair: "bg-orange-100 text-orange-900",
  low: "bg-canvas text-muted",
  normal: "bg-canvas text-muted",
  high: "bg-amber-100 text-amber-900",
  urgent: "bg-orange-100 text-orange-900",
};

export const LABELS = { in_repair: "In repair" };

export const label = (value) =>
  LABELS[value] || value.charAt(0).toUpperCase() + value.slice(1).replace("_", " ");

export default function StatusBadge({ value }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${STYLES[value] || "bg-canvas text-muted"}`}
    >
      {label(value)}
    </span>
  );
}
