# StockPilot API

The Flask REST API behind StockPilot. It stores every business in one PostgreSQL database, keeps
each business's data apart, and exposes OpenAPI documentation at `/api/docs`.

## Requirements

- Python 3.13
- PostgreSQL 16

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Create the database user and the development and test databases:

```bash
psql -U postgres -c "CREATE USER stockpilot WITH PASSWORD 'stockpilot' CREATEDB;"
psql -U postgres -c "CREATE DATABASE stockpilot_dev OWNER stockpilot;"
psql -U postgres -c "CREATE DATABASE stockpilot_test OWNER stockpilot;"
```

Build the schema and load the demo data:

```bash
flask db upgrade
python seed.py
```

## Running

```bash
flask run
```

- Health check: http://localhost:5000/api/health
- Interactive API docs: http://localhost:5000/api/docs

Without `BREVO_API_KEY` or `MAIL_SERVER`, emails (confirmation links, sign-in codes, summaries) are
printed in the terminal instead of being sent.

## Demo data

`python seed.py` creates two businesses. Every account uses the password `ChangeMe123!`; the
data is for review only.

| Business | Join code | Accounts |
|---|---|---|
| StockPilot Demo Shop | `DEMO2026` | `admin@`, `procurement@`, `inventory@`, `sales@`, `employee@stockpilot.test`; `grace@stockpilot.test` is waiting for approval |
| Highland Café | `CAFE2026` | `owner@highlandcafe.test` (administrator), `till@highlandcafe.test` (sales) |

The Demo Shop has someone in every role, so its administrator only oversees. Highland Café has no
procurement or inventory staff, so its owner covers those jobs. Products have usual suppliers, and
Metro Wholesale is a trusted supplier. As `sales@`, selling 20 reams of A4 paper drafts an order
for procurement to confirm, while selling the last 4 bags of sugar sends an order to Metro at once.
The Demo Shop also has ten weeks of M-Pesa statement history with regular customers, weekly
stock payments, wages and withdrawals, so Insights shows a forecast straight away. Running
`python seed.py` again on a database that already has the Demo Shop only adds this history if it
is missing.

## Tests

```bash
pytest
ruff check .
ruff format --check .
```

`tests/test_permissions.py` calls every endpoint as every role, and a new endpoint fails the
suite until it is listed there. `tests/test_tenancy.py` repeats the calls against a second
business to prove nothing leaks between them.

`postman/StockPilot.postman_collection.json` walks through the main flows in 50 requests. Run it
against freshly seeded data with `EMAIL_VERIFICATION_REQUIRED=false`,
`STAFF_APPROVAL_REQUIRED=false` and `test.com` added to `LOGIN_CODE_EXEMPT_DOMAINS`, since it signs
up a new account of its own.

## How it works

### Businesses and accounts

Every record belongs to a business, and `app/tenancy.py` filters each query to the signed-in
user's business, so ids from another business are simply not found.

1. **Start a business:** `POST /api/auth/register-business` creates the business and its
   administrator, starts a 14-day trial and emails a confirmation link.
2. **Join a business:** staff register with the join code from Settings
   (`POST /api/auth/register`). They confirm their email and then wait until the administrator
   approves them and picks their role (`POST /api/users/<id>/approve`).
3. **Confirm the email:** the emailed link opens `/verify-email?token=…`, which calls
   `POST /api/auth/verify-email`. Links work once and expire after 24 hours.
4. **Sign in:** `POST /api/auth/login` checks the password and emails a 6-digit code;
   `POST /api/auth/login/verify` exchanges it for an access token (15 minutes) and a refresh
   token (7 days). Codes work once, last 5 minutes and allow 5 attempts. Addresses in
   `LOGIN_CODE_EXEMPT_DOMAINS` skip the code.
5. **Sign out:** `POST /api/auth/logout` revokes the session and every token made from it.
6. **Reset a password:** `POST /api/auth/forgot-password` emails a one-hour link and
   `POST /api/auth/reset-password` sets the new password and ends every session.

