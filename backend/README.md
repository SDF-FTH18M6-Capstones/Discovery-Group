# StockPilot — Backend (Flask API)

## You need

- Python
- PostgreSQL 16 running on your computer

## Set up (first time)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
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
   `{"business_name", "full_name", "email", "password"}`. The person becomes its Administrator
   and is signed in (tokens in the answer).
2. **Join a business:** the Administrator shares the join code from `GET /api/business` (or the
   invite link `/register?code=…` from Settings). Staff call `POST /api/auth/register` with
   `{"full_name", "email", "password", "join_code"}` and start as Employee.
3. `POST /api/auth/login` with `{"email", "password"}` gives `access_token` (15 minutes) and
   `refresh_token` (7 days). Send `Authorization: Bearer <access_token>`; in Swagger click
   **Authorize**. `POST /api/auth/refresh` with the refresh token gives a new access token.
4. `POST /api/auth/logout` (either token) ends that session on the server: the refresh token and
   every access token made from it stop working.
5. Forgotten password: `POST /api/auth/forgot-password` emails a one-time link (1 hour);
   `POST /api/auth/reset-password` with `{"token", "password"}` sets it and signs the person out
   everywhere. Without `MAIL_SERVER`, emails are printed in the terminal.

Demo data (`python seed.py`), password `ChangeMe123!` for everyone (review only):

| Business | Join code | Accounts |
|---|---|---|
| StockPilot Demo Shop | `DEMO2026` | `admin@`, `procurement@`, `inventory@`, `sales@`, `employee@stockpilot.test` |
| Highland Café | `CAFE2026` | `owner@highlandcafe.test` (admin), `till@highlandcafe.test` (sales) |

Sign in as each owner to see that the two businesses never see each other's products or sales.

## Test

```bash
pytest                 # tests + coverage (fails below 60%)
ruff check .           # lint
ruff format .          # format the code
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
| `/api/auth/register-business`, `/register`, `/login`, `/refresh`, `/forgot-password`, `/reset-password`, `GET /api/images/<id>`, `/api/health` | public |

Error responses always look like `{"error": {"code": 422, "message": "...", "details": {...}}}`:
422 invalid fields · 400 unknown linked record or bad JSON · 401 not signed in · 403 wrong role ·
404 not found · 409 duplicate or not allowed in the current state · 405 wrong method.

The database design is in [`../docs/ERD.md`](../docs/ERD.md).

## Deploy

The repository has a Render Blueprint (`../render.yaml`): the API, a PostgreSQL database and a
small Redis for the rate limit. On render.com choose **New → Blueprint**, pick the repository, then
set `CORS_ORIGINS` and `FRONTEND_URL` to the frontend's address (and the `MAIL_*` values when you
have an SMTP account). Each deploy runs `flask db upgrade` before the new version goes live and
starts `gunicorn wsgi:app`. `Procfile` does the same on Heroku-style hosts (Railway, Dokku…).

With `APP_ENV=production` the API refuses to start without real `SECRET_KEY`, `JWT_SECRET_KEY`,
`DATABASE_URL`, `CORS_ORIGINS` and `FRONTEND_URL`, sends HSTS and trusts the proxy's client IP.
Load the demo data once with `python seed.py` from the host's shell if reviewers need it.

## Changed a model?

```bash
flask db migrate -m "describe the change"
flask db upgrade
```

Commit the new file in `migrations/versions/` together with the model change.
