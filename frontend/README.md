# StockPilot web app

The React front end of StockPilot. It talks to the [API](../backend/README.md), works on phones
and desktops, and can be installed as an app.

## Requirements

- Node.js 22
- The API running locally or a deployed API address

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

`VITE_API_URL` in `.env.local` points to the API (`http://localhost:5000` by default). Open
http://localhost:5173 and sign in with one of the [demo accounts](../backend/README.md#demo-data).
The System status page shows whether the API is reachable.

## Commands

| Command                 | Purpose                            |
| ----------------------- | ---------------------------------- |
| `npm run dev`           | Development server with hot reload |
| `npm test`              | Run the test suite                 |
| `npm run test:coverage` | Tests with a coverage report       |
| `npm run lint`          | Lint with oxlint                   |
| `npm run format`        | Format with Prettier               |
| `npm run build`         | Production build in `dist/`        |

## Pages

| Page                                                 | Address                                                                       | Who                                                                                 |
| ---------------------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Landing page                                         | `/`                                                                           | visitors                                                                            |
| Sign in, sign up, password reset, email confirmation | `/login`, `/register`, `/forgot-password`, `/reset-password`, `/verify-email` | everyone                                                                            |
| Dashboard                                            | `/`                                                                           | signed-in users: the figures for their role                                         |
| Products, product detail, categories                 | `/products`, `/products/:id`, `/categories`                                   | everyone reads; inventory edits                                                     |
| Suppliers                                            | `/suppliers`                                                                  | procurement edits and marks trusted suppliers; the administrator and inventory read |
| My requests, approvals                               | `/requests`, `/approvals`                                                     | everyone requests; procurement decides                                              |
| Purchases                                            | `/purchases`                                                                  | procurement orders; inventory receives                                              |
| New sale, sales                                      | `/sales/new`, `/sales`                                                        | sales staff run the till; the administrator follows every sale                      |
| Stock ledger                                         | `/stock`                                                                      | inventory adjusts; the administrator reads                                          |
| Assets, repairs                                      | `/assets`, `/repairs`                                                         | inventory manages; everyone sees what they hold and reports faults                  |
| Reports, users, audit log, billing                   | `/reports`, `/users`, `/audit`, `/billing`                                    | administrator; Reports has the loan-readiness PDF                                   |
| Insights, M-Pesa money                               | `/insights`, `/money`                                                         | administrator: forecasts; statements, SMS or a linked phone                         |
| Scan a receipt                                       | `/receipts/scan`                                                              | administrator, procurement, inventory: receipt to expense or stock                  |
| Notifications, settings                              | `/notifications`, `/settings`                                                 | everyone; business, M-Pesa and WhatsApp settings for the administrator              |
| Platform                                             | `/platform`                                                                   | StockPilot's own owners (`PLATFORM_OWNERS` on the API)                              |

Buttons follow the job rather than the title: `useAuth().canDo("sales")` is true for sales staff,
and for the administrator only while nobody holds that role.

## Structure

```
src/
├── api/            fetch client: adds the token, renews it, signs out when it expires
├── auth/           AuthContext (useAuth), session storage, RequireAuth, role names
├── components/     Layout, form fields, pickers, tables, charts, barcodes, timelines
├── features/       one folder per area: sales, purchases, products, billing, settings, …
├── pages/          landing, sign-in and account pages, system status
├── store/          Redux Toolkit slices for the list pages
├── theme/          light and dark mode
└── test/           Vitest and Testing Library tests
```

## Design

- Colours are CSS variables in `src/index.css` with light and dark values, exposed as Tailwind
  classes (`bg-surface`, `text-muted`, `bg-brand`, …), so every page works in both themes.
- Shared classes (`card`, `panel`, `btn-primary`, `input`, `figure`, …) and the blocks in
  `components/ui.jsx` keep pages consistent.
- Bricolage Grotesque for headings, Geist for text and Geist Mono for codes, bundled with the app.
- Money is shown in the business's currency, and pickers search the API as you type.
- Every page sits inside an error boundary, and lists show placeholder rows while loading.

## Installable app

`public/manifest.webmanifest`, the icons and `public/sw.js` make the built app installable over
HTTPS. The service worker caches only the app shell; API responses and tokens are never cached.
Offline, the app shows a banner, and pages that were never opened fall back to `offline.html`.

## Receipt reading

Scan a receipt shrinks the photo in the browser first. Unless the server has online reading
turned on, `tesseract.js` then reads it on the device. The library is loaded only when someone
scans, and it fetches its English language data (about 4 MB) from jsDelivr the first time, so the
first scan needs a connection.

## Deployment

- **Netlify:** set the base directory to `frontend` and `VITE_API_URL` to the API's address.
  `netlify.toml` builds `dist/` and serves `index.html` for every path.
- **Vercel:** set the root directory to `frontend`; `vercel.json` does the same.
- **Any static host:** upload `dist/` with an "all paths to `index.html`" rewrite
  (`public/_redirects` covers hosts that read it).

Set the API's `CORS_ORIGINS` and `FRONTEND_URL` to the address the app is served from.