### Roles

Procurement, inventory and sales staff do the daily work; the administrator oversees it. While
nobody has been approved into a role yet, as in a new business run by its owner alone, the
administrator covers that role, and `GET /api/auth/me` lists the covered roles in `covers`.
Notifications meant for an empty role go to the administrator.

### Automation

- **Sales** lower stock, write the stock ledger and the audit log, number the receipt and record
  the cost at that moment for profit reports.
- **Low stock** alerts inventory and procurement. If the product has a usual supplier, it goes on
  a draft order for procurement to confirm, one draft per supplier. For a trusted supplier the
  order is placed and emailed at once. Products already on order are skipped. The quantity is the
  product's `reorder_quantity`, or enough to reach twice the reorder level.
- **Approved requests** for a product with a usual supplier become a purchase order in the same
  way.
- **Placing an order** emails it to the supplier when the supplier has an email address.
- **Receiving a delivery** raises stock, writes a goods received note, updates the order and sets
  the product's cost to the weighted average of the stock on hand and the delivery.
- **The evening summary** emails each administrator the day's sales, payment methods, best
  sellers, voids, low stock, open drafts and staff awaiting approval. The schedule in
  `.github/workflows/daily-summary.yml` calls `POST /api/tasks/daily-summary` at 20:00 East
  Africa Time; `flask send-daily-summary` does the same by hand.

### M-Pesa at the till

Each business connects its own Paybill or Buy Goods till under Settings. The passkey and API keys
are encrypted with Fernet before they are stored and are never returned by the API. A business
chooses one of four modes:

| Mode | Behaviour |
|---|---|
| `off` | M-Pesa sales are recorded by hand |
| `simulate` | Test mode: no prompt is sent and the till shows "Customer pays" and "Customer cancels" |
| `sandbox` | Real prompts from Safaricom's test environment |
| `live` | Real payments into the business's own account |

The attendant enters the customer's number and `POST /api/payments/mpesa` sends an M-Pesa Express
prompt. Safaricom reports the result to `/api/payments/mpesa/callback/<token>`, where the token is
derived from `SECRET_KEY`. A successful payment completes the sale with the M-Pesa receipt
number. If the callback never arrives, `GET /api/payments/mpesa/<id>` asks Safaricom directly
after 20 seconds. If the money arrives after the stock has sold out, the payment is kept and the
administrator and sales staff are told to resell or refund.

Sales money only ever goes to the business's own account. Without its own keys, a business runs
in test mode when the platform does, and with M-Pesa off otherwise.

### Subscriptions

Businesses pay StockPilot monthly by M-Pesa from the Billing page (`POST /api/billing/pay`), using
the platform's Paybill from the `MPESA_*` variables. Plans cover 1, 3, 6 or 12 months at
`SUBSCRIPTION_PRICE` a month, and a payment extends the subscription from the later of today, the
end of the trial and the current paid-up date.

When `SUBSCRIPTIONS_REQUIRED=true`, a business whose trial or subscription ended more than 7 days
ago becomes read-only: it can still sign in, read its data and pay, but any change answers 403
with `"reason": "subscription_ended"`.

### Platform owners

People whose email address is listed in `PLATFORM_OWNERS` run StockPilot itself. They sign in
with their normal account and get a Platform page that lists every business with its owner, staff
count, last sale and subscription status, every subscription payment, and the takings for the
month. From there they can add free months (for example after a payment made outside M-Pesa),
suspend or reactivate a business, and change the monthly price, which is stored in
`platform_settings` and overrides `SUBSCRIPTION_PRICE`. The page also shows whether StockPilot's
Paybill is connected; its keys stay in the server's environment and never pass through the app.
Every action is written to the affected business's audit log, and its administrators are told.

### Insights

`GET /api/insights` works from the business's own data and needs no outside service.

- **Takings** are completed sales plus statement money-in sorted as sales that isn't already a
  till sale, so a business that only imports statements still gets a forecast.
