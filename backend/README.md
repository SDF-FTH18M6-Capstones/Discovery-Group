# StockPilot — Backend (Flask API)

## You need

- Python 3.12 or newer
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

## Run

```bash
flask run
```

- Health check: http://localhost:5000/api/health
- Swagger docs: http://localhost:5000/api/docs

## Test

```bash
pytest                 # tests + coverage (fails below 60%)
ruff check .           # lint
ruff format .          # format the code
```

API tests in Postman: import `postman/StockPilot.postman_collection.json` and run the collection.

## Endpoints

Every resource has the same five endpoints. Lists take `?page=1&per_page=20` (max 100).

| Resource | List / create | One item: get / update / delete | Extra filters |
|---|---|---|---|
| Categories | `/api/categories/` | `/api/categories/<id>` | |
| Products | `/api/products/` | `/api/products/<id>` | `search`, `category_id`, `low_stock` |
| Suppliers | `/api/suppliers/` | `/api/suppliers/<id>` | `search` |
| Requests | `/api/requests/` | `/api/requests/<id>` | `status` |
| Assets | `/api/assets/` | `/api/assets/<id>` | `search`, `status` |

## Changed a model?

```bash
flask db migrate -m "describe the change"
flask db upgrade
```

Commit the new file in `migrations/versions/` together with the model change.