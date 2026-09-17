# Phase 6 — Frontend feature modules and async job UX

Phase 6 removes frontend deployment assumptions from the UI and introduces a feature-oriented structure.

## Structure

```text
frontend/src/
├── app/
├── api/
├── auth/
├── cases/
├── uploads/
├── jobs/
├── analytics/
├── maps/
├── graphs/
├── alerts/
└── shared/
```

The original large dashboard is isolated as `analytics/LegacyDashboard.tsx` while the top-level `Dashboard.tsx` is now a thin app entry point. New functionality is implemented in feature modules instead of adding more code to the legacy component.

## API client

`src/api/client.ts` owns the base URL, auth header and 401 handling.

Local development:

```env
REACT_APP_API_BASE_URL=http://localhost:8000
```

Production container builds default to:

```text
/api
```

Nginx proxies `/api/` to `backend:8000`, so browser code has no production `localhost` dependency. A compatibility interceptor rewrites old absolute localhost calls from the isolated legacy analytics component to the configured base URL.

## Async analysis UX

`uploads/AsyncAnalysisPanel.tsx` submits `POST /cases/{id}/analysis`, receives a `job_id`, and `jobs/useJobPolling.ts` polls `GET /jobs/{job_id}` until a terminal state.

Displayed states:

```text
Queued
Processing <progress>%
Completed
Failed
```

Progress is durable because Phase 5 stores it in PostgreSQL rather than in browser/worker memory.

## Production frontend image

```bash
cd frontend
docker build -t ciis-frontend .
```

The image is a multi-stage Node build followed by Nginx serving the compiled React assets. `nginx.conf` includes SPA fallback, static asset caching, `/healthz`, and the `/api/` reverse proxy.

## Acceptance

```bash
cd frontend
npm ci
npm test -- --watchAll=false
npm run build
```

Then optionally:

```bash
docker build -t ciis-frontend .
docker run --rm -p 8080:80 ciis-frontend
```

For a full compose deployment the backend service should be resolvable by Nginx as `backend:8000`.
