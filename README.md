# Yomi

Yomi is a self-hosted, invite-only Japanese language learning platform with multi-user support, spaced repetition scheduling (FSRS), grammar/vocabulary content, and optional per-user AI key support.

**Current status:** Phases 1–3 substantially complete.
- Phase 1: Foundation (FastAPI, Next.js, Docker Compose, SQLite, nginx)
- Phase 2: Auth & multi-user (sessions, CSRF, encrypted secrets, admin, audit logging)
- Phase 3: Core content & SRS (grammar/vocab ingest, FSRS reviews, progress tracking)

Phases 4–6 (AI layer, advanced features, polish) are planned.

## Quick Start

```bash
make dev          # Start Docker Compose stack on http://localhost:8888
make test         # Run all tests (backend + ingestion)
make lint         # Check Python syntax, merge conflicts, frontend lint
make typecheck    # Python + frontend type checking
make bootstrap    # Create initial admin user (required on first run)
make backup       # Placeholder for future backup feature
```

## Architecture & Development

See `AGENTS.md` for project rules and context-loading guidelines.

Canonical architecture: [`docs/architecture/YOMI_ARCHITECTURE.md`](docs/architecture/YOMI_ARCHITECTURE.md)

Agent workflow docs: [`docs/agent/README.md`](docs/agent/README.md)
