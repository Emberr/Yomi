# Phase 0 ExecPlan — Repository Scaffold and Agent Workflow

## Purpose

Create a repository that future coding-agent sessions can work in safely and predictably. This phase does not implement product features. It establishes structure, commands, docs, and verification stubs.

## Source context

Read:

- `AGENTS.md`
- `docs/agent/YOMI_CONTEXT_BRIEF.md`
- `docs/agent/CONTEXT_LOADING_POLICY.md`
- `docs/agent/VALIDATION_MATRIX.md`

Consult full architecture sections if needed:

- Section 15 Docker Compose
- Section 16 Directory Structure
- Section 21 Build Order

## Scope

- Initialize repo structure.
- Add AGPL license placeholder or full license if available.
- Add README, SECURITY, CONTRIBUTING, LICENSES stubs.
- Add `frontend/`, `backend/`, `ingestion/`, `nginx/`, `deploy/`, `docs/` directories.
- Add Makefile with expected targets.
- Add `.env.example` and `.gitignore`.
- Preserve the agent context pack inside `docs/agent/` and full architecture in `docs/architecture/`.

## Non-goals

- Do not implement auth.
- Do not implement ingestion logic beyond stubs.
- Do not design the full UI.
- Do not add production dependencies unless required for initial skeletons.

## Milestones

### M0.1 — Create root structure

Expected files/directories:

```text
AGENTS.md
README.md
LICENSE
LICENSES.md
SECURITY.md
CONTRIBUTING.md
.env.example
.gitignore
Makefile
docker-compose.yml
frontend/
backend/
ingestion/
nginx/
deploy/
docs/agent/
docs/architecture/
```

### M0.2 — Add command stubs

Makefile targets should exist even if some fail with clear messages:

- `make dev`
- `make test`
- `make lint`
- `make typecheck`
- `make bootstrap`
- `make backup`

### M0.3 — Add initial Docker Compose skeleton

Services may be placeholders if apps are not scaffolded yet, but `docker compose config` should be valid by the end of Phase 1 at latest. In Phase 0, document blockers if Compose cannot validate yet.

### M0.4 — Commit agent workflow docs

Ensure `AGENTS.md` remains concise and points to detailed context files instead of embedding the full architecture.

## Done when

- Repo layout matches the intended architecture.
- Agent docs are committed in predictable locations.
- Makefile exists with named targets.
- `.env.example` includes required environment variables.
- There is a clear next prompt for Phase 1.

## Verification gate

Run:

```bash
find . -maxdepth 3 -type f | sort
make test || true
make lint || true
make typecheck || true
docker compose config || true
```

If any command is intentionally not implemented yet, the target must fail with a clear message instead of silently succeeding.

## Decision log

Record implementation decisions here as they are made.
