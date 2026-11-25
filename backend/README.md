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
6. Forgotten password: `POST /api/auth/forgot-password` emails a one-time link (1 hour);
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

## Endpoints and who may use them

Everything below is limited to the caller's own business. Lists take `?page=1&per_page=20`
(max 100). No token → 401; wrong role → 403. Full details in Swagger at `/api/docs`.

| Endpoint | Who |
|---|---|
| `GET /api/business` · `PUT` · `POST /api/business/join-code` | everyone reads (join code admin only) · admin changes name, time zone, currency, VAT, receipt details, join code |
| `/api/users/` (filters `search`, `role`, `active`) · `PUT /<id>/role` · `POST /<id>/deactivate`, `/reactivate` | admin (never on themselves); every change goes to the audit log |
| `GET /api/audit/` (filters `entity_type`, `entity_id`, `action`) | admin |
| `GET /api/dashboard/pulse` | everyone: the tiles for their role, in one call |
| `/api/categories/` (filter `active`) | everyone reads · admin, inventory change; a category with products is deactivated, not deleted |
| `/api/products/` (filters `search`, `category_id`, `low_stock`, `in_stock`, `status=active/retired/all`) | everyone reads · admin, inventory change |
| `POST /api/products/<id>/retire`, `/restore` · `POST`/`DELETE /<id>/photo` · `GET /<id>/timeline` | admin, inventory. Photos: JPEG/PNG/WebP up to 5 MB, resized to 1200 px. Quantity changes only through adjustments |
| `/api/suppliers/` (filters `search` incl. `SUP-001`, `active`) | admin, procurement |
| `/api/requests/` (filters `status`, `tab=active/completed`, `urgency`, `decided_today`, `sort=urgency`, `mine`, `search`) | admin and procurement see all; others their own |
| `POST /api/requests/<id>/approve`, `/reject` | procurement, never on their own request; reject needs a `comment` |
| `POST /api/requests/<id>/cancel` · `/fulfil` · `GET /<id>/timeline` | requester cancels while pending · admin, procurement mark approved requests fulfilled |
| `/api/purchases/` (filters `status` incl. `awaiting`, `supplier_id`, `search`) · `PUT /<id>` (drafts) · `POST /<id>/confirm`, `/cancel` (`reason`) | admin, procurement order; inventory reads |
| `POST /api/purchases/<id>/receive` `{lines: [{item_id, quantity}], idempotency_key, note}` | admin, inventory. Partial deliveries allowed; each gets a GRN; the same key never counts twice |
| `/api/sales/` (filters `day`, `date_from`, `date_to`, `payment_method`, `status`, `attendant_id`, `search`) · `POST` with `idempotency_key` | admin (all), sales (own) |
| `POST /api/sales/<id>/void` (`reason`, same day) | admin |
| `GET /api/stock/movements` (filters `product_id`, `type`, `date_from`, `date_to`) · `GET /api/stock/movements.csv` · `POST /api/stock/adjustments` | admin, inventory |
| `/api/assets/` (filters `search` incl. barcode, `status`, `category_id`, `overdue`, `mine`) · `GET /lookup/<barcode or code>` | admin, inventory see all; others what they hold |
| `POST /api/assets/<id>/assign` `{user_id, condition, expected_return}` · `/return` `{condition, notes}` · `/retire` · `/photo` · `GET /assignments`, `/timeline` | admin, inventory (history readable by the holder) |
| `/api/asset-categories/` | everyone reads · admin, inventory change |
| `/api/repairs/` (filters `status` incl. `open`, `asset_id`) · `PUT /<id>/status` `{status, resolution, cost}` | anyone reports for assets they hold · admin, inventory move them: submitted → in_progress → done, or submitted → rejected |
| `GET /api/reports/summary?days=7` or `?date_from=&date_to=` | admin: sales, VAT, gross profit (cost at time of sale), expenses, net profit, by day / payment / attendant, best sellers, low stock |
| `/api/expenses/` (filters `date_from`, `date_to`, `category`) | admin |
| `/api/notifications/` · `POST /<id>/read` · `POST /read-all` | everyone, their own (each has a `link` to open the record) |
| `/api/auth/register-business`, `/register`, `/login`, `/login/verify`, `/login/resend`, `/verify-email`, `/resend-verification`, `/refresh`, `/forgot-password`, `/reset-password`, `GET /api/images/<id>`, `/api/health` | public |

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

