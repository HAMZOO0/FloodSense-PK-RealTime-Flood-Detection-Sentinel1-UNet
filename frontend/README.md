# FloodSense-PK — React Web Console

Professional React web dashboard for the FloodSense-PK flood intelligence
platform. Mirrors every feature of the Streamlit app, driven entirely by the
FastAPI backend (`backend/`).

## Stack

- **Vite + React 19 + TypeScript**
- **Tailwind CSS v4** — custom dark ops-console design system (`src/index.css`)
- **Radix UI** primitives (dialog, tabs) with a hand-rolled shadcn-style component layer
- **TanStack Query v5** — data fetching, caching, job polling
- **React Router v7**, **Recharts**, **lucide-react**, **sonner**
- Self-hosted **Inter** + **Space Grotesk** (Fontsource)

## Pages ↔ API

| Page | Endpoints |
|---|---|
| Overview | `GET /api/analysis`, `GET /api/alerts`, `GET /api/health` |
| Detection | `POST /api/analysis/{district}` → poll `GET /api/jobs/{id}` → `latest` + `image` |
| River Flows | `GET /api/rivers` (+ `force_refresh`) |
| AI Intelligence | `GET /api/analysis/{district}/insights` |
| Agentic Workflow | `POST /api/pipeline/{district}` |
| Alerts | `GET/POST /api/alerts`, `GET /api/alerts/mine` |
| Knowledge Assistant | `POST /api/chat` |
| Auth (sidebar) | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |

## Run it

1. Start the backend from the project root (needs `MONGO_URI` etc. configured):

   ```powershell
   & .venv\Scripts\Activate.ps1
   uvicorn backend.app:app --host 0.0.0.0 --port 8000
   ```

2. Start the web console:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

   Open http://localhost:5173 — Vite proxies `/api` to `localhost:8000`
   (see `vite.config.ts`), so no CORS setup is needed in dev.

## Production build

```powershell
npm run build     # type-checks then bundles to dist/
npm run preview   # serve the production bundle locally
```

For deployment, serve `dist/` behind any static host and route `/api/*` to the
FastAPI service (or set an absolute base URL in `src/lib/api.ts`).

## Design notes

- Dark-only console on the brand base `#0B0F19`; electric-blue accent `#3987E5`.
- Status colors (LOW `#0CA30C` / MODERATE `#FAB219` / HIGH `#D03B3B`, river
  EXTREME `#EC835A`) were validated for ≥3:1 contrast and CVD separation on the
  dark surface, and are always paired with an icon + label — never color alone.
- Magnitude bars (risk ranking, river inflow) are single-hue; severity is
  carried by chips, not bar color ramps.
