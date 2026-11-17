export default function Pagination({ page, pages, count, onChange, standalone = false }) {
  if (!count) return null;
  return (
    <nav
      aria-label="Pagination"
      className={`flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-sm text-muted ${standalone ? "panel" : "border-t border-line"}`}
    >
      <span>
        Page {page} of {pages} · {count} total
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          className="btn-secondary min-h-0 px-3 py-1.5 text-sm"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          Previous
        </button>
        <button
          type="button"
          className="btn-secondary min-h-0 px-3 py-1.5 text-sm"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          Next
        </button>
      </div>
    </nav>
  );
}