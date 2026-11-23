import { useBusiness } from "../../auth/useBusiness";
import Icon from "../../components/Icon";
import { PAYMENT_LABELS, dateTime, money } from "../../format";

// US-27: business name, receipt number, date, attendant, lines, VAT, total and payment.
export default function Receipt({ sale, onClose, children }) {
  const business = useBusiness();
  const voided = sale.status === "voided";
  return (
    <div>
      <article
        aria-label={`Receipt ${sale.receipt_number}`}
        className="print-area perforated mb-2 flex flex-col gap-4 rounded-t-xl bg-surface px-6 pt-6 pb-5 font-mono text-[13px] shadow-[var(--sp-shadow-lg)] ring-1 ring-line"
      >
        <header className="flex flex-col items-center gap-1 text-center">
          <span className="font-display text-lg font-bold">{business?.name || "StockPilot"}</span>
          {business?.address && <span className="text-muted">{business.address}</span>}
          {business?.phone && <span className="text-muted">Tel {business.phone}</span>}
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
            {Number(sale.vat_rate) > 0 && (
              <>
                <tr className="border-t border-dashed border-line-strong text-muted">
                  <td className="pt-2">Before VAT</td>
                  <td className="pt-2 text-right">{money(sale.net_amount)}</td>
                </tr>
                <tr className="text-muted">
                  <td className="pb-2">VAT {Number(sale.vat_rate)}% (included)</td>
                  <td className="pb-2 text-right" data-testid="receipt-vat">
                    {money(sale.vat_amount)}
                  </td>
                </tr>
              </>
            )}
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
        {voided && (
          <p className="rounded-lg border-2 border-danger p-2 text-center font-bold text-danger">
            VOIDED{sale.void_reason ? `: ${sale.void_reason}` : ""}
          </p>
        )}
        <p className="text-center">{business?.receipt_footer || "Thank you"}</p>
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
