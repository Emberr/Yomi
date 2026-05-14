# Contributing

Yomi is AGPL v3 licensed, Docker-native, and security-first.

## Phase & Scope

Yomi is implemented incrementally by phase. Current status: **Phases 1–3 substantially complete**. Before contributing:

1. Read `AGENTS.md` for project rules and context-loading guidelines.
2. Read the active phase plan under `docs/agent/phases/` to understand scope and non-goals.
3. Preserve phase boundaries — do not implement features from future phases.

## Non-Negotiable Constraints

- **License**: All source code is AGPL v3. No proprietary or incompatible dependencies.
- **No public signup**: Registration requires invite codes. Admins do not have signup authority.
- **Local-first content**: All content data is local after ingestion; no runtime content API dependency.
- **Encrypted secrets**: Per-user AI keys are encrypted at rest with password-derived keys. Admins cannot decrypt them.
- **Sessions over JWTs**: Server-side sessions with httpOnly cookies. No JWTs in localStorage.
- **User scoping**: Every user-owned query is scoped by authenticated `user_id`.
- **Admin isolation**: Admin endpoints use separate admin dependency/check.
- **No background AI work**: Avoid background tasks requiring decrypted user API keys.
- **CSRF protection**: All mutating endpoints require valid CSRF tokens.
- **Parameterized queries**: No SQL string interpolation.

When these constraints are touched (auth, sessions, secrets, user data, admin, AI keys, imports/exports, migrations), read `docs/agent/SECURITY_INVARIANTS.md` before coding and add/update tests for the invariant.

## Dependencies

Before adding a production dependency, document in the relevant phase file or `DEPENDENCIES.md`:

- **Purpose**: What problem does this solve?
- **License**: Is it compatible with AGPL v3?
- **Why not stdlib/local**: Why not implement this ourselves?
- **Security & ops**: Any security or operational implications?

## Development Workflow

### Setup

```bash
# Backend (Python 3.12+)
cd backend
(uv || python3) -m pip install -e '.[dev]'  # or use pyproject.toml

# Frontend (Node 20+)
cd frontend
npm install

# Run all checks
make lint typecheck test
```

### Commit & Push

- Commits should be atomically sound — each commit should pass tests and lint.
- Use conventional commits when possible (e.g., `feat: add grammar API`, `fix: CSRF token validation`).
- Reference phase files and security invariants in PR descriptions.

### Testing

Tests are required for:

- Auth, sessions, CSRF, passwords, crypto
- User-scoped queries
- Admin endpoints
- SRS scheduling logic
- Content ingestion
- Database migrations

Run tests locally before pushing:

```bash
make test
```

Containerized tests (source of truth) run in CI:

```bash
docker compose run --rm backend python -m pytest
docker compose run --rm ingestion python -m pytest
```

## Security Review

Pull requests touching auth, sessions, CSRF, password handling, secret storage, admin permissions, user scoping, AI-provider calls, imports/exports, or database migrations require review against `docs/agent/SECURITY_INVARIANTS.md`.
