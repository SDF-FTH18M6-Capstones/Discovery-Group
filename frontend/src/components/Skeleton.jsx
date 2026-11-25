export function SkeletonRows({ rows = 5, cols = 4 }) {
  return Array.from({ length: rows }, (_, row) => (
    <tr key={row} className="border-t border-line" aria-hidden="true">
      {Array.from({ length: cols }, (_, col) => (
        <td key={col} className="px-5 py-4">
          <div className="skeleton h-4" style={{ width: `${55 + ((row + col) % 4) * 12}%` }} />
        </td>
      ))}
    </tr>
  ));
}

export function SkeletonCards({ count = 3 }) {
  return (
    <div className="flex flex-col gap-3" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="card flex flex-col gap-2 p-4">
          <div className="skeleton h-4 w-1/3" />
          <div className="skeleton h-3 w-2/3" />
        </div>
      ))}
    </div>
  );
}
