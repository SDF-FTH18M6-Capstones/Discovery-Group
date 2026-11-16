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

## Commands

| Command          | What it does                   |
| ---------------- | ------------------------------ |
| `npm run dev`    | Start the app with live reload |
| `npm test`       | Run the tests                  |
| `npm run lint`   | Check the code for mistakes    |
| `npm run format` | Format the code                |
| `npm run build`  | Build for deployment           |

## Folders

```
src/
├── api/client.js        talks to the Flask API, adds the token
├── auth/                Auth Context, session storage, RequireAuth
├── store/               Redux store (one slice per resource)
├── components/          Layout, Field, Pagination
├── features/products/   products list + form
├── features/suppliers/  suppliers list + form
├── pages/               Sign in, Create account, System status
└── test/                tests
```