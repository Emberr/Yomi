# Security Policy

Yomi is security-first and self-hosted. Current status: Phases 1–3 substantially complete. The application now includes invite-only authentication, server-side sessions, CSRF protection, encrypted per-user secret storage, user-scoped data access, grammar/vocabulary content ingestion, and FSRS-based review flows.

## Security Model

The project follows the non-negotiable invariants documented in [docs/agent/SECURITY_INVARIANTS.md](docs/agent/SECURITY_INVARIANTS.md). In short:

- public signup is disabled and registration requires a valid invite code;
- sessions are opaque server-side tokens stored in httpOnly cookies;
- all mutating endpoints require CSRF verification;
- per-user AI keys are encrypted at rest with a password-derived key;
- every user-owned query must be scoped by authenticated `user_id`;
- admin routes use separate authorization checks and must not expose user secrets or review history;
- SQL must use parameters only, never string interpolation.

## Reporting Issues

If you believe you have found a security issue, please document the affected endpoint, account state, and reproduction steps as precisely as possible. For security-sensitive code changes, review the invariant file before implementing or reviewing the patch.

Future security-sensitive work must follow `docs/agent/SECURITY_INVARIANTS.md`.
