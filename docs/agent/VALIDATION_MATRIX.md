# Yomi Validation Matrix

Use this to decide what checks must pass before a milestone or phase can be marked complete.

## Global checks

Run these whenever they exist:

- `docker compose config`
- `make test`
- `make lint`
- `make typecheck`

If a target does not exist yet, the current phase should either create it or explicitly record why it is deferred.

## Python local checks

Prefer `uv` for host-side Python commands because a `python` executable may not exist on developer machines:

- `uv run pytest`
- `uv run python -m compileall yomi tests`

If `uv` is unavailable, use:

- `python3 -m pytest`
- `python3 -m compileall yomi tests`

Container validation remains valid source of truth:

- `docker compose run --rm backend python -m pytest`

## Phase gates

| Phase | Required validation |
|---|---|
| 0 Repo scaffold | Repo layout exists; `AGENTS.md` installed; docs in place; empty app can be built or stubs explain missing implementation. |
| 1 Foundation | Compose config valid; frontend and backend containers build/start; health endpoint works; content/user DB connections initialize with WAL pragmas; nginx routes `/api` and frontend. |
| 2 Auth & Multi-user | Invite registration, login, logout, password change, session revocation, CSRF rejection, rate limits, audit logs, encrypted API-key storage tests. |
| 3 Content & SRS | Ingestion produces searchable content DB; grammar/vocab pages render; FSRS review updates due dates/history; self-rating review works; furigana/TTS smoke tests. |
| 4 AI Layer | Provider settings save encrypted keys; connectivity test works; AI evaluation returns schema-valid result; review override stores AI score and final rating separately; rate limits enforced. |
| 5 Advanced Features | Parser returns tokens/readings; parse tree renders; conjugation map handles irregulars; quiz mode records attempts; sentence library ownership tests. |
| 6 Polish & Release | Backup works; import/export works; account deletion cascades correctly; reset-password key-loss flow works; dependency/license audit; deployment docs complete; security review complete. |

## Security tests to add early

- Unauthenticated access to protected endpoints returns 401.
- Mutating request without CSRF returns 403.
- User A cannot read/update/delete User B's data.
- Non-admin cannot access admin endpoints.
- Suspended user cannot authenticate or use protected routes.
- Encrypted API keys are not plaintext in DB.
- Password reset makes old encrypted secrets unusable and prompts re-entry.

## Manual smoke checklist

- Bootstrap first admin.
- Generate invite.
- Register normal user with invite.
- Login as normal user.
- Add one content card.
- Complete one review.
- Logout.
- Login again.
- Verify progress persists.
- Verify admin sees user but not user content/secrets.
