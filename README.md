# StockPilot

Inventory, sales, procurement and asset management for a small business.
SDF-FTH18 capstone · Flask API + React app in one repository.

| Folder | What it is | How to run it |
|---|---|---|
| `backend/` | Flask REST API, PostgreSQL, Swagger docs | see [backend/README.md](backend/README.md) |
| `frontend/` | React app (Vite, Redux Toolkit, Tailwind) | see [frontend/README.md](frontend/README.md) |

## Team

| Role | Name |
|---|---|
| Scrum Master · QA/DevOps | David |
| Backend | Carlos |
| Database / API | Vincent |
| Frontend | Keith |

## How we work (Gitflow)

- `main` = what we release at each milestone gate. Never push to it directly.
- `develop` = where finished work is merged.
- One branch per GitHub issue, made from `develop`: `feature/<issue-number>-short-name`
- Commit messages: `feat: add product form`, `fix: reject negative prices`, `test: ...`, `docs: ...`
- Open a pull request into `develop`. CI must pass. The Scrum Master reviews and merges.
- No work starts unless it has an issue on the STOCKPILOT project board.
