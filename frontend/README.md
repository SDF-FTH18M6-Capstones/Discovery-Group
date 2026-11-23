# StockPilot — Frontend (React)

## You need

- Node.js
- The backend running (see `../backend/README.md`)

## Set up and run

```bash
cd frontend
npm install
cp .env.example .env.local       # Windows: copy .env.example .env.local
npm run dev
```

Open http://localhost:5173 and sign in with a demo account (see the backend README).
The **System status** page shows whether the backend is reachable.

## Sign-in

- `src/auth/AuthContext.jsx`: the Auth Context Provider. `useAuth()` gives `user`, `signIn`,
  `register`, `signOut` and `hasRole("admin", ...)`.
- `src/auth/session.js`: keeps the tokens in `localStorage` between page loads.
- `src/api/client.js`: the fetch interceptor. It adds the bearer token to every request, renews
  an expired access token with the refresh token, and sends the user to `/login` when both expire.
- `src/auth/RequireAuth.jsx`: wraps pages that need a signed-in user (and, optionally, a role).
- `src/auth/roles.js`: role names and which roles manage what; the menu and pages use it.

## Pages and who sees them

| Page               | Address                               | Who                                                                    |
| ------------------ | ------------------------------------- | ---------------------------------------------------------------------- |
| Landing page       | `/`                                   | visitors: what StockPilot does, Start your business                    |
| Sign up            | `/register`, `/register?code=…`       | join a business with its code, or start a new one (`?start=1`)         |
| Password reset     | `/forgot-password`, `/reset-password` | anyone; the emailed link opens the second page                         |
| Dashboard          | `/`                                   | everyone: StockPilot Pulse tiles for their role, each opening its list |
| Products           | `/products`                           | everyone; Add / Edit / Retire / photo for admin, inventory             |
| Product detail     | `/products/:id`                       | everyone; Trace timeline for admin, inventory                          |
| Categories         | `/categories`                         | everyone; changes for admin, inventory                                 |
| Suppliers          | `/suppliers`                          | admin, procurement (codes SUP-001, active / inactive)                  |
| My requests        | `/requests`                           | everyone: Active / Completed tabs, cancel, timeline                    |
| Approvals          | `/approvals`                          | procurement decides (Awaiting, Urgent, Decided today); admin views     |
| Assets             | `/assets`                             | admin, inventory: barcode labels, assign / return, history, overdue    |
| Assets with me     | `/assets`                             | everyone else: what they hold                                          |
| New sale (till)    | `/sales/new`                          | admin, sales                                                           |
| Sales and receipts | `/sales`                              | admin (all, can void today's), sales (own)                             |
| Purchases          | `/purchases`                          | procurement drafts and orders · inventory receives in parts · admin    |
| Stock ledger       | `/stock`                              | admin, inventory (adjustments, date filter, CSV export)                |
| Repairs            | `/repairs`                            | everyone reports; admin, inventory start, complete or reject           |
| Notifications      | `/notifications`                      | everyone (own); each opens the record it is about                      |
| Reports            | `/reports`                            | admin: date ranges, gross and net profit, expenses, CSV                |
| Users              | `/users`                              | admin: roles, deactivate / reactivate                                  |
| Audit log          | `/audit`                              | admin                                                                  |
| Settings           | `/settings`                           | everyone; business settings and the join code for admin                |

## Installable app (PWA)

`public/manifest.webmanifest`, the icons and `public/sw.js` make StockPilot installable over
HTTPS. The service worker caches only the app shell (HTML, JS, CSS, icons); API responses and
tokens are never cached (the API is on another address, and `/api/` is skipped too). Offline, the
app shows a banner, and a page that was never loaded shows `offline.html`. The service worker is
registered only in the built app (`npm run build`), not in `npm run dev`.

## Deploy

- **Netlify**: base directory `frontend`; `netlify.toml` builds `dist/` and sends every address
  to `index.html`, so refreshing `/products` works. Set `VITE_API_URL` to the API's address.
- **Vercel**: root directory `frontend`; `vercel.json` does the same.
- Any other static host: upload `dist/` and add the same "all paths → index.html" rewrite
  (`public/_redirects` covers hosts that read that file).

Then set the API's `CORS_ORIGINS` and `FRONTEND_URL` to this address.

## Look and dark mode

- **Palette**: pine (the sidebar and landing page), jade (actions, money in), saffron
  (attention: the active page, unread, low stock), brick (money out, errors) on a cool paper
  background. Each colour is a CSS variable in `src/index.css` with a light and a dark value.
  Use the token classes (`bg-surface`, `text-muted`, `border-line`, `bg-brand`, `bg-saffron`…)
  and the shared classes (`panel`, `card`, `btn-primary`, `btn-secondary`, `btn-accent`,
  `btn-ghost`, `btn-danger`, `input`, `seg`, `chip`, `page-title`, `figure`, `code`), never
  fixed colours, and a new page works in both themes.
- **Type**: Bricolage Grotesque for headings and figures, Geist for text, Geist Mono for codes
  (SKUs, receipt and order numbers). They are npm packages (`@fontsource-variable/…`) bundled
  with the app, so nothing is fetched from Google.
- **Building blocks** in `components/ui.jsx`: `StatStrip` (the row of figures at the top of a
  page), `Panel`, `EmptyState`, `StockMeter`, `Avatar`, `Sparkline` and `BarChart` (with a
  tooltip and a hidden table for screen readers).
- `src/theme/ThemeContext.jsx` keeps the choice (Light, Dark, Same as my device) in this browser
  and puts the `dark` class on `<html>`; a small script in `index.html` does it before the first
  paint so the page never flashes white.
- Visitors who are not signed in see the landing page (`pages/LandingPage.jsx`) at `/`; signed
  in, `/` is the dashboard. The logo is `components/Logo.jsx` (swap in your own file there).
- Every page sits inside `ErrorBoundary`: a crash shows a banner, not a blank screen.
- Lists show grey placeholder rows while loading (`components/Skeleton.jsx`).
- Money uses the business's currency (`format.js` `money()`), set from the signed-in account.
- Pickers that used to load "the first 100" records now search the API as you type
  (`components/SearchPicker.jsx`).
- Cancelling a request, approving / rejecting, moving a repair and marking notifications read
  change the screen at once and are undone if the server says no (`store/resourceSlice.js`:
  `patchItem`, `removeItem`, `restoreItems`).

## Commands

| Command                 | What it does                   |
| ----------------------- | ------------------------------ |
| `npm run dev`           | Start the app with live reload |
| `npm test`              | Run the tests                  |
| `npm run test:coverage` | Tests with a coverage report   |
| `npm run lint`          | Check the code for mistakes    |
| `npm run format`        | Format the code                |
| `npm run build`         | Build for deployment           |

## Folders

```
src/
├── api/client.js        talks to the Flask API, adds the token
├── auth/                Auth Context, session storage, RequireAuth, role names
├── store/               Redux store (one slice per resource)
├── theme/               light / dark mode
├── components/          Layout, ui (shared blocks), Logo, ThemeSwitch, ErrorBoundary, Skeleton, Icon, PageHeader, Field, Pagination, StatusBadge,
│                        Timeline (Trace Timeline), SearchPicker, PhotoPicker, Barcode (Code 128)
├── csv.js               CSV export of any report table
├── features/dashboard/  home page: counts for the signed-in role (+ the week's sales for admin)
├── features/sales/      till (point of sale), sales history, printable receipt
├── features/purchases/  purchase orders: place, receive, cancel
├── features/stock/      stock ledger + adjustments
├── features/repairs/    report a fault / repair board
├── features/notifications/ notifications centre
├── features/reports/    sales, profit, stock value, best sellers (admin)
├── features/settings/   profile, password, appearance
├── features/products/   products list + form, product detail with stock trace
├── features/categories/ categories list + add / rename
├── features/suppliers/  suppliers list + form
├── features/requests/   My requests (everyone) and Approvals (procurement)
├── features/assets/     asset register (admin, inventory) / My assets (everyone else)
├── features/users/      users and roles (admin)
├── features/audit/      audit log (admin)
├── pages/               Landing page, Sign in, Join / start a business, password reset, System status
└── test/                tests
```
