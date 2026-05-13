# Phase 6 ExecPlan — Polish and Release

## Purpose

Bring Yomi from daily-driveable prototype to v1.0 release: Tatoeba ingestion, import/export, account deletion, password-reset key-loss flow, FSRS optimization, performance review, security review, deployment docs, screenshots, and AGPL compliance.

## Source context

Read:

- `AGENTS.md`
- `docs/agent/YOMI_CONTEXT_BRIEF.md`
- `docs/agent/SECURITY_INVARIANTS.md`
- `docs/agent/VALIDATION_MATRIX.md`

Consult full architecture sections:

- Section 3 Project Licensing
- Section 4 Data Sources & Licensing
- Section 9 Account Management
- Section 20 Operational Concerns
- Section 21 Build Order
- Section 23 Open Questions

## Scope

- Tatoeba ingestion and searchable sentence browser.
- User progress import/export JSON.
- Account deletion flow and cascade verification.
- Admin reset-password flow with unrecoverable-key warning.
- FSRS per-user optimizer trigger.
- Query/performance review.
- Dependency/license audit.
- Security review pass.
- README, screenshots, deployment guide for Caddy and Cloudflare Tunnel.
- `/source` link or equivalent AGPL source disclosure.
- Release checklist.

## Non-goals

- No email infrastructure.
- No TOTP 2FA in v1.
- No pitch accent, stroke order, AnkiConnect, Yomitan export, or sentence mining unless explicitly moved from roadmap.

## Milestones

### M6.1 — Tatoeba ingestion

- Ingest/search Tatoeba locally.
- Attribute properly.
- Ensure ingestion remains reproducible and idempotent.

### M6.2 — Import/export

- Export own user progress as JSON.
- Import own backup with schema validation.
- Never export decrypted secrets.

### M6.3 — Account deletion and reset password

- Self-delete account cascades user data.
- Admin reset password invalidates encrypted keys and flags re-entry.
- UI warns clearly.

### M6.4 — FSRS optimizer

- Add user/admin-triggered optimization when enough review history exists.
- Store per-user parameters.
- Provide safe fallback to defaults.

### M6.5 — Performance and query review

- Check indexes for due cards, history, sessions, audit, daily activity, content search.
- Review slow routes with realistic fixture data.

### M6.6 — Security review

- Run dependency audit.
- Review auth/session/CSRF/secrets/admin/user-scope code.
- Confirm logs do not leak secrets.
- Confirm source disclosure path.

### M6.7 — Release docs

- README with setup and screenshots.
- Caddy guide.
- Cloudflare Tunnel guide.
- Backup/restore guide.
- License and attribution docs.
- CHANGELOG v1.0.

## Done when

- Fresh install can bootstrap admin, ingest content, start stack, invite user, run review, configure AI, export data, and back up DB.
- Security and dependency audits are complete or documented with accepted risks.
- AGPL/source disclosure and data-source attributions are present.
- v1.0 release checklist is satisfied.

## Verification gate

```bash
make test
make lint
make typecheck
docker compose --profile tools run --rm ingestion
docker compose build
docker compose up -d
curl -fsS http://localhost:8888/api/health
make backup
# manual release smoke checklist from VALIDATION_MATRIX.md
docker compose down
```

## Security considerations

This phase must test destructive flows carefully. Account deletion and import/export are high-risk for data loss and data leakage. Admin reset-password must not imply secret recoverability.

## Decision log

Record implementation decisions here.
