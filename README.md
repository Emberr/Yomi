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

## Local Development Bootstrap

Full first-run sequence:

**1. Start the stack and run ingestion**
```bash
docker compose up -d --build
docker compose --profile tools run --rm ingestion
```

**2. Create the initial admin account**

Pass credentials via environment variables (no hardcoded defaults):
```bash
YOMI_BOOTSTRAP_ADMIN_USERNAME=admin \
YOMI_BOOTSTRAP_ADMIN_DISPLAY_NAME="Admin" \
YOMI_BOOTSTRAP_ADMIN_PASSWORD=changeme \
make bootstrap
```

The script prompts interactively if any variable is unset.

**3. Log in and verify content**

Open http://localhost:8888/login, sign in as `admin`, then:
- `/grammar` — browse grammar points by JLPT level
- `/grammar/<slug>` — detail view with furigana, examples, TTS
- `/vocabulary` — search JMDict (e.g. `食べる`, `eat`, `taberu`)

**4. Create invite codes for additional users (optional)**

```bash
ADMIN_USER=admin ADMIN_PASS=changeme ./scripts/dev-invite.sh
```

Outputs an invite code. Register the new user at http://localhost:8888/register.

To create an admin-level invite:
```bash
ADMIN_USER=admin ADMIN_PASS=changeme ADMIN_INVITE=1 ./scripts/dev-invite.sh
```

## Architecture & Development

See `AGENTS.md` for project rules and context-loading guidelines.

Canonical architecture: [`docs/architecture/YOMI_ARCHITECTURE.md`](docs/architecture/YOMI_ARCHITECTURE.md)

Agent workflow docs: [`docs/agent/README.md`](docs/agent/README.md)
