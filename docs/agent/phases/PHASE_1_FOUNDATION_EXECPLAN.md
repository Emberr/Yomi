# Phase 1 ExecPlan — Foundation

## Purpose

Create a runnable but minimal Yomi stack: Docker Compose, nginx routing, FastAPI backend skeleton, Next.js frontend skeleton, SQLite connection layer, and ingestion scaffold.

## Source context

Read:

- `AGENTS.md`
- `docs/agent/YOMI_CONTEXT_BRIEF.md`
- `docs/agent/VALIDATION_MATRIX.md`

Consult full architecture sections:

- Section 6 Database Architecture
- Section 7 System Architecture Overview
- Section 8 Service Breakdown
- Section 15 Docker Compose
- Section 16 Directory Structure
- Section 19 Frontend Architecture
- Section 20 Operational Concerns

## Scope

- Docker Compose with `nginx`, `frontend`, `backend`, and `ingestion` profile.
- nginx reverse proxy: `/api/*` to backend, `/*` to frontend.
- Security headers in nginx or backend as appropriate.
- FastAPI app with `/api/health` and basic app lifecycle.
- SQLite connection helpers for `content.db` and `user.db` with required pragmas.
- Basic migration mechanism placeholder.
- Next.js app router skeleton with dark gothic CSS variables and navigation shell.
- PWA manifest.
- Ingestion service scaffold that can create/populate a minimal `content.db` placeholder.

## Non-goals

- Do not build authentication yet.
- Do not implement real content ingestion beyond a minimal scaffold unless low-risk.
- Do not implement SRS logic.
- Do not implement AI provider calls.

## Milestones

### M1.1 — Backend skeleton

- Create FastAPI application.
- Add `/api/health` returning DB connectivity and app version placeholder.
- Add database connection module applying SQLite pragmas.
- Add tests for health endpoint and DB initialization if test framework exists.

### M1.2 — Frontend skeleton

- Scaffold Next.js 15 TypeScript app.
- Add dark gothic theme CSS variables.
- Add app shell/navigation placeholders.
- Add login route placeholder but no real auth.
- Add PWA manifest.

### M1.3 — Compose and nginx

- Implement `docker-compose.yml` matching architecture.
- Add nginx config for frontend/backend routing.
- Add security headers: HSTS when behind HTTPS, nosniff, frame deny, referrer policy, CSP baseline.
- Validate `docker compose config`.

### M1.4 — Ingestion scaffold

- Create ingestion package/script.
- Script creates `content.db` with version metadata and minimal placeholder tables.
- It never touches `user.db`.

### M1.5 — Command integration

- `make dev` starts local stack or documents exact command.
- `make test`, `make lint`, `make typecheck` run real checks where possible.
- `.env.example` includes required variables.

## Done when

- The stack builds and starts.
- `/api/health` is reachable through nginx.
- Frontend route is reachable through nginx.
- `content.db` and `user.db` paths are mounted into backend volume.
- DB pragmas are applied at connection time.

## Verification gate

```bash
docker compose config
docker compose build
docker compose up -d
curl -fsS http://localhost:8888/api/health
curl -fsS http://localhost:8888/
make test
make lint
make typecheck
docker compose down
```

If ports differ, update this file and README.

## Security considerations

- Do not add auth shortcuts that will survive into later phases.
- Do not use permissive CORS unless local dev requires it, and then scope it to local dev config.
- Confirm nginx does not expose internal files or `/data`.

## Decision log

Record implementation decisions here.
