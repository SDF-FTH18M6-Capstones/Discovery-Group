# StockPilot

StockPilot runs the till, the stockroom, purchasing and company assets for small businesses. One
installation serves any number of businesses: each signs up, invites its staff with a join code,
takes M-Pesa payments into its own Paybill or till, and only ever sees its own data.

**Live demo:** https://stockpilotke254.netlify.app

## Features

- **Point of sale:** sell from a searchable product grid, send an M-Pesa prompt to the customer's
  phone and complete the sale automatically when Safaricom confirms it. Cash and card sales,
  printable receipts with VAT, same-day voids.
- **Stock that keeps itself up to date:** every sale, delivery and adjustment is written to a stock
  ledger. Low stock prepares a purchase order for the product's usual supplier, or sends it
  straight away to a trusted supplier. Receiving a delivery updates stock and the average cost.
- **Purchasing:** staff requests with approval, purchase orders emailed to suppliers, partial
  deliveries with goods received notes.
- **Assets and repairs:** barcode labels, assignment and return, overdue items, a repair board.
- **Oversight for owners:** the administrator approves new staff and chooses their roles, follows
  every sale and order, and reads reports, profit, expenses and a full audit log. An evening email
  summarises the day.
- **Security:** email confirmation, one-time sign-in codes, revocable sessions, role checks on
  every endpoint and strict separation between businesses.
- **Subscriptions:** a 14-day trial, then monthly plans paid by M-Pesa to StockPilot's Paybill. A
  lapsed business keeps read access to its data until it renews. A platform console lets
  StockPilot's owners follow every business and payment, add free months, suspend accounts and
  set the price.
- Installable as an app on phones and computers, with light and dark themes.

## Tech stack

| Part | Built with |
|---|---|
| API | Python 3.13, Flask, flask-smorest (OpenAPI), SQLAlchemy 2, Alembic, JWT |
| Database | PostgreSQL 16 |
| Web app | React 19, Vite, Redux Toolkit, React Router, Tailwind CSS |
| Payments and email | Safaricom Daraja (M-Pesa Express), Brevo |
| Quality | pytest (97% coverage), Vitest and Testing Library, Ruff, oxlint, Prettier, GitHub Actions |
| Hosting | Render (API, database, Key Value) and Netlify (web app) |

## Repository layout

| Folder | Contents |
|---|---|
| [`backend/`](backend/README.md) | REST API, database migrations, demo data and tests |
| [`frontend/`](frontend/README.md) | React web app and its tests |
| [`docs/`](docs/ERD.md) | Database design, user stories and wireframes |
| `.github/workflows/` | CI on every push and pull request, and the evening summary schedule |
| `render.yaml` | Render Blueprint for the API, database and Key Value |

## Running it locally

You need Python 3.13, Node.js 22 and PostgreSQL 16.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask db upgrade && python seed.py
flask run
```

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:5173. The demo data includes two businesses; sign in as
`admin@stockpilot.test` with the password `ChangeMe123!`, or start a business of your own. The
[backend README](backend/README.md#demo-data) lists every demo account.

## Deployment

The API deploys to Render from [`render.yaml`](render.yaml) and the web app to Netlify from
[`frontend/netlify.toml`](frontend/netlify.toml). The [backend README](backend/README.md#deployment)
covers the environment variables, email, M-Pesa and the scheduled summary.

## Team

| Role | Name |
|---|---|
| Scrum Master, QA and DevOps | David |
| Backend | Carlos |
| Database and API | Vincent |
| Frontend | Keith |

## Contributing

- `main` holds released work and `development` collects finished features; neither takes direct
  pushes.
- Branch from `development` as `feature/<issue-number>-short-name`.
- Write commit messages as `feat: …`, `fix: …`, `test: …` or `docs: …`.
- Open a pull request into `development`. CI must pass: linting, formatting, migrations and tests.
- Merge `development` into `main` with a merge commit, not a squash, so the two branches keep a
  shared history.
