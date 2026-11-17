export default function Field({ label, name, error, children, ...inputProps }) {
  const id = `field-${name}`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-semibold">
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
      {error && <span className="text-sm text-danger">{error}</span>}
    </div>
  );
}
