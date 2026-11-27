# Changes in this round

## M-Pesa at the till

- Choose M-Pesa, type the customer's number and press **Send M-Pesa request**. The customer gets
  the prompt on their phone; once Safaricom confirms, the sale completes by itself with the M-Pesa
  code on the receipt. No "mark as paid" click.
- A cancelled prompt, a low balance, a wrong PIN or no answer is explained at the till and the cart
  is kept to try again or take cash.
- If Safaricom's confirmation is lost, the till asks Safaricom after 20 seconds.
- If money arrives for stock that has just run out, the payment is kept and the Administrator and
  sales staff are told to sell again or refund.
- Test mode (`MPESA_MODE=simulate`) shows "Customer pays" and "Customer cancels" buttons instead of
  sending a real prompt, so the flow can be shown without Safaricom keys.

## Evening summary

- Every Administrator gets one email a day: sales and how they were paid, best sellers, voids, low
  stock, draft orders and staff waiting for approval. On by default; Settings can turn it off.
- Sent by a scheduled GitHub Action at 20:00 Nairobi time, or `flask send-daily-summary`.

## Files

Backend: `app/mpesa.py`, `app/summary.py`, `app/models/payments.py`, `app/resources/payments.py`,
`app/resources/tasks.py` (all new), `app/resources/sales.py` (sale creation shared with M-Pesa),
migration `124577034daa_mpesa_payments_and_daily_summary.py`. Tests: `tests/test_mpesa.py`,
`tests/test_summary.py`.

Frontend: `features/sales/PosPage.jsx`, `features/sales/Receipt.jsx`,
`features/settings/BusinessSettings.jsx`. Tests: `test/mpesa.test.jsx`.

Other: `.github/workflows/daily-summary.yml`, `render.yaml` (`TASK_TOKEN`, `MPESA_MODE`).

---

# Earlier round

## The Administrator oversees

- Day-to-day work belongs to the roles that do it: Sales sell and void their own sales,
  Inventory receive deliveries, adjust stock and manage products, assets and repairs,
  Procurement order, manage suppliers and decide requests.
- The Administrator sees all of it (sales, stock ledger, purchases, assets, repairs, reports,
  audit log) and is told when a sale is voided, but does not do the work.
- While nobody holds a role, the Administrator covers it, so a new shop with only its owner still
  works. Once someone is approved into that role, the job is theirs.

## New staff wait for approval

- After joining with the code, a person cannot sign in until the Administrator approves them and
  chooses their role. The Administrator gets a notification and an email.
- Users page: a "Waiting for your approval" list with a role picker, Approve and Decline.
- Everyone who already had an account is approved by the migration.

## Stock that updates itself

- Receiving a delivery sets the product's cost price to the weighted average of the stock on hand
  and the delivery, and records the change in the audit log.
- Products have a usual supplier and an optional "order this many" amount.
- When stock falls to the reorder level, the product is added to a draft order for its usual
  supplier (one draft per supplier), marked "Auto: low stock", for Procurement to check and confirm.
- Approving a request for a product with a usual supplier drafts its purchase order.
- Procurement can create a missing product from inside a purchase order.

## Files

Backend: `app/auth.py`, `app/notify.py`, `app/reorder.py` (new), `app/resources/*` (permissions),
`app/resources/users.py` (approve, decline), `app/models/*`, migration
`e5f1e5474e06_staff_approval_and_stock_automation.py`, `seed.py`.
Tests: `tests/test_oversight.py` (new), `tests/test_permissions.py` and others updated.

Frontend: `auth/AuthContext.jsx` (`canDo`), `auth/RequireAuth.jsx`, `components/Layout.jsx`,
`features/users/UsersPage.jsx`, `features/products/ProductForm.jsx`,
`features/purchases/PurchaseForm.jsx`, `features/purchases/PurchasesPage.jsx`, and the pages whose
buttons now follow the job rather than the title.
