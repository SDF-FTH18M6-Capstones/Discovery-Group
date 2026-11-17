export default function Field({ label, name, error, children, ...inputProps }) {
  const id = `field-${name}`;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-ink-2">
        {label}
      </label>
      {children ? (
        children(id)
      ) : (
        <input
          id={id}
          name={name}
          aria-invalid={Boolean(error)}
          className={`input ${error ? "border-danger" : ""}`}
          {...inputProps}
        />
      )}
      {error && (
        <span className="flex items-center gap-1.5 text-sm text-danger">
          <span aria-hidden="true" className="size-1.5 rounded-full bg-danger" />
          {error}
        </span>
      )}
    </div>
  );
}
