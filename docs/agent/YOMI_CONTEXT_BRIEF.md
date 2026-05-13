# Yomi Context Brief

This is the compressed context agents should load before phase work. The canonical source remains `docs/architecture/YOMI_ARCHITECTURE.md`.

## Product

Yomi is a self-hosted, invite-only, multi-user Japanese learning platform for small homelab-style deployments. It combines local grammar/vocabulary/kanji content, SRS review, sentence analysis, and optional AI-powered production feedback.

Core differentiator: traditional SRS tools mostly test recognition or constrained answers; Yomi should support free-form Japanese sentence production with AI feedback on grammar, particles, conjugation, and naturalness. AI is optional and advisory.

## Stack

- Frontend: Next.js 15, TypeScript, Tailwind CSS, shadcn/ui, React Query, Zustand.
- Backend: FastAPI, Pydantic, SQLModel/SQLAlchemy, server-side sessions, CSRF middleware, rate limiting.
- Data: two SQLite databases in one persistent Docker volume.
  - `content.db`: static, reproducible, read-only at runtime.
  - `user.db`: dynamic, irreplaceable, backed up.
- Ingestion: one-time tool profile that downloads and populates `content.db`.
- Reverse proxy: nginx inside Compose; TLS provided by Caddy or Cloudflare Tunnel in front.
- SRS: FSRS via `py-fsrs`, FSRS-primary from v1.
- AI abstraction: LiteLLM gateway with per-user provider settings and encrypted per-user API keys.
- Deployment: Docker Compose, AGPL v3, self-hosted only.

## Content sources

Yomi uses open/redistributable Japanese datasets: Hanabira Japanese Content, JMDict, KANJIDIC2, KRADFILE/RADKFILE, Tatoeba, and bunpou/japanese-grammar-db. Ingestion downloads sources rather than rebundling them. Attribution goes in About, relevant footers, and `LICENSES.md`.

## Security model

Primary risk: stolen `user.db` or backups exposing paid API keys. Per-user API keys must be encrypted at rest using a key derived from that user's password. The server caches the derived key only for active sessions. Password resets make encrypted API keys unrecoverable and require the user to re-enter them.

Auth uses invite-only registration, Argon2id password hashing, server-side sessions in `user.db`, httpOnly secure sameSite cookies, CSRF protection on mutating requests, rate limits, account lockout, audit logs, and user-id scoped queries.

Admins may manage users/invites/instance settings and view high-level audit events. They must not have a route to read user content, review history, saved sentences, or API keys.

## Database architecture

Use SQLite with WAL mode. `content.db` and `user.db` are separate to avoid write-lock contention and separate reproducible static content from irreplaceable user state.

Important tables in `user.db`: users, sessions, invites, user_secrets, user_settings, audit_log, instance_settings, srs_cards, review_history, lesson_completions, quiz_attempts, saved_sentences, daily_activity.

Important runtime pragmas: WAL, synchronous=NORMAL, foreign_keys=ON, cache_size=-32000.

## Backend routers

- `/api/auth`: csrf-token, register, login, logout, password change, sessions, delete own account.
- `/api/grammar`, `/api/vocab`, `/api/kanji`: content lookup.
- `/api/srs`: due cards, card creation, review submission.
- `/api/quiz`: quiz generation/evaluation.
- `/api/progress`: summary, heatmap, weak points.
- `/api/ai`: evaluate, explain, translate, provider status.
- `/api/parser`: parse, furigana, romaji.
- `/api/sentences`: search/save.
- `/api/settings`: user preferences and encrypted API key operations.
- `/api/export`: own data export/import.
- `/api/admin`: user/invite/audit/instance/stats management.

Authenticated JSON envelope:

```json
{ "data": { }, "error": null }
```

Mutating endpoints require `X-CSRF-Token` matching the CSRF cookie.

## Frontend requirements

- English-only v1.
- Single dark gothic theme using CSS variables; no theme picker.
- Always-on furigana everywhere Japanese text with kanji is displayed.
- Auth pages: login, invite registration, password change, logout.
- Dashboard: progress heatmap, grammar completion, SRS health, accuracy, streak, weak points.
- Review UI: keyboard-first, one card at a time, self-rating fallback, AI advisory feedback with override.
- Parse tree: left-to-right, POS-colored, hover lookup, simple renderer for v1.
- TTS: browser Web Speech API only.
- PWA manifest from day one.

## Build phases

0. Repo scaffold and agent workflow.
1. Foundation: Compose, nginx, ingestion starter, DB skeleton, FastAPI/Next skeleton, theme/nav/PWA.
2. Auth and multi-user: schemas, invite registration, sessions, CSRF, rate limits, crypto service, auth pages, admin skeleton.
3. Core content and SRS: grammar/vocab browsers, furigana/TTS, FSRS scheduling, self-rating review, conjugation engine, progress dashboard.
4. AI layer: LiteLLM gateway, encrypted key flow, provider settings, AI evaluation, one-tap override.
5. Advanced features: parser, parse tree, conjugation map, quiz mode, sentence library, extra AI features, KANJIDIC2 browser.
6. Polish/release: Tatoeba ingestion, import/export, account deletion, admin reset-password, FSRS optimizer, performance/security review, docs, public AGPL release.
