const shillings = new Intl.NumberFormat("en-KE", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export const money = (value) => `KES ${shillings.format(Number(value || 0))}`;

export const shortDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "";

export const dateTime = (iso) =>
  iso
    ? new Date(iso).toLocaleString("en-GB", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

export const PAYMENT_LABELS = { cash: "Cash", mpesa: "M-Pesa", card: "Card" };

// "just now", "5 min ago", "3 h ago", "yesterday", then the date.
export function timeAgo(iso) {
  if (!iso) return "";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  if (hours < 48) return "yesterday";
  return shortDate(iso);
}

// Money without the currency, for tight columns and chart axes.
export const amount = (value) => shillings.format(Number(value || 0));