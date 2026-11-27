# StockPilot — Backend (Flask API)

## You need

- Python
- PostgreSQL 16 running on your computer

## Set up (first time)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      
pip install -r requirements.txt
cp .env.example .env       
```

Create the database user and two databases (once per computer):

```bash
psql -U postgres -c "CREATE USER stockpilot WITH PASSWORD 'stockpilot' CREATEDB;"
psql -U postgres -c "CREATE DATABASE stockpilot_dev OWNER stockpilot;"
psql -U postgres -c "CREATE DATABASE stockpilot_test OWNER stockpilot;"
```

Create the tables and add demo data:

```bash
flask db upgrade
python seed.py
```

Upgrading a database from before multi-business support? `flask db upgrade` keeps your data:
everything is moved into one business called "My Business" (rename it in Settings), and new
columns are filled in from what is already there. Back the database up first; this step cannot
be undone automatically.

## Run

```bash
flask run
```

- Health check: http://localhost:5000/api/health
- Swagger docs: http://localhost:5000/api/docs

## Businesses and sign-in

StockPilot serves many businesses from one database. Every record belongs to one business and
the API filters every query to the signed-in user's business (`app/tenancy.py`), so one shop can
never see or change another's data, even by guessing ids.

1. **Start a business:** `POST /api/auth/register-business` with
   `{"business_name", "full_name", "email", "password"}`. The person becomes its Administrator.
   The answer is `{"verification_required": true, "message"}` and a confirmation link is emailed.
2. **Join a business:** the Administrator shares the join code from `GET /api/business` (or the
   invite link `/register?code=…` from Settings). Staff call `POST /api/auth/register` with
   `{"full_name", "email", "password", "join_code"}` and start as Employee.
3. **Confirm the email (US-02):** the link opens `/verify-email?token=…` in the app, which calls
   `POST /api/auth/verify-email` with `{"token"}`. Links work once and last 24 hours;
   `POST /api/auth/resend-verification` with `{"email"}` sends a new one. Until then, sign-in
   answers 403 with `"reason": "email_unverified"`. Accounts that existed before this change
   count as confirmed.
4. **Sign in (US-03):** `POST /api/auth/login` with `{"email", "password"}`. When the password is
   right the server emails a 6-digit code and answers `{"code_required": true, "challenge_id",
   "email_hint", "expires_in": 300, "resend_after": 60}`. `POST /api/auth/login/verify` with
   `{"challenge_id", "code"}` gives the tokens. A code works once, lasts 5 minutes and allows 5
   tries; `POST /api/auth/login/resend` with `{"challenge_id"}` sends a new one (after 60 seconds,
   at most 5 times). Emails in `LOGIN_CODE_EXEMPT_DOMAINS` (the demo accounts) skip the code.
   The tokens: `access_token` (15 minutes) and `refresh_token` (7 days). Send `Authorization: Bearer <access_token>`; in Swagger click
   **Authorize**. `POST /api/auth/refresh` with the refresh token gives a new access token.
5. `POST /api/auth/logout` (either token) ends that session on the server: the refresh token and
   every access token made from it stop working.
6. **New staff wait for approval:** after joining (and confirming their email) a person cannot
   sign in until the Administrator approves them and chooses their role (`POST
   /api/users/<id>/approve`). Until then sign-in answers 403 with `"reason": "awaiting_approval"`.
   The Administrator is notified and emailed. `STAFF_APPROVAL_REQUIRED=false` turns this off.
7. Forgotten password: `POST /api/auth/forgot-password` emails a one-time link (1 hour);
   `POST /api/auth/reset-password` with `{"token", "password"}` sets it and signs the person out
   everywhere (it also confirms the email, since the link proved the person reads it).
   Without `BREVO_API_KEY` or `MAIL_SERVER`, emails are printed in the terminal.

Switches (all on by default, off in the test config): `EMAIL_VERIFICATION_REQUIRED=false` and
`LOGIN_CODE_REQUIRED=false` turn the two checks off, for example on a laptop with no email.

Demo data (`python seed.py`), password `ChangeMe123!` for everyone (review only):

| Business | Join code | Accounts |
|---|---|---|
| StockPilot Demo Shop | `DEMO2026` | `admin@`, `procurement@`, `inventory@`, `sales@`, `employee@stockpilot.test` |
| Highland Café | `CAFE2026` | `owner@highlandcafe.test` (admin), `till@highlandcafe.test` (sales) |

Sign in as each owner to see that the two businesses never see each other's products or sales.
The Demo Shop has someone in every role, so its admin only oversees; `grace@stockpilot.test` is
waiting for approval on its Users page. Highland Café has no Procurement or Inventory staff, so its
owner does those jobs. The demo products have usual suppliers: sell 20 reams of A4 paper as `sales@`
(30 in stock, reorder level 10) and a draft order appears for `procurement@` to confirm.

## Test

```bash
pytest              
ruff check .          
ruff format .          
```

API tests in Postman: start the backend on a freshly seeded database (`python seed.py`), import
`postman/StockPilot.postman_collection.json` and run the collection (50 requests). The
`joinCode` variable is the demo shop's code.

`tests/test_permissions.py` checks every endpoint for every role (a new endpoint fails the build
until it is listed), and `tests/test_tenancy.py` checks every endpoint against a second business.

## What happens by itself

- **A sale** lowers stock, writes the stock ledger and audit log, numbers the receipt and keeps the
  cost at that moment for profit reports.
- **Stock falling to its reorder level** alerts Inventory and Procurement. If the product has a
  usual supplier (`default_supplier_id`), it is added to a draft purchase order for that supplier
  (one open draft per supplier, `source: "low_stock"`), unless it is already on order. The amount
  is the product's `reorder_quantity`, or enough to reach twice the reorder level.
- **Approving a request** for a product with a usual supplier drafts a purchase order for it
  (`source: "request"`), linked to the request.
- **Receiving a delivery** raises stock, writes a GRN, updates the order's status and resets the
  product's cost price to the weighted average of the stock on hand and the delivery.
- Nothing is sent to a supplier without a person: drafts wait for Procurement to confirm them.
- **M-Pesa at the till:** the attendant enters the customer's number and StockPilot sends an
  M-Pesa prompt to their phone (Daraja STK Push). When Safaricom confirms the payment, the sale is
  completed by itself with the M-Pesa receipt code on it. If Safaricom's message is lost (a server
  asleep, say), the till asks Safaricom for the result after 20 seconds. If the money arrives but
  the stock has gone meanwhile, the payment is kept and the Administrator and sales staff are told.
- **Evening summary:** every Administrator gets one email a day with sales, payment methods, best
  sellers, voids, low stock, draft orders and staff waiting for approval. Businesses can turn it
  off in Settings. `.github/workflows/daily-summary.yml` calls `POST /api/tasks/daily-summary` at
  20:00 Nairobi time (17:00 UTC); `flask send-daily-summary` does the same from a terminal.

### M-Pesa settings

| Variable | Meaning |
|---|---|
| `MPESA_MODE` | `off` (record M-Pesa by hand), `simulate` (test mode: no real prompt, the till shows "Customer pays / cancels" buttons), `sandbox` (Safaricom's test system), `live`. Defaults to `simulate` locally and `off` in production |
| `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET` | from your app on developer.safaricom.co.ke (sandbox or live). Never commit them |
| `MPESA_SHORTCODE`, `MPESA_PASSKEY` | default to Safaricom's public sandbox values (174379); your own Paybill or till store number and passkey when live |
| `MPESA_TRANSACTION_TYPE`, `MPESA_PARTY_B` | `CustomerPayBillOnline` for a Paybill; `CustomerBuyGoodsOnline` with `MPESA_PARTY_B` set to the till number for Buy Goods |
| `MPESA_CALLBACK_BASE` | the API's public address, if it differs from the one requests arrive on |

Safaricom posts results to `/api/payments/mpesa/callback/<token>`; the token is derived from
`SECRET_KEY`, so the address cannot be guessed. Safaricom expects that address to answer within a few
seconds, so `sandbox` and `live` need an API that does not sleep (a paid Render instance).
Today one set of M-Pesa settings serves the whole installation; each business having its own
Paybill is a later step.

## Endpoints and who may use them

Everything below is limited to the caller's own business. Lists take `?page=1&per_page=20`
(max 100). No token → 401; wrong role → 403. Full details in Swagger at `/api/docs`.

| Endpoint | Who |
|---|---|
| `GET /api/business` · `PUT` · `POST /api/business/join-code` | everyone reads (join code admin only) · admin changes name, time zone, currency, VAT, receipt details, join code |
| `/api/users/` (filters `search`, `role`, `active`, `pending`) · `PUT /<id>/role` · `POST /<id>/deactivate`, `/reactivate` | admin (never on themselves); every change goes to the audit log |
| `POST /api/users/<id>/approve` `{role}` · `POST /<id>/decline` | admin: lets a new joiner in with a role, or removes the request |
| `GET /api/audit/` (filters `entity_type`, `entity_id`, `action`) | admin |
| `GET /api/dashboard/pulse` | everyone: the tiles for their role, in one call |
| `/api/categories/` (filter `active`) | everyone reads · inventory changes; a category with products is deactivated, not deleted |
| `/api/products/` (filters `search`, `category_id`, `low_stock`, `in_stock`, `status=active/retired/all`) | everyone reads · inventory and procurement create (procurement while ordering) · inventory changes |
| `POST /api/products/<id>/retire`, `/restore` · `POST`/`DELETE /<id>/photo` · `GET /<id>/timeline` | inventory (admin reads the timeline). Photos: JPEG/PNG/WebP up to 5 MB, resized to 1200 px. Quantity changes only through adjustments |
| `/api/suppliers/` (filters `search` incl. `SUP-001`, `active`) | admin, procurement, inventory read · procurement changes |
| `/api/requests/` (filters `status`, `tab=active/completed`, `urgency`, `decided_today`, `sort=urgency`, `mine`, `search`) | admin and procurement see all; others their own |
| `POST /api/requests/<id>/approve`, `/reject` | procurement, never on their own request; reject needs a `comment` |
| `POST /api/requests/<id>/cancel` · `/fulfil` · `GET /<id>/timeline` | requester cancels while pending · procurement marks approved requests fulfilled |
| `/api/purchases/` (filters `status` incl. `awaiting`, `supplier_id`, `search`) · `PUT /<id>` (drafts) · `POST /<id>/confirm`, `/cancel` (`reason`) | procurement orders; admin and inventory read |
| `POST /api/purchases/<id>/receive` `{lines: [{item_id, quantity}], idempotency_key, note}` | inventory. Partial deliveries allowed; each gets a GRN; the same key never counts twice |
| `/api/sales/` (filters `day`, `date_from`, `date_to`, `payment_method`, `status`, `attendant_id`, `search`) · `POST` with `idempotency_key` | sales sell and see their own · admin sees all |
| `POST /api/sales/<id>/void` (`reason`, same day) | sales, on their own sales; the admin is notified |
| `GET /api/stock/movements` (filters `product_id`, `type`, `date_from`, `date_to`) · `GET /api/stock/movements.csv` | admin, inventory |
| `POST /api/stock/adjustments` | inventory |
| `/api/assets/` (filters `search` incl. barcode, `status`, `category_id`, `overdue`, `mine`) · `GET /lookup/<barcode or code>` | admin, inventory see all; others what they hold |
| `POST /api/assets/<id>/assign` `{user_id, condition, expected_return}` · `/return` `{condition, notes}` · `/retire` · `/photo` · `GET /assignments`, `/timeline` | inventory (history readable by admin and the holder) |
| `/api/asset-categories/` | everyone reads · inventory changes |
| `/api/repairs/` (filters `status` incl. `open`, `asset_id`) · `PUT /<id>/status` `{status, resolution, cost}` | anyone reports for assets they hold · admin follows all · inventory moves them: submitted → in_progress → done, or submitted → rejected |
| `GET /api/reports/summary?days=7` or `?date_from=&date_to=` | admin: sales, VAT, gross profit (cost at time of sale), expenses, net profit, by day / payment / attendant, best sellers, low stock |
| `/api/expenses/` (filters `date_from`, `date_to`, `category`) | admin |
| `/api/notifications/` · `POST /<id>/read` · `POST /read-all` | everyone, their own (each has a `link` to open the record) |
| `GET /api/payments/mpesa/config` | everyone: whether the till sends M-Pesa prompts |
| `POST /api/payments/mpesa` `{phone, items, idempotency_key}` · `GET /<id>` · `POST /<id>/simulate` `{outcome}` | sales start and follow a prompt (admin can follow any); simulate only in test mode |
| `POST /api/payments/mpesa/callback/<token>` · `POST /api/tasks/daily-summary` (header `X-Task-Token`) | Safaricom · the scheduler |
| `/api/auth/register-business`, `/register`, `/login`, `/login/verify`, `/login/resend`, `/verify-email`, `/resend-verification`, `/refresh`, `/forgot-password`, `/reset-password`, `GET /api/images/<id>`, `/api/health` | public |

**The Administrator oversees.** Day-to-day jobs belong to Procurement, Inventory and Sales. While
nobody holds one of those roles (a new business with only its owner, say), the Administrator can do
that job; once someone is approved into the role, it is theirs. `GET /api/auth/me` lists the jobs
the Administrator is covering in `covers`. Notices meant for an empty role go to the Administrator.

Error responses always look like `{"error": {"code": 422, "message": "...", "details": {...}}}`:
422 invalid fields · 400 unknown linked record or bad JSON · 401 not signed in · 403 wrong role ·
404 not found · 409 duplicate or not allowed in the current state · 405 wrong method.

The database design is in [`../docs/ERD.md`](../docs/ERD.md).

## Deploy

The repository has a Render Blueprint (`../render.yaml`) set to Render's **free** plan: the API,
a PostgreSQL database and a small Key Value (Redis) for the rate limit. The free plan has no shell
and no pre-deploy step, so `start.sh` does everything on each start: `flask db upgrade`, then
`python seed.py` when `SEED_DEMO=true` (the seed skips data that is already there), then
`gunicorn wsgi:app`. `Procfile` runs the same script on Heroku-style hosts.

Render's free services cannot send email over SMTP (ports 25, 465 and 587 are blocked), so
production email goes through Brevo's HTTPS API: set `BREVO_API_KEY` and `MAIL_FROM` (a sender
address you verified in Brevo). Without `BREVO_API_KEY`, `MAIL_SERVER` (SMTP) is used if set.

Limits of the free plan: the API sleeps after 15 minutes without traffic (the next request takes
up to a minute), and the free database expires 30 days after it is created. Upgrade the database
before then, or export it with `pg_dump` and make a new one.

With `APP_ENV=production` the API refuses to start without real `SECRET_KEY`, `JWT_SECRET_KEY`,
`DATABASE_URL`, `CORS_ORIGINS` and `FRONTEND_URL`, sends HSTS and trusts the proxy's client IP.
Set `SEED_DEMO=false` once real businesses use it.

## Changed a model?

```bash
flask db migrate -m "describe the change"
flask db upgrade
```

