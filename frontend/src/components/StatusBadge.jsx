const STYLES = {
  pending: "bg-warn-soft text-warn",
  ordered: "bg-warn-soft text-warn",
  submitted: "bg-warn-soft text-warn",
  approved: "bg-mint text-brand-dark",
  received: "bg-mint text-brand-dark",
  available: "bg-mint text-brand-dark",
  done: "bg-mint text-brand-dark",
  assigned: "bg-info-soft text-info",
  in_progress: "bg-info-soft text-info",
  rejected: "bg-danger-soft text-danger",
  cancelled: "bg-danger-soft text-danger",
  in_repair: "bg-danger-soft text-danger",
  urgent: "bg-danger-soft text-danger",
  high: "bg-warn-soft text-warn",
  low: "bg-surface-2 text-muted",
  normal: "bg-surface-2 text-muted",
  purchase: "bg-mint text-brand-dark",
  sale: "bg-info-soft text-info",
  adjustment: "bg-surface-2 text-muted",
  cash: "bg-surface-2 text-muted",
  mpesa: "bg-mint text-brand-dark",
  card: "bg-info-soft text-info",
  low_stock: "bg-warn-soft text-warn",
  out_of_stock: "bg-danger-soft text-danger",
};

export const LABELS = {
  in_repair: "In repair",
  in_progress: "In progress",
  mpesa: "M-Pesa",
  low_stock: "Low stock",
  out_of_stock: "Out of stock",
};

export const label = (value) =>
  LABELS[value] || value.charAt(0).toUpperCase() + value.slice(1).replaceAll("_", " ");

export default function StatusBadge({ value }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold whitespace-nowrap ${STYLES[value] || "bg-surface-2 text-muted"}`}
    >
      {label(value)}
    </span>
  );
}
