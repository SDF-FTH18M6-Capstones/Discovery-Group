# What changed: multi-business StockPilot and the remaining user stories

## 1. Several businesses in one system

| Area | What it does |
|---|---|
| Sign-up | `Start your business` creates a business; its owner becomes the Administrator. Staff join with the business's **join code** (or an invite link `/register?code=…`). The Administrator can make a new code at any time. |
| Isolation | Every table has `business_id`. `app/tenancy.py` adds the business filter to every ORM query (selects, joins, counts, `Session.get`, updates, deletes) and stamps new rows. `get_or_404` / `find` double-check it. `tests/test_tenancy.py` runs every endpoint against a second business: lists never include its rows, its ids return 404, its ids in request bodies are refused. |
| Settings | Per business: name, time zone (dates and reports follow it), currency, VAT rate, phone, email, address and receipt footer (printed on receipts). |
| Numbering | Each business has its own sequences: S-0001, PO-0001, GRN-0001, REQ-0001, REP-001, ADJ-0001, SUP-001, AST-0001. |
| Uniqueness | SKUs, category names, asset codes and barcodes are unique per business. An email belongs to one business. |
| Existing data | The migration moves everything already in the database into one business, "My Business" (rename it in Settings). |

## 2. The quick fixes from the walkthrough guide

| Issue | Done |
|---|---|
| No CI | `.github/workflows/ci.yml`. The backend job runs ruff lint and format check, migrations on a fresh Postgres (`flask db upgrade`, `flask db check`, seed), and pytest with coverage (fails under 60%), then uploads coverage. The frontend job runs oxlint, Prettier check, Vitest with coverage, then builds. |
| Backend lint (24 errors) | `__all__` fixed, long lines wrapped, `ruff format` applied: `ruff check` and `ruff format --check` pass. |
| No deployment config | `render.yaml` (API + Postgres + Redis, `flask db upgrade` before each release, gunicorn), `backend/Procfile`, `frontend/netlify.toml`, `frontend/vercel.json`, `frontend/public/_redirects` (SPA rewrite). |
| Broken ERD link | Fixed in both READMEs; `docs/ERD.md` regenerated from the models. |
| `develop` vs `development` | PR template now says `development`. |
| Sign-out only in the browser | `POST /api/auth/logout` revokes the session server-side: the refresh token and every access token made from it stop working (US-04). |
| Profit used today's cost | `sale_items.unit_cost` is saved at sale time; reports use it (US-25/US-41). |
| In-memory rate limiter | `RATELIMIT_STORAGE_URI` points at Redis in `render.yaml`. |
| First-100 dropdowns | Product, supplier and ledger pickers now search the API as you type. |
| Product form could change stock | Quantity is only the opening stock when creating; afterwards stock changes only through adjustments, receipts and sales (US-09). |
| Hard-coded receipt header | The receipt shows the business's own name, address, phone, VAT and footer. |

## 3. User stories

| Story | Status |
|---|---|
| US-04 Sign-out revokes the session | Built |
| US-05 Password reset by email (1-hour one-time link, same answer for unknown emails, signs out every device) | Built |
| US-06 Deactivate users; audit log of role changes and deactivations | Built (`/audit` page) |
| US-07 Phone on the profile | Built |
| US-08 Deactivate a category | Built |
| US-10 Photo upload (JPEG/PNG/WebP ≤ 5 MB, resized to 1200 px, old photo removed) | Built (products and assets) |
| US-12 Retire / restore products; price changes affect new sales only | Built |
| US-13 Supplier codes (SUP-001), inactive suppliers get no new orders | Built |
| US-14 Request can point at a catalogue product; REQ numbers; urgent requests emailed | Built |
| US-15 Active / Completed tabs, Fulfilled and Cancelled states, Trace Timeline | Built |
| US-16 Cancel a pending request (kept on record) | Built |
| US-17 Queue sorted by urgency then age; Awaiting / Urgent / Decided today filters | Built |
| US-19 Draft → Ordered; link a PO to an approved request | Built |
| US-20 Cancel with a reason (only before anything is received) | Built |
| US-21/22 Receive in parts, GRN numbers, outstanding per line; linked request becomes Fulfilled | Built |
| US-23/26 Idempotency keys on receiving and on sales | Built (tested: the same key never adds stock or a sale twice) |
| US-25 VAT (included in prices) on receipts; cost saved per sale line | Built |
| US-29 Void a same-day sale with a reason (stock returns through `sale_void` lines) | Built |
| US-31 Ledger: quantity after, reference, date filter, CSV export | Built |
| US-32–35 Asset categories, serial numbers, server-made codes and Code 128 barcodes, assignment history with expected return and condition, overdue filter | Built |
| US-38 Repairs: Rejected with a reason, resolution and cost on completion, previous asset status restored | Built |
| US-39 StockPilot Pulse: one role-aware API call | Built |
| US-40 Trace Timeline for products, requests and assets | Built |
| US-41 Today / 7 days / this month / custom ranges, gross and net profit, expenses, CSV for every report table | Built |
| US-42 Email notifications for decisions, repairs, assignments, urgent requests and low stock; low-stock alert only when crossing the level; notifications link to the record | Built |
| US-43 Installable PWA (manifest, icons, service worker caching only the app shell, offline page and banner) | Built |
| US-02/03 Email verification and one-time sign-in codes | **Next phase.** The team removed this earlier (migrations 2–3). The email layer it needs now exists (`app/mail.py`), so it can return without new infrastructure. |
| US-48 Live on two platforms over HTTPS | **Ready, not deployed.** The configuration is in the repository; someone with the team's Render and Netlify/Vercel accounts must connect them (see the README). |

## 4. Checks run

- Backend: 981 tests pass with 97% coverage. They include the permission matrix for every endpoint and role, the cross-business isolation suite, idempotency, partial receiving, voids, password reset, sign-out revocation, photos, CSV and email delivery. `ruff check` and `ruff format --check` are clean.
- The migration was run on a database built with the original migrations and seed. After upgrading, its schema is identical to a fresh `create_all`: constraints and indexes were compared and `flask db check` reports nothing. The data stayed consistent too: each product's quantity equals the last ledger line.
- Frontend: 88 tests pass; oxlint and Prettier are clean; the production build succeeds.
- A browser walkthrough of the built app against the seeded API completed a sale, partial receiving and an asset barcode label. Signing in as the second business showed none of the first business's data, and there were no console errors.
- The Postman collection was updated (join codes, server-made asset codes, retiring instead of deleting a product with history). Every request returned its expected status on a freshly seeded database.

## 5. Things to know

- **Email** goes out only when `MAIL_SERVER` is set; otherwise messages are printed in the API's log. Sending happens after the database commit, on a background thread.
- **Photos** are stored in PostgreSQL (`images` table) so they survive redeploys on hosts with temporary disks. For very large catalogues, move them to object storage (S3, Cloudinary) later.
- **Downgrading** past the multi-business migration is not automatic. Take a database backup before upgrading production.
- **Branch protection** is a repository setting: turn it on for `main` and `development` so merging waits for CI.
- `docs/erddoc.png` still shows the original single-business design; `docs/ERD.md` is current.
