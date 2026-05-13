# Yomi Security Invariants

These are non-negotiable. Read this file before modifying auth, sessions, user data, admin, AI provider calls, import/export, or database migrations.

## Secrets

- User AI API keys are never stored in plaintext.
- API keys are encrypted with AES-GCM or an equivalent authenticated encryption scheme.
- The encryption key is derived from the user's password and per-user salt.
- The derived encryption key exists only in process memory for active sessions.
- Logout and session expiry remove the session's cached encryption key.
- Password change re-encrypts secrets in one transaction.
- Admin password reset cannot recover encrypted secrets and must mark user AI keys as requiring re-entry.
- No global provider API key exists in v1.

## Authentication

- Public signup is disabled.
- Registration requires a valid invite code.
- Passwords are hashed with Argon2id.
- Login is rate-limited per IP and account.
- Session IDs are random opaque tokens stored server-side.
- Session cookies are httpOnly; secure when behind HTTPS; SameSite=Strict.
- Session rotation occurs on login.
- Logout revokes the server-side session.

## CSRF

- All POST/PUT/PATCH/DELETE endpoints require CSRF verification.
- SameSite cookies are defense-in-depth, not the only CSRF control.
- Frontend API client attaches the CSRF header for mutating requests.

## Authorization and data isolation

- Every user-owned table has a `user_id` foreign key.
- Every query over user-owned data is scoped by authenticated `user_id`.
- Admin-only endpoints use a separate admin dependency.
- Admin routes must not expose user review history, saved sentences, user content, or decrypted secrets.
- `is_admin` controls admin permissions; no route should infer admin status from username or invite history.

## Database and input safety

- Use ORM/query-builder parameters or bound SQL parameters only.
- No raw SQL string interpolation.
- Pydantic validates every request body.
- Import/export validates ownership and schema.
- Migrations are forward-only and must preserve user data unless explicitly destructive and documented.

## Browser/client safety

- Do not use `dangerouslySetInnerHTML` with user-supplied content.
- Set CSP and standard security headers through nginx/backend as appropriate.
- Do not store session tokens in localStorage.
- Do not expose encrypted secret material unnecessarily to the client.

## AI gateway safety

- AI calls are per-user, opt-in, and rate-limited.
- The backend decrypts the API key only for the duration of the provider call.
- AI output is validated against a schema before use.
- AI scores are proposals, not final ratings.
- Review history stores both AI score and final user rating when relevant.
