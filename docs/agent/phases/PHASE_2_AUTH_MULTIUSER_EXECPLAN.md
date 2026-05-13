# Phase 2 ExecPlan — Authentication and Multi-User Core

## Purpose

Implement secure invite-only multi-user account management: users, invites, sessions, CSRF, password hashing, encrypted API-key storage, audit logging, and admin skeleton.

## Source context

Read:

- `AGENTS.md`
- `docs/agent/YOMI_CONTEXT_BRIEF.md`
- `docs/agent/SECURITY_INVARIANTS.md`
- `docs/agent/VALIDATION_MATRIX.md`

Consult full architecture sections:

- Section 5 Threat Model & Security Principles
- Section 9 Authentication & Account Management
- Section 10 Secrets Handling
- Section 17 Database Schemas
- Section 18 API Contract

## Scope

- `users`, `sessions`, `invites`, `user_secrets`, `user_settings`, `audit_log`, `instance_settings` tables/migrations.
- Bootstrap admin CLI.
- Invite generation/redemption.
- Register/login/logout/logout-everywhere/change-password/session list/revoke.
- Server-side session middleware.
- CSRF middleware and frontend client token handling.
- Rate limiting for auth endpoints.
- Argon2id password hashing.
- Password-derived encryption key service and AES-GCM secret storage.
- Admin panel skeleton for users, invites, audit.

## Non-goals

- Do not implement full SRS/content features.
- Do not implement real AI provider calls yet.
- Do not add email password recovery in v1.
- Do not expose user content to admins.

## Milestones

### M2.1 — User DB migrations

Create migrations/models for users, sessions, invites, user_secrets, user_settings, audit_log, and instance_settings.

### M2.2 — Password hashing and bootstrap admin

- Implement Argon2id hashing/verification.
- Implement `python -m yomi.bootstrap_admin`.
- First admin can generate invites.

### M2.3 — Session middleware

- Opaque session tokens stored in `sessions` table.
- httpOnly cookie behavior.
- Session rotation on login.
- Session revocation on logout.
- Current-user dependency.

### M2.4 — CSRF and rate limits

- CSRF endpoint issues token.
- Mutating endpoints reject missing/invalid token.
- Login and registration are rate-limited.
- Account lockout after repeated failures.

### M2.5 — Invite registration and auth frontend

- Register-with-invite flow.
- Login/logout UI.
- Session check on app load.
- Auth-aware API client.

### M2.6 — Crypto service and secret storage

- Derive per-user encryption key from password and `enc_salt`.
- Cache key by session ID.
- Store provider API keys in `user_secrets` encrypted with AES-GCM.
- Drop plaintext immediately after use.
- Password change decrypts/re-encrypts secrets in one transaction.

### M2.7 — Admin skeleton and audit log

- Admin user list, invites, high-level audit log.
- Admin-only dependency.
- Audit events for login success/failure, password change, invite creation/redemption, role changes, suspension/deletion.

## Done when

- Normal user can register via invite, login, logout, and change password.
- Admin can create invites and view high-level admin screens.
- CSRF protection rejects mutating requests without token.
- User secrets are encrypted in DB and cannot be decrypted without active session key.
- Tests cover user isolation and admin restrictions.

## Verification gate

```bash
make test
make lint
make typecheck
docker compose build
docker compose up -d
# manual/API smoke: bootstrap admin, create invite, register user, login, logout
docker compose down
```

Add automated tests for:

- unauthenticated protected route = 401
- missing CSRF on mutating route = 403
- non-admin admin route = 403
- encrypted API key not plaintext in DB
- password change re-encrypts keys
- password reset marks secrets as unrecoverable/re-entry needed

## Security considerations

This phase is security-critical. Do not skip tests. Do not use JWT localStorage. Do not use server-wide encryption keys for user API keys.

## Decision log

Record implementation decisions here.
