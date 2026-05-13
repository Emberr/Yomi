# AGENTS.md — Yomi Repository Instructions

This file is intentionally concise. It is the always-loaded agent guide. For detailed requirements, read only the referenced phase/context files needed for the current task.

## Project summary

Yomi is a self-hosted, multi-user Japanese language learning platform. It uses FastAPI, Next.js, SQLite, Docker Compose, FSRS scheduling, local content ingestion, and optional per-user BYO AI provider configuration. The project is AGPL v3 and security-first.

Canonical architecture: `docs/architecture/YOMI_ARCHITECTURE.md`.
Agent context index: `docs/agent/README.md`.

## Context-loading rule

Do not load the full architecture document for every task. First read:

1. `docs/agent/YOMI_CONTEXT_BRIEF.md`
2. The current phase ExecPlan under `docs/agent/phases/`
3. Any focused invariant file referenced by that phase, especially `docs/agent/SECURITY_INVARIANTS.md`

Read `docs/architecture/YOMI_ARCHITECTURE.md` only when the current phase file explicitly points to a section, or when implementation details are missing from the compressed context.

## Working mode

For complex tasks, first produce or update an ExecPlan. Then implement in small, verifiable milestones. Do not attempt to build all of Yomi in one pass.

Every implementation step must end with:

- files changed summary
- tests/checks run
- unresolved risks or decisions
- next concrete milestone

## Non-negotiable project constraints

- License all Yomi source as AGPL v3.
- No public signup in v1. Registration requires invite codes.
- All content data is local after ingestion; no runtime content API dependency.
- Per-user AI keys must be encrypted at rest with a password-derived key. Admins must not be able to read them.
- Use server-side sessions with httpOnly cookies. Do not use JWTs in localStorage.
- CSRF protection is required on mutating endpoints.
- Parameterized queries only; no SQL string interpolation.
- Every user-owned query must be scoped by authenticated `user_id`.
- Admin endpoints must use a separate admin dependency/check.
- AI scoring is advisory. Users must be able to override it.
- Avoid background AI work requiring decrypted user API keys.

## Suggested repo conventions

If the repository is empty, scaffold toward this layout unless a phase file says otherwise:

```text
yomi/
  frontend/      Next.js 15, TypeScript, Tailwind, shadcn/ui
  backend/       FastAPI, SQLModel/SQLAlchemy, Pydantic, pytest
  ingestion/     one-shot content ingestion scripts
  nginx/         reverse proxy config
  deploy/        Caddy/Cloudflare deployment docs
  docs/          architecture, agent docs, security, decisions
```

Create `Makefile` targets as soon as possible:

- `make dev`
- `make test`
- `make lint`
- `make typecheck`
- `make bootstrap`
- `make backup`

If a command cannot be implemented yet, create a stub that fails clearly and update it in the relevant phase.

## Verification expectations

Use the narrowest relevant checks during work, then run the phase gate before declaring a phase complete. Preferred checks once available:

- `docker compose config`
- backend tests: `pytest` or project-specific equivalent
- frontend checks: typecheck, lint, unit tests if configured
- migration/smoke tests for database changes
- security-specific tests for auth, CSRF, session, crypto, and user scoping

Do not claim a phase is complete unless the phase ExecPlan's “Done when” and “Verification gate” sections are satisfied.

## Dependency policy

Prefer well-maintained, permissively licensed dependencies compatible with AGPL distribution. Before adding a production dependency, record:

- purpose
- license
- why the dependency is needed instead of standard library/local code
- security or operational implications

## UX constraints

The v1 UI is English-only, dark gothic only, and has always-on furigana wherever Japanese text containing kanji is displayed. No theme picker or i18n scaffolding in v1 unless explicitly moved into scope.

## Security review trigger

When modifying auth, session, CSRF, password handling, secret storage, admin permissions, user scoping, AI-provider calls, import/export, or database migrations, read `docs/agent/SECURITY_INVARIANTS.md` before coding and add/update tests for the invariant touched.
