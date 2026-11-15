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

Open http://localhost:5173. The **System status** page shows whether the backend is reachable.

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | Start the app with live reload |
| `npm test` | Run the tests |
| `npm run lint` | Check the code for mistakes |
| `npm run format` | Format the code |
| `npm run build` | Build for deployment |

## Folders

```
src/
├── api/client.js        talks to the Flask API
├── store/               Redux store (one slice per resource)
├── components/          Layout, Field, Pagination
├── features/products/   products list + form
├── features/suppliers/  suppliers list + form
├── pages/               System status
└── test/                tests
```