- **The forecast** (`app/insights.py`) learns how each weekday compares with an average day over
  the last 8 weeks, tracks the underlying level with exponential smoothing over the last 4, and
  multiplies the two back together for the next 14 days. The range covers about 80% of the past
  misses. Before showing it, the model is re-fitted without the last 14 days and scored on them,
  and the page shows that accuracy. It needs 14 days of history.
- **Stock**: products that will run out within a week at the last 30 days' pace, with an order
  that covers two weeks; products with no sales in 30 days, by money tied up; the five most
  profitable.
- **Customers** come from M-Pesa payments at the till and statement money-in sorted as sales,
  grouped by phone number or name. Regulars with three or more payments and none in 30 days are
  listed as gone quiet.
- **Cash**: the last 8 weeks in and out, and the next 30 days from the takings forecast plus the
  usual other income, less the usual spending and recorded expenses. Moving the owner's own money
  in and out (deposits and withdrawals) is left out.

### M-Pesa history

`POST /api/money/statement` takes the statement Safaricom emails (an encrypted PDF, read with
`pypdf` using the password from the same SMS) or a CSV export, and `POST /api/money/sms` takes
pasted confirmation messages. `app/statements.py` turns both into transactions: receipt, time,
direction, amount, balance and the other party. Failed or reversed rows are skipped, transaction
charges become their own rows, and a row already imported is never added twice. A Fuliza payment shows as two rows with one receipt (the overdraft coming in and the payment going out), and both are kept.

Each transaction gets a category from, in order, a rule the administrator taught it for that phone
number or name, the transaction type (an agent withdrawal, airtime, a Paybill payment), keywords
for utilities, and the business's supplier names. A receipt that matches an M-Pesa till sale is
linked to the sale. Changing a category with `remember` also changes earlier transactions from
the same sender and every future import. A whole import can be undone.

Statements contain customers' names and phone numbers. They are stored only in the business's own
records, the file itself is discarded once read, and undoing an import deletes its rows. A
business using this should tell customers how their payment details are used, as the Data
Protection Act, 2019 expects.

### Receipt scanning

A photo of a paper receipt becomes either an expense or a stock purchase. Out of the box the
photo is read in the browser with Tesseract (`tesseract.js`), so nothing is uploaded and nothing
is paid for; the text goes to `POST /api/receipts/text`, where `app/receipts.py` finds the shop,
date, receipt number, total, VAT and item lines. With `RECEIPT_AI_KEY` set, the photo is sent to
`POST /api/receipts/photo` instead and read by Claude, which copes far better with faded or
crumpled till slips. Either way the photo is not stored.

Item lines are matched to products by SKU or by name, and the shop to an existing supplier. The
person checks everything against the photo before saving. A stock purchase
(`POST /api/receipts/stock`) is recorded as a purchase already received: stock goes up, average
cost is updated, and a shop that isn't a supplier yet is added as one.

### M-Pesa messages from a phone

