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
| `/api/notifications/` · `POST /<id>/read`, `/read-all` | everyone, their own |
| `/api/auth/register`, `/register-business`, `/login`, `/login/verify`, `/login/resend`, `/verify-email`, `/resend-verification`, `/refresh`, `/forgot-password`, `/reset-password` · `GET /api/images/<id>` · `GET /api/health` | public |
| `GET`/`PUT /api/auth/me` · `POST /api/auth/password`, `/logout` | the signed-in user |
| `POST /api/payments/mpesa/callback/<token>` · `POST /api/tasks/daily-summary` | Safaricom · the scheduler (`X-Task-Token` header) |

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
| `SUBSCRIPTIONS_REQUIRED`, `SUBSCRIPTION_PRICE` | Whether lapsed businesses become read-only, and the monthly price in KES |
| `DATA_KEY` | Encrypts each business's M-Pesa keys; defaults to `SECRET_KEY`. Changing it means businesses re-enter their keys |
| `TASK_TOKEN` | Shared secret for the evening summary schedule |
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
