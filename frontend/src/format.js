const shillings = new Intl.NumberFormat("en-KE", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

// The signed-in business's currency (set from the account when it loads; KES by default).
let currency = "KES";
export const setCurrency = (code) => {
  currency = code || "KES";
};
export const currencyCode = () => currency;

export const money = (value) => `${currency} ${shillings.format(Number(value || 0))}`;

// "07 Nov 2026, 09:30"
export const fullDateTime = (iso) =>
  iso
    ? new Date(iso).toLocaleString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

// "10 min ago" for the last day, then "07 Nov 2026, 09:30" (US-40, US-45).
export const whenShort = (iso) => {
  if (!iso) return "";
  const hours = (Date.now() - new Date(iso).getTime()) / 3600000;
  return hours < 24 ? timeAgo(iso) : fullDateTime(iso);
};

// Today's date in the user's clock as YYYY-MM-DD (for date inputs and filters).
export const isoToday = () => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

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
