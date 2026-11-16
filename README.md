# StockPilot

Inventory, sales, procurement and asset management for a small business.
Flask API + React app 

| Folder | What it is | How to run it |
|---|---|---|
| `backend/` | Flask REST API, PostgreSQL, Swagger docs | see [backend/README.md](backend/README.md) |
| `frontend/` | React app (Vite, Redux Toolkit, Tailwind) | see [frontend/README.md](frontend/README.md) |
| `docs/` | Database design ([ERD.md](docs/ERD.md), [erd.png](docs/erd.png)), user stories | |

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
- Open a pull request into `development`. CI must pass. The Scrum Master reviews and merges.

