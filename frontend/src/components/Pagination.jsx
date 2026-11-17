export default function Pagination({ page, pages, count, onChange }) {
  if (!count) return null;
  return (
    <nav
      aria-label="Pagination"
      className="flex items-center justify-between gap-3 p-3 text-sm text-muted"
    >
      <span>
        Page {page} of {pages} · {count} total
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          className="btn-secondary px-3 py-1 text-sm"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          Previous
        </button>
        <button
          type="button"
          className="btn-secondary px-3 py-1 text-sm"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          Next
        </button>
      </div>
    </nav>
  );
}
