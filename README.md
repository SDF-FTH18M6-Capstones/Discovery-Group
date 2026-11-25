# StockPilot

Inventory, sales, procurement and asset management for **any number of businesses**.
Flask API + React app. Each business signs up, invites its staff with a join code, and sees only
its own products, sales, orders, assets and people.

| Folder | What it is | How to run it |
|---|---|---|
| `backend/` | Flask REST API, PostgreSQL, Swagger docs | see [backend/README.md](backend/README.md) |
| `frontend/` | React app (Vite, Redux Toolkit, Tailwind), installable as a PWA | see [frontend/README.md](frontend/README.md) |
| `docs/` | Database design ([ERD.md](docs/ERD.md), [erddoc.png](docs/erddoc.png)), user stories, [what changed](docs/CHANGES.md) | |

## Quick start

```bash
# backend (needs PostgreSQL 16)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
flask db upgrade && python seed.py && flask run

# frontend, in a second terminal
cd frontend && npm install && cp .env.example .env.local && npm run dev
```

Open http://localhost:5173 and sign in as `admin@stockpilot.test` / `ChangeMe123!` (demo data
for review only; all demo accounts are in the backend README), or start your own business.

## Deploy

- **API**: Render Blueprint in [`render.yaml`](render.yaml) on the free plan (web service +
  PostgreSQL + Key Value). `backend/start.sh` runs migrations (and the demo seed when
  `SEED_DEMO=true`) on each start, then `gunicorn wsgi:app`. Email goes through Brevo's API
  (`BREVO_API_KEY`), because Render's free plan blocks SMTP. See `backend/README.md`.
- **Frontend**: Netlify ([`frontend/netlify.toml`](frontend/netlify.toml)) or Vercel
  ([`frontend/vercel.json`](frontend/vercel.json)); both rewrite every path to `index.html`.
- Set the API's `CORS_ORIGINS` and `FRONTEND_URL` to the frontend's HTTPS address, and the
  frontend's `VITE_API_URL` to the API's.

## Team

| Role | Name |
|---|---|
| Scrum Master · QA/DevOps | David |
| Backend | Carlos |
| Database / API | Vincent |
| Frontend | Keith |

## How we work (Gitflow)

- `main` = what we release at each milestone gate. Never push to it directly.
- `development` = where finished work is merged.
- One branch per GitHub issue, made from `development`: `feature/<issue-number>-short-name`
- Commit messages: `feat: add product form`, `fix: reject negative prices`, `test: ...`, `docs: ...`
- Open a pull request into `development`. CI (`.github/workflows/ci.yml`) must pass: lint,
  format check, tests with coverage.
  Turn on branch protection for `main` and `development` so merging waits for CI.