The administrator links a phone from the M-Pesa money page. `POST /api/phone/link` returns a
private address, `/api/phone/inbox/<token>`, shown once; only a SHA-256 hash of the token is
stored, and making a new link retires the old one. On an Android phone, the free, open-source
[SMS to URL Forwarder](https://f-droid.org/packages/tech.bogomolov.incomingsmsgateway/) app posts
each message from `MPESA` to that address as JSON (`{"from": "...", "text": "..."}`; form posts
and plain text also work). Messages from other senders, and texts that aren't transactions, are
ignored, and a receipt already imported is never added twice. Each day's messages collect in one
import that can be undone like any other.

### Alerts

The evening summary ends with a look ahead: expected sales for the next 7 days, products that will
run out within a week with a suggested order, and a warning when the next 30 days are likely to
leave the business short of cash.

With WhatsApp alerts turned on in Settings, the same low-stock warnings (as stock crosses its
reorder level) and the evening cash warning go to the owner's WhatsApp, through Meta's WhatsApp
Cloud API. Business-started messages must use an approved template, so the API needs one:

1. In [Meta for Developers](https://developers.facebook.com/), create a Business app and add
   WhatsApp. Note the **phone number ID** of the sending number.
2. In Business Settings, create a system user with the `whatsapp_business_messaging` permission
   and generate a permanent **access token**.
3. In WhatsApp Manager, create a **Utility** template named `stockpilot_alert` in English with the
   body `StockPilot alert for {{1}}: {{2}}` and wait for approval.
4. Set `WHATSAPP_TOKEN` and `WHATSAPP_PHONE_ID`.

Without those two variables, alerts are written to the log instead of being sent. Meta charges
per delivered template message.

### Loan-readiness report

`GET /api/reports/performance.pdf?months=6` (3, 6 or 12) builds a one-page PDF with ReportLab
for the last complete months: average monthly sales, the best month, months with more coming in
than going out, the sales trend, days with sales, paying and regular customers, a monthly chart and
table (sales, other money in, spending, in minus out, closing M-Pesa balance), loans received and
repaid, and stock at cost. It says how the figures were prepared and that they are the business's
own, unaudited records.

## API reference

Every endpoint is limited to the caller's business. Lists accept `?page=1&per_page=20` (at most
100). The full schema is in the interactive docs at `/api/docs`.

| Endpoint | Who |
|---|---|
| `GET /api/business` · `PUT` · `POST /join-code` | everyone reads; the administrator edits and sees the join code |
| `GET`/`PUT /api/business/mpesa` | administrator: the business's own Paybill or till |
| `GET /api/billing` · `POST /pay` · `GET /payments/<id>` · `POST /payments/<id>/simulate` | administrator |
| `/api/users/` · `PUT /<id>/role` · `POST /<id>/approve`, `/decline`, `/deactivate`, `/reactivate` | administrator, never on themselves |
| `GET /api/audit/` | administrator |
| `GET /api/dashboard/pulse` | everyone: the figures for their role |
| `/api/categories/` | everyone reads; inventory changes |
| `/api/products/` · `/<id>/retire`, `/restore`, `/photo` · `GET /<id>/timeline` | everyone reads; inventory changes; procurement can create while ordering; the administrator reads timelines |
| `/api/suppliers/` | administrator, procurement and inventory read; procurement changes, including `trusted` |
| `/api/requests/` · `/<id>/approve`, `/reject`, `/fulfil`, `/cancel` · `GET /<id>/timeline` | everyone requests; procurement decides, never on its own requests |
| `/api/purchases/` · `PUT /<id>` · `POST /<id>/confirm`, `/cancel` | procurement; the administrator and inventory read |
| `POST /api/purchases/<id>/receive` | inventory, in full or in parts |
| `/api/sales/` · `POST /<id>/void` | sales sell and void their own sales the same day; the administrator sees all |
| `GET /api/payments/mpesa/config` · `POST /api/payments/mpesa` · `GET /<id>` · `POST /<id>/simulate` | sales; the administrator follows any payment |
| `GET /api/stock/movements` · `.csv` · `POST /api/stock/adjustments` | the administrator and inventory read; inventory adjusts |
| `/api/assets/` · `/<id>/assign`, `/return`, `/retire`, `/photo` · `/api/asset-categories/` | inventory manages; others see what they hold |
| `/api/repairs/` · `PUT /<id>/status` | anyone reports for assets they hold; inventory moves repairs along |
| `GET /api/reports/summary` · `/api/expenses/` | administrator |
| `GET /api/insights` | administrator |
| `GET /api/receipts/reader` · `POST /text`, `/photo` | administrator, procurement, inventory |
| `POST /api/receipts/stock` | procurement, inventory |
| `GET`/`POST`/`DELETE /api/phone/link` | administrator |
| `POST /api/phone/inbox/<token>` | anyone with the private link (the phone) |
| `GET`/`PUT /api/business/whatsapp` · `POST /whatsapp/test` | administrator |
| `GET /api/reports/performance.pdf` | administrator |
| `GET /api/money/categories`, `/imports`, `/transactions`, `/totals` · `POST /statement`, `/sms` · `DELETE /imports/<id>` · `PUT /transactions/<id>` | administrator |
| `/api/notifications/` · `POST /<id>/read`, `/read-all` | everyone, their own |
| `/api/auth/register`, `/register-business`, `/login`, `/login/verify`, `/login/resend`, `/verify-email`, `/resend-verification`, `/refresh`, `/forgot-password`, `/reset-password` · `GET /api/images/<id>` · `GET /api/health` | public |
| `GET`/`PUT /api/auth/me` · `POST /api/auth/password`, `/logout` | the signed-in user |
| `POST /api/payments/mpesa/callback/<token>` · `POST /api/tasks/daily-summary` | Safaricom · the scheduler (`X-Task-Token` header) |
| `GET /api/platform/overview`, `/businesses`, `/payments` · `PUT /price` · `POST /businesses/<id>/extend`, `/suspend`, `/reactivate` | platform owners only; everyone else gets 404 |

Errors share one shape:

```json
{"error": {"code": 422, "message": "Some fields are invalid.", "details": {"email": ["…"]}}}
```

401 means not signed in, 403 not allowed (with a `reason` such as `email_unverified`,
`awaiting_approval` or `subscription_ended` where one applies), 404 not found in this business,
409 a duplicate or a change the record's state does not allow, and 422 invalid fields.

## Configuration

`.env.example` lists every variable with a short description. The ones that matter most:

| Variable | Purpose |
|---|---|
| `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY` | Required in production |
| `CORS_ORIGINS`, `FRONTEND_URL` | The web app's address, for browser access and for links in emails |
| `BREVO_API_KEY` or `MAIL_SERVER`, `MAIL_FROM` | Email delivery; Brevo's HTTPS API works where SMTP ports are blocked |
| `MPESA_MODE`, `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`, `MPESA_SHORTCODE`, `MPESA_PASSKEY` | StockPilot's own Paybill, used for subscriptions |
| `SUBSCRIPTIONS_REQUIRED`, `SUBSCRIPTION_PRICE` | Whether lapsed businesses become read-only, and the default monthly price in KES |
| `PLATFORM_OWNERS` | Comma-separated email addresses that can open the Platform page |
| `DATA_KEY` | Encrypts each business's M-Pesa keys; defaults to `SECRET_KEY`. Changing it means businesses re-enter their keys |
| `TASK_TOKEN` | Shared secret for the evening summary schedule |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_TEMPLATE`, `WHATSAPP_LANGUAGE` | Optional. WhatsApp Cloud API credentials and the approved template (`stockpilot_alert`, `en` by default) |
| `RECEIPT_AI_KEY`, `RECEIPT_AI_MODEL` | Optional. An Anthropic API key turns on online receipt reading; without it receipts are read on the user's device |
| `EMAIL_VERIFICATION_REQUIRED`, `LOGIN_CODE_REQUIRED`, `STAFF_APPROVAL_REQUIRED` | Security checks, on by default |

## Deployment

`render.yaml` is a Render Blueprint for the API, a PostgreSQL database and a Key Value store for
rate limiting. `start.sh` applies migrations, loads the demo data when `SEED_DEMO=true` (existing
data is never duplicated) and starts Gunicorn. `Procfile` runs the same script on other hosts.

With `APP_ENV=production` the API refuses to start without real secrets and addresses, sends HSTS
and trusts the proxy's forwarded address and scheme.

Points to plan for on Render's free plan:

- Free web services cannot use SMTP, so set `BREVO_API_KEY` for email.
- The service sleeps after 15 minutes without traffic. M-Pesa expects its callback to answer
  within seconds, so `sandbox` and `live` payments need a paid instance.
- A free database expires 30 days after it is created.

For the evening summary, add the repository secrets `STOCKPILOT_API_URL` and `TASK_TOKEN` (the
same value as on Render) under GitHub's Actions settings.

## Changing the database

Edit the models in `app/models/`, then generate and apply a migration:

```bash
flask db migrate -m "describe the change"
flask db upgrade
```
