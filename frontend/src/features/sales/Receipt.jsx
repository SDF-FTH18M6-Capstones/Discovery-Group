import Icon from "../../components/Icon";
import { PAYMENT_LABELS, dateTime, money } from "../../format";

export default function Receipt({ sale, onClose, children }) {
  return (
    <div>
      <article
        aria-label={`Receipt ${sale.receipt_number}`}
        className="print-area perforated mb-2 flex flex-col gap-4 rounded-t-xl bg-surface px-6 pt-6 pb-5 font-mono text-[13px] shadow-[var(--sp-shadow-lg)] ring-1 ring-line"
      >
        <header className="flex flex-col items-center gap-1 text-center">
          <span className="font-display text-lg font-bold">StockPilot Demo Shop</span>
          <span className="text-muted">Receipt {sale.receipt_number}</span>
          <span className="text-muted">{dateTime(sale.created_at)}</span>
        </header>
        <table className="w-full">
          <thead className="sr-only">
            <tr>
              <th>Item</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {sale.items.map((line) => (
              <tr
                key={line.product_id}
                className="border-t border-dashed border-line-strong align-top"
              >
                <td className="py-2">
                  {line.product_name}
                  <span className="block text-xs text-muted">
                    {line.quantity} × {money(line.unit_price)}
                  </span>
                </td>
                <td className="py-2 text-right">{money(line.line_total)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-ink text-base font-bold">
              <td className="pt-3">Total</td>
              <td className="pt-3 text-right" data-testid="receipt-total">
                {money(sale.total)}
              </td>
            </tr>
          </tfoot>
        </table>
        <p className="text-center text-muted">
          Paid by {PAYMENT_LABELS[sale.payment_method] || sale.payment_method}. Served by{" "}
          {sale.attendant_name}.
        </p>
        <p className="text-center">Thank you</p>
        <div className="flex flex-wrap justify-center gap-2 border-t border-dashed border-line-strong pt-4 font-sans print:hidden">
          <button type="button" onClick={() => window.print()} className="btn-secondary">
            <Icon name="printer" size={16} /> Print
          </button>
          {children}
          {onClose && (
            <button type="button" onClick={onClose} className="btn-secondary">
              Close
            </button>
          )}
        </div>
      </article>
    </div>
  );
}
