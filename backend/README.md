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

Already had a database from Sprint 2? Passwords are now hashed with Bcrypt, so rebuild the
demo data once (this deletes local data only):

```bash
flask db downgrade base
flask db upgrade
python seed.py
```

## Run

```bash
flask run
```

- Health check: http://localhost:5000/api/health
- Swagger docs: http://localhost:5000/api/docs

## Sign in

Sign-in has two steps, and every endpoint except health and `/api/auth/*` needs a token.

1. `POST /api/auth/login` with `{"email", "password"}`. A 6-digit code is emailed.
2. `POST /api/auth/verify-otp` with `{"email", "code"}`. You get `access_token` (15 minutes)
   and `refresh_token` (7 days).
3. Send `Authorization: Bearer <access_token>` with every request. In Swagger, click
   **Authorize** and paste the access token.

Locally there is no email service: with `SENDGRID_API_KEY` empty, emails (verification links and
codes) are printed in the `flask run` terminal. With `DEV_SHOW_OTP=true` in `.env`, the login
response also contains the code as `dev_code`. **Never** set `DEV_SHOW_OTP` on the deployed backend.

Demo accounts (after `python seed.py`), password `ChangeMe123!`:
`admin@`, `procurement@`, `inventory@`, `sales@`, `employee@stockpilot.test`.

## Test

```bash
pytest                 # tests + coverage (fails below 60%)
ruff check .           # lint
ruff format .          # format the code
```

API tests in Postman: start the backend with `DEV_SHOW_OTP=true`, run `python seed.py`, import
`postman/StockPilot.postman_collection.json` and run the collection (54 requests, 73 checks).

## Endpoints and who may use them

Lists take `?page=1&per_page=20` (max 100). No token → 401; wrong role → 403.

| Endpoint | Read | Create / update / delete |
|---|---|---|
| `/api/categories/`, `/api/categories/<id>` | everyone signed in | admin, inventory |
| `/api/products/`, `/api/products/<id>` (filters: `search`, `category_id`, `low_stock`) | everyone signed in | admin, inventory |
| `/api/suppliers/`, `/api/suppliers/<id>` (filter: `search`) | admin, procurement | admin, procurement |
| `/api/requests/`, `/api/requests/<id>` (filter: `status`) | admin and procurement see all; others see their own | anyone creates; only the requester edits or deletes, while pending |
| `POST /api/requests/<id>/approve`, `/reject` | | procurement only, never on their own request; reject needs a `comment` |
| `/api/assets/`, `/api/assets/<id>` (filters: `search`, `status`) | admin and inventory see all; others see what they hold | admin, inventory |
| `/api/users/`, `/api/users/<id>`, `PUT /api/users/<id>/role` | admin | admin (cannot change own role) |
| `/api/auth/register`, `verify-email`, `resend-verification`, `login`, `verify-otp`, `refresh` | public | |
| `GET /api/auth/me` | everyone signed in | |

Error responses always look like `{"error": {"code": 422, "message": "...", "details": {...}}}`:
422 invalid fields · 400 unknown linked record or bad JSON · 401 not signed in · 403 wrong role ·
404 not found · 409 duplicate or not allowed in the current state · 405 wrong method.

The database design is in [`../docs/ERD.md`](../docs/ERD.md).

## Changed a model?

```bash
flask db migrate -m "describe the change"
flask db upgrade
```

Commit the new file in `migrations/versions/` together with the model change.
