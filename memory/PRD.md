# PRD — Telegram Ultra (cloned repo deployment)

## Original problem statement
Clone https://github.com/alifnewone7-create/a-v-k.git (public), copy all files/folders into /app, run the frontend, change nothing. Frontend .env already contains backend (Neon Postgres) connection.

## What was done (2026-09-08)
- Cloned the repo and copied all files/folders (frontend, backend, tests, test_reports, memory, design_guidelines.json, README) into /app, replacing the default template.
- Frontend: Next.js 16 app (app router), deps installed with pnpm 9 using the repo's pnpm-lock.yaml (frozen). Runs on port 3000 via supervisor (`yarn start` -> `next dev`).
- Backend: FastAPI transparent reverse proxy on :8001 forwarding /api/* to Next.js :3000 (installed `httpx`).
- No repo file was modified (pnpm-workspace.yaml was only temporarily moved during install, then restored).
- Verified: https://2dce9fe2-b84d-4144-a79b-cec13960e418.preview.emergentagent.com redirects to /login and renders the Telegram Ultra login page; /api proxy responds (401 without session = auth working).

## Data
- Neon Postgres via DATABASE_URL in /app/frontend/.env (external, managed by repo owner).
- TGLion API credentials in same .env.

## Known notes / backlog
- HMR websocket from the preview domain is blocked (allowedDevOrigins wildcard doesn't cover two-level subdomain `avk-preview.cluster-5.preview.emergentcf.cloud`). App works fine; only dev hot-reload affected. Left unchanged per "do not change anything".
- P0 remaining: none. P1: none requested.

## Next action items
- User to sign in with their username/password/secret to use the dashboard.
