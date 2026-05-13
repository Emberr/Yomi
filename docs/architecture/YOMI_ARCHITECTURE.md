# Yomi — Architecture Document
> *Yomi (読み / 黄泉) — "reading" and "the underworld" in Japanese. A name that holds duality: the act of learning to read, and the mythological realm beyond the threshold. You are always crossing a door.*

**Version:** 0.3 — Multi-user, security-first, AGPL, FSRS-primary
**Status:** Pre-build planning, architecture finalised
**Target:** Self-hosted multi-user instance behind HTTPS, Docker-native, AGPL v3

---

## Table of Contents

1. [Project Vision](#1-project-vision)
2. [Name & Aesthetic Direction](#2-name--aesthetic-direction)
3. [Project Licensing](#3-project-licensing)
4. [Data Sources & Licensing](#4-data-sources--licensing)
5. [Threat Model & Security Principles](#5-threat-model--security-principles)
6. [Database Architecture — The Full Reasoning](#6-database-architecture--the-full-reasoning)
7. [System Architecture Overview](#7-system-architecture-overview)
8. [Service Breakdown](#8-service-breakdown)
9. [Authentication & Account Management](#9-authentication--account-management)
10. [Secrets Handling — API Key Encryption](#10-secrets-handling--api-key-encryption)
11. [Data Flow Diagrams](#11-data-flow-diagrams)
12. [AI Layer — Provider Abstraction](#12-ai-layer--provider-abstraction)
13. [SRS Engine](#13-srs-engine)
14. [Feature Specification](#14-feature-specification)
15. [Docker Compose — Full Stack](#15-docker-compose--full-stack)
16. [Directory Structure](#16-directory-structure)
17. [Database Schemas](#17-database-schemas)
18. [API Contract](#18-api-contract)
19. [Frontend Architecture](#19-frontend-architecture)
20. [Operational Concerns](#20-operational-concerns)
21. [Build Order](#21-build-order)
22. [Post-v1.0 Roadmap](#22-post-v10-roadmap)
23. [Open Questions](#23-open-questions)

---

## 1. Project Vision

Yomi is a self-hosted, multi-user Japanese language learning platform. It is not a clone of Bunpro or Hanabira — it is a ground-up rebuild that takes the best data and features from the open-source ecosystem and adds an AI evaluation layer that none of them have.

**Core principles:**
- **Open source, copyleft.** AGPL v3. Network use counts as distribution, so any modified version running on a server must offer its source to its users. Yomi exists in service of the open-source language-learning ecosystem, not as a stepping stone to a closed-source product.
- **Multi-user, single-instance.** One Yomi instance hosts multiple learners. The operator (admin) runs it on their homelab and invites others. There is no SaaS plan, no central server — every instance is self-hosted.
- **Invite-only.** No public signup. The admin generates invite codes; users register against them. This is appropriate for the "host it on Ignis for friends" use case and removes a whole class of abuse.
- **Bring your own AI.** Each user supplies their own API keys, encrypted at rest with a key derived from their password. The admin cannot read user API keys. There is no shared AI proxy.
- **Security is a first-class concern.** Argon2id for password hashing, server-side sessions with httpOnly cookies, CSRF tokens on state-changing requests, rate limiting on auth and AI endpoints, audit logging of sensitive operations. See Section 5.
- **All content data is local.** No runtime API calls for grammar, vocabulary, or kanji content. Works fully offline once content is ingested.
- **AI is opt-in and provider-agnostic.** Works without it; becomes significantly more powerful with it.
- **Lightweight.** No bundled large models. Tokenization is small, fast Python. TTS uses the browser.
- **The interface reflects its design — refined, dark, deliberate.**
- **Docker-native.** Slots into an existing homelab. Single `docker compose up -d` to run.

**What sets it apart from Hanabira:**
Hanabira is a good content platform with a functional SRS. Yomi's differentiator is the AI evaluation loop: free-form sentence production, not fill-in-the-blank, with real feedback on particle use, conjugation correctness, and naturalness. This is the gap between recognition and production — the gap that traditional SRS tools cannot close.

---

## 2. Name & Aesthetic Direction

**Yomi** (読み / 黄泉)

The kanji 読み means "reading" or "recitation" — the act of learning. The homophone 黄泉 is Yomi, the Japanese underworld in Shinto mythology — the realm beyond the threshold, dark and ancient. The name holds both meanings simultaneously.

**Aesthetic:** Gothic, minimal, dark. Think illuminated manuscript meets terminal. Deep blacks, off-whites, muted golds. No neon, no anime-bright. The kind of interface that feels like a private library at 2am.

**UI language:** English only. No internationalization scaffolding in v1.

**Theme:** The dark gothic theme is the only theme. CSS variables exist for cleanliness of the codebase, not for customization — there is no theme picker in settings.

**Logo direction:** A torii gate silhouetted against a pale moon, or a single vertical stroke of kanji dissolving into shadow.

---

## 3. Project Licensing

**Code:** GNU Affero General Public License v3.0 (AGPL v3). All Yomi source code, Docker configurations, scripts, frontend, backend, and documentation are AGPL v3.

**Why AGPL over MIT or GPL v3:**

- GPL v3 has the *ASP loophole*: anyone could fork Yomi, modify it, run the modified version as a hosted service, and never release their changes — because they never "distributed" the binary, they just served it over a network. AGPL closes this. Any modified Yomi running on any server must offer its source to the users of that server.
- MIT lets a downstream actor close the source of a fork entirely. That is at odds with the project's purpose.
- AGPL is the right license for software designed to be served over a network to other people.

**Practical implications:**

- Anyone running a modified Yomi on a public server must provide a way for users to obtain its source. A `/source` link in the footer pointing to the running version's commit is enough.
- Any modifications must themselves be AGPL v3 (or compatible).
- AGPL is compatible with GPL v3 (via explicit cross-licensing clauses in both licenses).
- All bundled Python and JavaScript dependencies must be AGPL-compatible. The chosen stack (FastAPI/MIT, Next.js/MIT, py-fsrs/MIT, fugashi/MIT, LiteLLM/MIT, pwdlib/MIT, pykakasi/GPL-3.0, etc.) is fully compatible — MIT and GPL v3 can both be combined with AGPL v3.

**Bundled content:** Each data source retains its original license (see Section 4). The ingestion script downloads sources at first run rather than re-bundling them in the repository.

**User data:** The user owns their own data. Each user can export their own progress as JSON via the settings UI. The admin can export aggregate data for backup but not per-user secrets (those are encrypted).

**Contributions:** By submitting a PR, contributors agree to license their contribution under AGPL v3. Standard.

---

## 4. Data Sources & Licensing

All content data is sourced from open, redistributable datasets. No scraping. No runtime dependency on external services for content.

| Source | What it provides | License | Format |
|---|---|---|---|
| **Hanabira Japanese Content** | Grammar points N5–N1, example sentences, verb/adjective sentence banks | CC BY-SA 4.0 (credit required) | JSON |
| **JMDict** (via jmdict-simplified) | Full Japanese-English dictionary, 200k+ entries | EDRDG License (attribution + share-alike, behaves like CC BY-SA) | JSON |
| **KANJIDIC2** | 13,108 kanji with stroke counts, grades, JLPT levels, readings | CC BY-SA 4.0 | XML → JSON |
| **KRADFILE / RADKFILE** | Kanji component/radical decomposition | EDRDG License (commercial use permitted with attribution) | Text → JSON |
| **Tatoeba** | Hundreds of thousands of real example sentences | CC BY 2.0 FR | CSV/SQLite |
| **bunpou/japanese-grammar-db** | Grammar references from Tae Kim and Imabi | MIT | JSON |

All attributions appear in the app's About page, the per-page data-acknowledgement footer where relevant, and the repo's `LICENSES.md`.

**JLPT levels note:** The JLPT organization has not published an official vocabulary or grammar list since the test was redesigned in 2010. Every JLPT-tagged dataset is an unofficial reconstruction. Yomi treats JLPT tags as a useful heuristic, not as ground truth, and surfaces source-of-tag where useful (`jlpt_source` column).

---

## 5. Threat Model & Security Principles

Yomi is a homelab application hosted by one admin for a small group of users. The threats it defends against, in order of priority:

1. **Theft of API keys via stolen database.** A user's API key has direct monetary cost and grants access to LLM accounts. Database backups, accidentally committed files, and compromised SQLite files must not expose keys in plaintext. → API keys are encrypted at rest with a key derived from each user's password. Keys are unreadable without an active login.

2. **Account takeover via credential attacks.** → Argon2id password hashing with sensible parameters. Rate limiting on `/auth/login`. Account lockout after repeated failures. Strong password requirements at registration (zxcvbn-validated). Optional TOTP 2FA (post-v1).

3. **Session hijacking.** → Server-side sessions stored in the database, identified by an opaque random session ID delivered as an `httpOnly, secure, samesite=strict` cookie. No JWTs in localStorage. Sessions rotate on login. Logout invalidates the session server-side.

4. **CSRF on state-changing actions.** → Synchronizer-token-pattern CSRF tokens, validated on all POST/PUT/PATCH/DELETE. Same-site cookies as a defense-in-depth layer.

5. **Cross-user data leakage.** → All user data tables have a `user_id` FK. Every query is filtered by the authenticated user's ID via a single shared dependency. There is no "admin viewing your data" path — admins can manage users but cannot see review history, sentences, or API keys.

6. **Injection.** → Parameterized queries everywhere. SQLModel/SQLAlchemy for ORM (no raw string interpolation). Pydantic for input validation on every endpoint.

7. **XSS.** → React escapes by default; we never use `dangerouslySetInnerHTML` with user-supplied content. CSP headers set.

8. **DoS via expensive AI calls.** → Rate limit on `/api/ai/*` per user (configurable). Background queue is not used; AI is synchronous within a request, so request timeouts cap exposure.

9. **Privilege escalation.** → Single `is_admin` flag. Admin-only endpoints check it via a separate dependency. Admin actions logged to `audit_log`.

10. **Audit & forensics.** → All login attempts (success/failure), password changes, API key changes, invite generation/redemption, role changes, and account deletions are logged with timestamp, IP, and user agent.

**Explicit non-goals:**

- Yomi does not defend against an attacker who has root on the host. The encryption-at-rest design protects against database theft, not against an attacker who can read the running process's memory.
- Yomi does not defend against compromised AI providers. If a user's chosen LLM provider is malicious, no protection on Yomi's side helps.
- Yomi does not protect against the admin going rogue. The admin owns the server. Users who want stronger guarantees should self-host their own instance.

---

## 6. Database Architecture — The Full Reasoning

### Why not MongoDB (like Hanabira)?

Hanabira chose MongoDB because it's a multi-user platform that needs to scale horizontally. Yomi is multi-user but small-scale — dozens of users, not thousands. MongoDB adds a ~600MB container, a separate server process, and operational complexity we don't need.

### Why SQLite for multi-user?

SQLite handles low-concurrency multi-user workloads fine with WAL mode enabled. For a homelab instance with ~10–50 users, peak write concurrency is one or two transactions per second. SQLite handles that without breaking a sweat. The full content corpus is under 200MB. User data (even with 50 active users) is under 100MB.

If the instance ever genuinely outgrows SQLite — which is unlikely — migration to PostgreSQL is a Phase-N concern, not a v1 concern.

### Two SQLite databases, one persistent volume

```
/data/
  content.db    ← static, populated once by ingestion script, read-only at runtime
  user.db       ← dynamic, all user state for all users
```

- `content.db` is reproducible — if it gets corrupted, run the ingestion script again.
- `user.db` is irreplaceable — it contains all users' learning history, accounts, and encrypted secrets. Backup target.
- Read/write patterns differ. Separating them avoids SQLite write-lock contention affecting content reads.

### SQLite operational settings

At first connection both databases are opened with:
- `PRAGMA journal_mode=WAL;`
- `PRAGMA synchronous=NORMAL;`
- `PRAGMA foreign_keys=ON;`
- `PRAGMA cache_size=-32000;`

Explicit indexes (in addition to FTS5):
- `srs_cards(user_id, due) WHERE suspended=0` — the daily review query
- `srs_cards(user_id, card_type, due)`
- `vocab_items(jlpt_level, frequency)`
- `example_sentences(grammar_tags)`
- `review_history(card_id, reviewed_at)`
- `sessions(id)` and `sessions(user_id)`
- `audit_log(user_id, timestamp)`
- `daily_activity(user_id, date)`

---

## 7. System Architecture Overview

```
                ┌────────────────────────────────────────┐
                │             PUBLIC INTERNET            │
                └─────────────────┬──────────────────────┘
                                  │ HTTPS
                  ┌───────────────▼───────────────┐
                  │   Caddy / Cloudflare Tunnel    │
                  │   TLS termination + headers    │
                  └───────────────┬───────────────┘
                                  │
                  ┌───────────────▼───────────────┐
                  │           NGINX               │
                  │  Reverse Proxy + Rate Limit   │
                  └─────────┬──────────┬──────────┘
                            │          │
              ┌─────────────▼──┐    ┌──▼─────────────────────┐
              │   FRONTEND     │    │       BACKEND          │
              │   Next.js 15   │    │   FastAPI (Python)     │
              │   :3000        │    │   :8000                │
              └────────────────┘    │  - Auth middleware     │
                                    │  - CSRF middleware     │
                                    │  - Rate limiter        │
                                    │  - SRS engine (FSRS)   │
                                    │  - AI gateway          │
                                    │  - Parser              │
                                    │  - Crypto service      │
                                    └─────────┬──────────────┘
                                              │
                                    ┌─────────▼─────────┐
                                    │    SQLite DBs      │
                                    │    content.db      │
                                    │    user.db (WAL)   │
                                    └─────────┬─────────┘
                                              │ (optional, external)
                                    ┌─────────▼──────────────────┐
                                    │      AI PROVIDERS          │
                                    │  Per-user, BYO API keys    │
                                    │  OpenRouter / Anthropic /  │
                                    │  OpenAI / Ollama / Custom  │
                                    └────────────────────────────┘
```

**TLS:** Either Caddy with automatic Let's Encrypt or a Cloudflare tunnel terminates TLS. Yomi itself doesn't ship a TLS cert — the operator provides it. Documented in deployment guide.

**Tailscale option:** For installs where the operator doesn't want public exposure, the entire stack works behind Tailscale with no other changes. Cookies use `secure` only if Yomi is told it's behind HTTPS (env var).

---

## 8. Service Breakdown

### 8.1 nginx (Reverse Proxy)

- Routes `/api/*` → FastAPI backend (:8000)
- Routes `/*` → Next.js frontend (:3000)
- Handles gzip compression and static asset caching
- Sets security headers: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, a strict `Content-Security-Policy`
- Per-IP request rate limit as a backstop in front of FastAPI

### 8.2 frontend (Next.js 15)

- App Router, TypeScript, Tailwind CSS, shadcn/ui
- React Query (server state) + Zustand (UI state)
- Dark gothic theme via CSS variables (single theme, no picker)
- All AI calls go through the backend gateway
- Parse trees rendered as a simple left-to-right tree (D3 reserved for v1.1+)
- Audio via browser Web Speech API
- PWA manifest from day one
- Auth pages: login, register-with-invite, password change, logout
- Session check on app load redirects unauthenticated users to login

### 8.3 backend (FastAPI)

The central API. All business logic lives here.

| Router | Prefix | Auth required? | Notes |
|---|---|---|---|
| Auth | `/api/auth` | No (mostly) | login, logout, register, password change, csrf-token |
| Grammar | `/api/grammar` | Yes | Grammar point lookup, lesson flow |
| Vocabulary | `/api/vocab` | Yes | JMDict lookup |
| Kanji | `/api/kanji` | Yes | KANJIDIC lookup |
| SRS | `/api/srs` | Yes | Card scheduling, review submission |
| Quiz | `/api/quiz` | Yes | Quiz generation and answer evaluation |
| Progress | `/api/progress` | Yes | Per-user stats |
| AI | `/api/ai` | Yes | Provider-agnostic AI evaluation gateway |
| Parser | `/api/parser` | Yes | Tokenization, furigana, romaji |
| Sentences | `/api/sentences` | Yes | Tatoeba search, mining |
| Settings | `/api/settings` | Yes | Per-user preferences, AI provider config |
| Export | `/api/export` | Yes | User data export (own data only) |
| Admin | `/api/admin` | Yes + admin | User management, invite codes, audit log, instance settings |

**Services within the backend:**
- `services/auth.py` — Session management, password hashing (pwdlib + Argon2id), CSRF
- `services/crypto.py` — Per-user encryption key derivation (Argon2id KDF) and AES-GCM for API keys
- `services/srs_engine.py` — FSRS via py-fsrs (FSRS-6)
- `services/ai_gateway.py` — LiteLLM-based provider abstraction
- `services/parser.py` — `fugashi` + `pykakasi` + `cutlet`
- `services/conjugation_engine.py` — Programmatic + irregular lookup
- `services/quiz_generator.py` — Rule-based + optional AI question generation
- `services/audit.py` — Audit log writer

### 8.4 ingestion (One-time script)

Same as v0.2 — downloads, parses, populates `content.db` only. Never touches `user.db`. Run via `docker compose --profile tools run ingestion`.

---

## 9. Authentication & Account Management

### 9.1 Registration

Public signup is disabled. Registration requires a valid invite code, generated by an admin via the admin UI or CLI.

- User visits `/register?invite=<code>`
- Form: username (3–32 chars, alphanumeric + underscore), display name, password (zxcvbn score ≥ 3 required), password confirm
- Server validates invite code (exists, not used, not expired)
- Server hashes password with Argon2id (pwdlib defaults: m=65536 KiB, t=3, p=4)
- Server derives the user's encryption key from password (Section 10) and stores its salt
- User record created with `is_admin=false` unless the invite was an "admin invite"
- Invite marked used
- User is automatically logged in and gets a session cookie
- `audit_log` records `account_created` event

### 9.2 Login

- `POST /api/auth/login` with `{ username, password }`
- Rate limit: 5 attempts per IP per minute (slowapi)
- Account-level limit: after 10 failed attempts within an hour, account is locked for 15 minutes
- On success:
  - Server creates a session row in `user.db sessions` table with a random 32-byte URL-safe token as ID
  - Server derives the user's encryption key from the supplied password and stores it in an in-process session cache (TTL = session lifetime). This is what lets the backend decrypt the user's API keys for the duration of the login.
  - `Set-Cookie: yomi_session=<token>; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=...`
  - A CSRF token is issued in a separate non-httpOnly cookie for double-submit verification
  - `audit_log` records `login_success`
- On failure: `audit_log` records `login_failure` with the attempted username and IP

### 9.3 Session lifecycle

- Default session lifetime: 7 days, sliding (renewed on activity)
- Sessions stored in `user.db sessions`: `(id, user_id, created_at, expires_at, last_seen_at, ip_address, user_agent, revoked)`
- Every authenticated request:
  - Looks up session by cookie value
  - Checks `expires_at > now`, `revoked = 0`
  - Updates `last_seen_at`
  - Loads `user_id`, exposes `current_user` dependency to routers
- Logout: `POST /api/auth/logout` deletes the session row, clears cookies, drops the in-process encryption-key cache for that session, logs `logout`
- "Log out everywhere": deletes all sessions for the user

### 9.4 Password change

- Requires current password (re-authentication)
- New password validated (zxcvbn ≥ 3)
- New password hashed
- The user's encryption key changes. All encrypted API keys must be re-encrypted with the new key. This happens in a transaction within the request:
  1. Decrypt all of the user's API keys using the old key (still in session cache)
  2. Derive the new encryption key from the new password
  3. Re-encrypt all API keys with the new key
  4. Update the user's password hash and encryption-key salt
- All sessions for the user are invalidated (forces re-login on other devices)
- `audit_log` records `password_changed`

### 9.5 Admin role

The first user created (via the bootstrap CLI or first-run admin invite) is the admin. Admins can:

- Generate invite codes (single-use, optional expiry)
- View user list (username, display name, last seen, status)
- Suspend or delete users
- Promote users to admin or demote
- View `audit_log` (own actions and high-level system events; never user content)
- Configure instance-level settings (registration enabled, allowed AI providers list)

Admins cannot read user content, review history, or API keys. The encryption design makes this enforced, not policy.

### 9.6 Account deletion

Users can delete their own account from settings. Deletion:
- Removes the user row and cascades to all owned data (SRS cards, history, sentences, sessions, settings)
- Writes a final `audit_log` entry recording the deletion (the user_id is preserved as a tombstone for audit integrity but everything else is gone)
- Is irreversible

### 9.7 Lost password

There is no email-based password reset in v1.0 (no email infrastructure). If a user forgets their password:
- The admin can reset their password via the admin UI
- **But:** since the user's encryption key is derived from the password, all of that user's encrypted API keys become unrecoverable. The admin's reset sets a flag warning the user to re-enter their AI keys on next login.

This is documented prominently. The tradeoff is intentional: it's the same tradeoff a password manager makes. If you want recoverability, accept that the server can decrypt your secrets without your password.

### 9.8 Optional TOTP 2FA

Post-v1.0. The schema reserves columns for it.

---

## 10. Secrets Handling — API Key Encryption

### 10.1 Threat model

The goal is: an attacker who obtains a copy of `user.db` (via backup theft, accidental commit, server compromise without RAM access) cannot decrypt any user's API keys.

### 10.2 Design — per-user password-derived encryption

Each user has:
- A password (never stored, hashed with Argon2id for verification)
- An encryption-key salt (`enc_salt`, random 16 bytes, stored in users table)
- Encrypted API keys (one row per provider, stored in `user_secrets`)

On login, the backend derives a 32-byte encryption key from the password and `enc_salt` using Argon2id as a KDF (different parameters than password hashing: tuned for KDF). This key is cached in memory keyed by session ID.

When the user saves an API key:
1. Caller provides plaintext API key
2. Backend pulls the user's encryption key from session cache
3. Backend encrypts with AES-GCM (`nonce | ciphertext | tag`)
4. Backend stores ciphertext + nonce in `user_secrets`

When the AI gateway needs the key:
1. Backend pulls the user's encryption key from session cache
2. Backend pulls ciphertext from `user_secrets`
3. Backend decrypts, uses, immediately drops the plaintext

When the user logs out or session expires:
- The encryption key is removed from cache
- API keys remain encrypted at rest
- No background AI operations can run because no encryption key is available

### 10.3 Why this design

- **Properties:** Database theft is harmless. Admin cannot read user keys. Backups are safe.
- **Cost:** Forgotten password = lost keys (user re-enters them). Background jobs that need AI cannot run (acceptable — Yomi has none).
- **Alternative considered:** A server-side master key (env var) encrypting all keys. Simpler, but lets the admin read keys and exposes everything if the env is dumped. Rejected for "security is paramount."

### 10.4 Implementation notes

- `cryptography` library (pyca/cryptography) for AES-GCM and KDF
- KDF parameters: Argon2id, m=65536 KiB, t=3, p=4, output=32 bytes — same as pwdlib defaults but different domain separation (different salt usage)
- Nonces are random 12 bytes per encryption operation, stored alongside ciphertext
- Authenticated encryption — tampering is detected, not silently accepted
- The in-process key cache is a dict keyed by session_id, cleared on logout. Process restart drops the cache; users re-login.

### 10.5 What is NOT encrypted

- Username, display name, email if provided
- SRS cards, review history, lesson completions, quiz attempts, saved sentences, settings preferences (everything except secrets)
- This is intentional. Encrypting all user data would prevent the admin from doing anything (e.g., diagnosing a broken card) and adds significant complexity. The threat model treats this data as recoverable from backups, unlike secrets.

---

## 11. Data Flow Diagrams

### 11.1 Authenticated request flow

```
Client request with yomi_session cookie + X-CSRF-Token header
        │
        ▼
nginx (rate limit, security headers, gzip)
        │
        ▼
FastAPI middleware stack:
  1. Session lookup → user_id, encryption_key from cache
  2. CSRF validation (for POST/PUT/PATCH/DELETE)
  3. Per-user rate limit check
        │
        ▼
Router dependency: current_user, current_user_admin
        │
        ▼
Handler executes, queries scoped by user_id
        │
        ▼
Response
```

### 11.2 SRS Review Flow (FSRS)

```
User opens review session
        │
        ▼
GET /api/srs/due  (authenticated)
        │
        ▼
Backend queries user.db:
  SELECT * FROM srs_cards
  WHERE user_id = :uid AND due <= NOW() AND suspended = 0
  ORDER BY due ASC
  LIMIT settings.max_session_size
        │
        ▼
Each card shown one at a time, full keyboard control
        │
User answers
        │
    ┌───▼──────────────────────────────┐
    │  If AI enabled & key available:  │
    │  POST /api/ai/evaluate           │
    │  → fetches encrypted key,        │
    │    decrypts via session cache,   │
    │    calls provider with structured│
    │    output, returns proposed score│
    │                                  │
    │  If AI disabled or no key:       │
    │  Show model answer, user picks   │
    │  Again / Hard / Good / Easy      │
    └───┬──────────────────────────────┘
        │ FSRS rating (Again=1, Hard=2, Good=3, Easy=4)
        ▼
POST /api/srs/review with final rating
        │
        ▼
Backend: load Card from DB, feed to py-fsrs Scheduler:
  card, log = scheduler.review_card(card, rating)
        │
        ▼
Persist updated card and append log row to review_history
Update daily_activity (user_id, today)
        │
        ▼
Frontend shows result + moves to next card
```

### 11.3 AI Evaluation Flow

```
User submits free-form answer: "今ご飯をたべています"
        │
        ▼
POST /api/ai/evaluate  (authenticated, CSRF-validated)
        │
        ▼
Per-user rate limit check (default: 60 AI calls/hour)
        │
        ▼
Look up user's encryption key in session cache
        │
        ▼
Pull encrypted API key + provider config from user_secrets
Decrypt API key in memory
        │
        ▼
AI Gateway via LiteLLM:
  - Structured output mode (json_schema)
  - User-configured model + temperature
  - Plaintext key passed to provider
  - Plaintext key dropped after call
        │
        ▼
Response validated against Pydantic schema
        │
        ▼
Frontend renders:
  ✅ Correct te-form  ✅ Correct iru  ⚠️ Consider using 食べて (kanji)
  AI score: Good  [Accept]  [Override → Again/Hard/Good/Easy]
        │
        ▼
User confirms or overrides → POST /api/srs/review
review_history records both ai_score and final rating
```

---

## 12. AI Layer — Provider Abstraction

The AI gateway is a provider-agnostic abstraction layer. Each user configures their preferred provider and API key via settings. Keys are encrypted as described in Section 10.

**API keys are never shared, never centralised, never proxied through any third party.** Each user supplies their own. No global API key exists in the system.

### 12.1 Supported Providers

| Provider | Models | Notes |
|---|---|---|
| **OpenRouter** | Any model in their catalogue | Recommended default. One API key, access to many models. |
| **Anthropic** | claude-sonnet, claude-haiku | Direct API, structured outputs via tool use |
| **OpenAI** | gpt-4o, gpt-4o-mini | response_format json_schema |
| **Ollama** | Any locally-running model | User's own machine. No API key. qwen2.5:7b or llama3.1:8b recommended. |
| **Custom / OpenAI-compatible** | Any | Base URL + API key for self-hosted or custom endpoints |

The gateway uses LiteLLM internally for unified per-provider calls including their structured-output modes.

### 12.2 Per-user Provider Configuration

Stored in `user_secrets` (encrypted) and `user_settings` (plain):

```json
{
  "ai": {
    "enabled": true,
    "provider": "openrouter",
    "model": "anthropic/claude-haiku-4-5",
    "base_url": null,
    "fallback_provider": "ollama",
    "fallback_model": "qwen2.5:7b",
    "temperature": 0.3,
    "max_tokens": 500
  }
}
```

The `api_key` is stored separately in `user_secrets` as encrypted ciphertext, keyed by `(user_id, provider)`.

### 12.3 Reliability and Trust

- AI scores are proposals, not decisions. The user always has the final say with one tap.
- `review_history` records `ai_score` and final `rating` separately, plus an `ai_overridden` flag.
- Settings UI advises which models tend to perform well for Japanese grammar evaluation, with a clear warning that local 7B models hallucinate and are best used for "explain it differently" rather than grading.

### 12.4 AI Feature Map

| Feature | AI Used For | Works Without AI? |
|---|---|---|
| Free-form sentence evaluation | Core evaluation | Yes (falls back to self-rating with model answer) |
| Grammar explanation on demand | "Explain this to me differently" | No |
| Next lesson recommendation | "What should I study next?" | Yes (rule-based) |
| Sentence naturalness check | "Does this sound natural?" | No |
| Translation with breakdown | Particle-by-particle translation | No |
| Quiz question generation | Generate novel questions | Yes (pre-seeded bank) |

---

## 13. SRS Engine

### 13.1 Algorithm choice — FSRS from v1.0

v1.0 ships FSRS (Free Spaced Repetition Scheduler), via the `py-fsrs` Python package (FSRS-6 model, MIT-licensed, maintained by Open Spaced Repetition).

**Why FSRS, not SM-2:**
- Anki has had FSRS as a built-in alternative since 23.10 (2023) and the community has converged on it as the recommended algorithm.
- FSRS uses a three-variable memory model (Difficulty, Stability, Retrievability) instead of SM-2's single ease factor.
- FSRS eliminates "ease hell" — SM-2's pathological behavior where repeated lapses permanently damage a card's interval growth.
- Reported efficiency gains: 20–30% fewer reviews for equivalent retention.
- Per-user parameter optimization from review history is possible (`fsrs.Optimizer`) once a user has enough data.

There is no SM-2 fallback. The schema is FSRS-shaped from day one.

### 13.2 FSRS implementation

```python
from fsrs import Scheduler, Card, Rating, ReviewLog

scheduler = Scheduler(
    parameters=user.fsrs_parameters or DEFAULT_PARAMETERS,
    desired_retention=user.desired_retention or 0.90,
)

# On review
card = load_card(card_id)
rating = Rating(user_rating)  # 1=Again, 2=Hard, 3=Good, 4=Easy
card, review_log = scheduler.review_card(card, rating)
save_card(card)
append_review_log(review_log)
```

py-fsrs Card and ReviewLog have `to_json()` / `from_json()` methods, so serialization to SQLite is straightforward.

### 13.3 Per-user optimization

Once a user has accumulated enough reviews (`fsrs.Optimizer` recommends 1000+ but works with fewer), an admin-or-user-triggered "optimize my FSRS parameters" action recomputes the 21 model parameters from their `review_history` and stores them per-user. Default parameters work fine until then.

### 13.4 Card Types

Every learnable item is a card.

| Type | Prompt | Evaluation |
|---|---|---|
| `grammar_production` | "Write a sentence using [grammar point]" | AI or self-rate |
| `grammar_recognition` | "What does this sentence structure mean?" | Multiple choice |
| `vocab_reading` | Show kanji → provide reading | Text match |
| `vocab_meaning` | Show Japanese → provide meaning | Text match / AI |
| `kanji_reading` | Show kanji → provide on/kun reading | Text match |
| `conjugation` | Show verb + target form → conjugate it | Text match |
| `particle_fill` | Sentence with blank → correct particle | Multiple choice |

### 13.5 Daily Review Session

- Due cards: all per-user cards where `due <= NOW() AND suspended = 0`
- New cards: up to `settings.daily_new_cards` (default: 10) cards not yet introduced
- Session ends when both queues are empty or user quits
- Progress saved after every card
- Full keyboard support: Space reveals, 1–4 rate, Enter submits free-form, Esc exits with progress saved

---

## 14. Feature Specification

### 14.1 Grammar Lessons
Structured lesson pages per grammar point: name, pronunciation, JLPT level badge with source-of-tag, short explanation, formation pattern, 3–5 example sentences with furigana and TTS, formation breakdown across word types (godan/ichidan/irregular/i-adj/na-adj), common mistakes, related grammar points, "Practice this" button to create an SRS card.

### 14.2 SRS Flashcards
Daily review queue. Cards presented one at a time. Grammar cards: free-form sentence production with AI evaluation or self-rating. Vocab/kanji cards: standard recognition/recall. Progress bar, streak counter, session summary. Keyboard-first.

### 14.3 Quiz Mode
Session-based quizzes. Grammar quiz, vocabulary quiz, conjugation drill, particle challenge. Random / JLPT-filtered / category-filtered / AI-generated from a custom topic.

### 14.4 Parse Tree / Sentence Analyser
Enter any Japanese sentence → visual parse tree. Nodes colour-coded by POS. Hover → reading, dictionary form, meaning (JMDict lookup), grammar pattern. Powered by `fugashi` + `pykakasi` + Yomi's pattern matcher.

### 14.5 Conjugation Map
Select any verb → full conjugation table. Each cell creates an SRS card on click. Programmatic; irregulars (来る, する, 行く, ある, だ/です, 問う, 死ぬ, いい/良い) handled via lookup table.

### 14.6 Essential Verbs
Curated high-frequency verbs list (Hanabira's 600 Essential Verbs JSON) with usage examples, collocations, particle patterns, Tatoeba sentences, inline conjugation map.

### 14.7 Vocabulary Browser
JMDict filtered by JLPT, POS, frequency, FTS search. Readings, meanings, example sentences, kanji breakdown. "Add to deck" creates SRS card. Per-user tagging.

### 14.8 Kanji Browser
KANJIDIC2 filtered by JLPT, grade, frequency, radical. Readings, meanings, stroke count, radical decomposition (KRADFILE), example words from JMDict, example sentences from Tatoeba. "Add to deck" creates a kanji_reading SRS card.

### 14.9 Progress Dashboard (per-user)
Heatmap calendar, grammar completion by JLPT level, SRS card health (new/learning/review/mature), accuracy per grammar category over time, streak counter, total time estimate, weak points.

### 14.10 Sentence Library (per-user)
Personal saved sentences from the analyser, AI generation, Tatoeba, or in-review flagging. Tag, annotate, convert to SRS card.

### 14.11 Furigana
**Always on, everywhere.** No toggle. Every Japanese display surface that contains kanji also shows furigana above. The user can choose to mentally skip them but the interface does not.

### 14.12 Settings & Customisation (per-user)
- **AI provider** — provider, API key (encrypted), model, temperature
- **Daily limits** — new cards per day, max review session size
- **Display** — font size, font choice (Japanese font)
- **Audio** — TTS voice selection (from browser-detected voices), playback speed
- **FSRS parameters** — desired retention, optimize from history button
- **Data management** — export/import own progress as JSON, delete account
- **Security** — change password, log out everywhere, view own audit log

### 14.13 Admin Panel
Separate route, admin-only.
- **Users** — list, suspend, delete, promote/demote
- **Invites** — generate single-use codes with optional expiry; view used/unused
- **Audit log** — system-wide login attempts, security events
- **Instance settings** — registration enabled (toggle), allowed AI providers
- **Stats** — instance-level (total users, total reviews, content version)

---

## 15. Docker Compose — Full Stack

```yaml
services:

  nginx:
    image: nginx:alpine
    container_name: yomi_nginx
    ports:
      - "8888:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - frontend
      - backend
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: yomi_frontend
    environment:
      - NEXT_PUBLIC_API_BASE=/api
    depends_on:
      - backend
    restart: unless-stopped

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: yomi_backend
    environment:
      - DB_CONTENT_PATH=/data/content.db
      - DB_USER_PATH=/data/user.db
      - YOMI_BEHIND_HTTPS=${YOMI_BEHIND_HTTPS:-true}
      - YOMI_BASE_URL=${YOMI_BASE_URL}
      - YOMI_SESSION_SECRET=${YOMI_SESSION_SECRET}
      - YOMI_LOG_LEVEL=${YOMI_LOG_LEVEL:-INFO}
    volumes:
      - yomi_data:/data
    restart: unless-stopped

  ingestion:
    build:
      context: ./ingestion
      dockerfile: Dockerfile
    container_name: yomi_ingestion
    environment:
      - DB_CONTENT_PATH=/data/content.db
    volumes:
      - yomi_data:/data
    profiles:
      - tools

volumes:
  yomi_data:
    driver: local
```

**Required environment variables** (in `.env`, never committed):
- `YOMI_SESSION_SECRET` — random 32+ byte string for session cookie signing. Generate with `openssl rand -hex 32`.
- `YOMI_BASE_URL` — full external URL (e.g. `https://yomi.example.org`)
- `YOMI_BEHIND_HTTPS` — `true` in production, `false` for local dev without HTTPS

**TLS:** Configure Caddy or Cloudflare Tunnel in front of nginx. The Caddy config is documented in `deploy/caddy/Caddyfile.example`.

**Starting Yomi:**

```bash
# Generate secrets
openssl rand -hex 32 > .secrets/session_secret

# First time: download + ingest content data
docker compose --profile tools run ingestion

# Bootstrap first admin (interactive prompt)
docker compose run --rm backend python -m yomi.bootstrap_admin

# Start the stack
docker compose up -d
```

A `make bootstrap` target wraps all of this.

---

## 16. Directory Structure

```
yomi/
├── docker-compose.yml
├── Makefile
├── LICENSE                           # AGPL v3
├── LICENSES.md                       # Bundled data sources + their licenses
├── README.md
├── SECURITY.md                       # Vulnerability disclosure, threat model
├── CONTRIBUTING.md
├── .env.example
├── nginx/
│   └── nginx.conf                    # Includes CSP, HSTS, etc.
├── deploy/
│   ├── caddy/Caddyfile.example
│   └── cloudflare-tunnel.md
│
├── frontend/                         # Next.js 15
│   ├── Dockerfile
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   │   ├── login/page.tsx
│   │   │   │   ├── register/page.tsx
│   │   │   │   └── change-password/page.tsx
│   │   │   ├── (dashboard)/
│   │   │   │   ├── page.tsx          # Progress dashboard
│   │   │   │   ├── grammar/...
│   │   │   │   ├── review/page.tsx
│   │   │   │   ├── quiz/page.tsx
│   │   │   │   ├── analyse/page.tsx
│   │   │   │   ├── vocabulary/page.tsx
│   │   │   │   ├── kanji/page.tsx
│   │   │   │   ├── verbs/page.tsx
│   │   │   │   ├── library/page.tsx
│   │   │   │   └── settings/page.tsx
│   │   │   └── (admin)/
│   │   │       └── admin/
│   │   │           ├── users/page.tsx
│   │   │           ├── invites/page.tsx
│   │   │           ├── audit/page.tsx
│   │   │           └── instance/page.tsx
│   │   ├── components/...
│   │   ├── lib/
│   │   │   ├── api.ts                # Typed client, attaches CSRF token
│   │   │   ├── auth.ts               # Session check, redirects
│   │   │   └── ...
│   │   └── styles/
│   └── public/manifest.json
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── yomi/
│   │   ├── main.py
│   │   ├── bootstrap_admin.py        # CLI for first admin
│   │   ├── middleware/
│   │   │   ├── session.py
│   │   │   ├── csrf.py
│   │   │   ├── rate_limit.py
│   │   │   └── security_headers.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── grammar.py
│   │   │   ├── vocabulary.py
│   │   │   ├── kanji.py
│   │   │   ├── srs.py
│   │   │   ├── quiz.py
│   │   │   ├── progress.py
│   │   │   ├── ai.py
│   │   │   ├── parser.py
│   │   │   ├── sentences.py
│   │   │   ├── settings.py
│   │   │   ├── export.py
│   │   │   └── admin.py
│   │   ├── services/
│   │   │   ├── auth.py
│   │   │   ├── crypto.py
│   │   │   ├── srs_engine.py
│   │   │   ├── ai_gateway.py
│   │   │   ├── parser.py
│   │   │   ├── quiz_generator.py
│   │   │   ├── conjugation_engine.py
│   │   │   └── audit.py
│   │   ├── db/
│   │   │   ├── content.py
│   │   │   ├── user.py
│   │   │   └── migrations/
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── session.py
│   │   │   ├── grammar.py
│   │   │   ├── srs.py
│   │   │   ├── ai.py
│   │   │   └── ...
│   │   └── deps.py                   # current_user, current_admin, etc.
│   └── tests/
│
├── ingestion/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── ingest.py
│   └── sources/...
│
└── data/
    └── sources/                      # Cached downloads (gitignored)
```

---

## 17. Database Schemas

### 17.1 content.db (read-only at runtime)

Same as v0.2. Tables: `grammar_points`, `example_sentences`, `vocab_items`, `kanji`, FTS5 virtual tables, indexes.

### 17.2 user.db (read-write)

```sql
-- Users
CREATE TABLE users (
  id              INTEGER PRIMARY KEY,
  username        TEXT UNIQUE NOT NULL,
  display_name    TEXT NOT NULL,
  email           TEXT,                       -- optional, not required
  password_hash   TEXT NOT NULL,              -- Argon2id encoded
  enc_salt        BLOB NOT NULL,              -- 16 bytes, for KDF
  is_admin        INTEGER DEFAULT 0,
  is_active       INTEGER DEFAULT 1,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_login_at   DATETIME,
  failed_logins   INTEGER DEFAULT 0,
  locked_until    DATETIME,
  -- FSRS per-user
  fsrs_parameters TEXT,                       -- JSON array of 21 floats, NULL = defaults
  desired_retention REAL DEFAULT 0.90,
  -- 2FA (post-v1 placeholder)
  totp_secret     TEXT,
  totp_enabled    INTEGER DEFAULT 0
);

-- Sessions
CREATE TABLE sessions (
  id              TEXT PRIMARY KEY,           -- random 32-byte URL-safe token
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  expires_at      DATETIME NOT NULL,
  last_seen_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  ip_address      TEXT,
  user_agent      TEXT,
  revoked         INTEGER DEFAULT 0
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- Invite codes
CREATE TABLE invites (
  code            TEXT PRIMARY KEY,           -- random 16-byte URL-safe
  created_by      INTEGER REFERENCES users(id),
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  expires_at      DATETIME,                   -- nullable
  is_admin_invite INTEGER DEFAULT 0,
  used_by         INTEGER REFERENCES users(id),
  used_at         DATETIME
);

-- Per-user encrypted secrets (API keys etc.)
CREATE TABLE user_secrets (
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider        TEXT NOT NULL,              -- 'openrouter','anthropic','openai','ollama','custom'
  nonce           BLOB NOT NULL,              -- 12 bytes
  ciphertext      BLOB NOT NULL,              -- AES-GCM encrypted API key + tag
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, provider)
);

-- Per-user settings (non-secret)
CREATE TABLE user_settings (
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key             TEXT NOT NULL,
  value           TEXT NOT NULL,              -- JSON
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, key)
);

-- Audit log
CREATE TABLE audit_log (
  id              INTEGER PRIMARY KEY,
  user_id         INTEGER,                    -- nullable for system events
  event_type      TEXT NOT NULL,              -- 'login_success','login_failure', etc.
  timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
  ip_address      TEXT,
  user_agent      TEXT,
  details         TEXT                        -- JSON
);
CREATE INDEX idx_audit_user_time ON audit_log(user_id, timestamp);
CREATE INDEX idx_audit_event_time ON audit_log(event_type, timestamp);

-- Instance settings (admin-managed, single-row KV)
CREATE TABLE instance_settings (
  key             TEXT PRIMARY KEY,
  value           TEXT NOT NULL,              -- JSON
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- SRS cards (FSRS-shaped)
CREATE TABLE srs_cards (
  id              INTEGER PRIMARY KEY,
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  card_type       TEXT NOT NULL,
  content_id      INTEGER NOT NULL,
  content_table   TEXT NOT NULL,
  -- FSRS state (from py-fsrs Card.to_json)
  state           TEXT NOT NULL,              -- 'New','Learning','Review','Relearning'
  difficulty      REAL,
  stability       REAL,
  step            INTEGER,
  last_review     DATETIME,
  due             DATETIME NOT NULL,
  -- Yomi metadata
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  suspended       INTEGER DEFAULT 0
);
CREATE INDEX idx_cards_user_due ON srs_cards(user_id, due) WHERE suspended = 0;
CREATE INDEX idx_cards_user_type ON srs_cards(user_id, card_type, due);

-- Review history (append-only)
CREATE TABLE review_history (
  id              INTEGER PRIMARY KEY,
  card_id         INTEGER NOT NULL REFERENCES srs_cards(id) ON DELETE CASCADE,
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  reviewed_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
  rating          INTEGER NOT NULL,           -- 1=Again, 2=Hard, 3=Good, 4=Easy
  user_answer     TEXT,
  ai_score        REAL,
  ai_feedback     TEXT,
  ai_overridden   INTEGER DEFAULT 0,
  time_taken_ms   INTEGER,
  -- FSRS log fields
  state_before    TEXT,
  stability_before REAL,
  difficulty_before REAL
);
CREATE INDEX idx_history_card_time ON review_history(card_id, reviewed_at);
CREATE INDEX idx_history_user_time ON review_history(user_id, reviewed_at);

-- Lesson completions
CREATE TABLE lesson_completions (
  id              INTEGER PRIMARY KEY,
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  grammar_id      INTEGER NOT NULL,
  completed_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_lessons_user ON lesson_completions(user_id);

-- Quiz attempts
CREATE TABLE quiz_attempts (
  id              INTEGER PRIMARY KEY,
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  quiz_type       TEXT NOT NULL,
  grammar_id      INTEGER,
  vocab_id        INTEGER,
  question        TEXT NOT NULL,
  user_answer     TEXT,
  correct         INTEGER,
  attempted_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_quiz_user_time ON quiz_attempts(user_id, attempted_at);

-- Saved sentences
CREATE TABLE saved_sentences (
  id              INTEGER PRIMARY KEY,
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  japanese        TEXT NOT NULL,
  romaji          TEXT,
  translation     TEXT,
  notes           TEXT,
  tags            TEXT,
  source          TEXT,
  saved_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_saved_user ON saved_sentences(user_id);

-- Daily activity (per-user, for heatmap & streaks)
CREATE TABLE daily_activity (
  user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date            DATE NOT NULL,
  reviews_done    INTEGER DEFAULT 0,
  lessons_done    INTEGER DEFAULT 0,
  minutes_est     INTEGER DEFAULT 0,
  PRIMARY KEY (user_id, date)
);
```

---

## 18. API Contract

All authenticated responses follow the envelope:
```json
{ "data": { ... }, "error": null }
```

State-changing endpoints (POST/PUT/PATCH/DELETE) require `X-CSRF-Token` header matching the CSRF cookie.

### 18.1 Public (no auth)

```
GET  /api/auth/csrf-token            ← issues a CSRF token cookie + body
POST /api/auth/register              body: { invite_code, username, display_name, password }
POST /api/auth/login                 body: { username, password }
GET  /api/auth/me                    ← returns current_user or 401
```

### 18.2 Authenticated

```
POST /api/auth/logout
POST /api/auth/logout-everywhere
POST /api/auth/change-password       body: { current_password, new_password }
GET  /api/auth/sessions              ← list user's active sessions
DELETE /api/auth/sessions/:id        ← revoke a specific session

GET  /api/grammar?level=N5
GET  /api/grammar/:slug
GET  /api/grammar/:slug/sentences

GET  /api/vocab/search?q=食べる
GET  /api/vocab/:id
GET  /api/kanji/:character

GET  /api/srs/due
POST /api/srs/review                 body: { card_id, rating, user_answer?, ai_score?, ai_feedback?, ai_overridden? }
POST /api/srs/cards                  body: { content_id, content_table, card_type }

GET  /api/progress/summary
GET  /api/progress/heatmap?year=2026
GET  /api/progress/weak-points

POST /api/ai/evaluate
POST /api/ai/explain
POST /api/ai/translate
GET  /api/ai/status                  ← test current provider connectivity

POST /api/parser/parse
POST /api/parser/furigana
POST /api/parser/romaji

GET  /api/sentences/search
POST /api/sentences/save

GET  /api/settings
PUT  /api/settings/:key
POST /api/settings/api-key           body: { provider, api_key } ← stored encrypted
DELETE /api/settings/api-key/:provider

GET  /api/export                     ← own data as JSON
POST /api/export/import              ← own backup
DELETE /api/auth/me                  ← delete own account
```

### 18.3 Admin-only

```
GET  /api/admin/users
POST /api/admin/users/:id/suspend
POST /api/admin/users/:id/unsuspend
POST /api/admin/users/:id/promote
POST /api/admin/users/:id/demote
DELETE /api/admin/users/:id
POST /api/admin/users/:id/reset-password   ← invalidates user's encrypted keys

GET  /api/admin/invites
POST /api/admin/invites              body: { expires_in_days?, is_admin? }
DELETE /api/admin/invites/:code

GET  /api/admin/audit-log?event_type=&user_id=&limit=
GET  /api/admin/instance-settings
PUT  /api/admin/instance-settings/:key

GET  /api/admin/stats                ← user count, review count, content version
```

---

## 19. Frontend Architecture

### Theme

Single dark gothic theme. CSS variables for code-cleanliness, not for customization.

```css
:root {
  --bg-base:      #0d0d0d;
  --bg-surface:   #141414;
  --bg-raised:    #1c1c1c;
  --border:       #2a2a2a;
  --text-primary: #e8e0d0;
  --text-muted:   #7a7060;
  --accent:       #c8a96e;
  --accent-dim:   #6e5a30;
  --danger:       #8b3030;
  --success:      #3a5c3a;
  --jlpt-n5:      #4a6741;
  --jlpt-n4:      #5c6741;
  --jlpt-n3:      #6b6030;
  --jlpt-n2:      #7a4c28;
  --jlpt-n1:      #8b3030;
}
```

### State management

- React Query — server state. Handles auth-aware caching (clears on logout).
- Zustand — UI state.
- No Redux.

### Auth flow on frontend

- Root layout checks session on mount via `/api/auth/me`. Redirects to `/login` if 401.
- Login page exchanges credentials for a session cookie (set by server, not JS-accessible)
- API client attaches `X-CSRF-Token` header from non-httpOnly CSRF cookie on every mutating request
- React Query invalidates everything on logout

### Furigana rendering

Every kanji-containing text node is wrapped in `<ruby>` tags with readings from the parser. There is no toggle. Components accept either plain Japanese strings (and call the parser themselves) or pre-rendered furigana token arrays.

### Parse tree

Left-to-right tree layout for v1. Nodes are POS-coloured. Hover triggers a JMDict lookup and side-panel render. Swappable renderer interface for future D3 work.

### TTS

Browser Web Speech API only. Settings enumerate available voices on the user's device. Documented limitation: quality varies by platform.

### PWA

Minimal `manifest.json` and a service worker that caches the app shell. Mobile review on the go via the operator's public HTTPS URL.

---

## 20. Operational Concerns

### 20.1 Backup

The entire user state lives in `user.db`. Backup is `cp user.db user.db.YYYYMMDD` (with WAL checkpoint first via `sqlite3 user.db "PRAGMA wal_checkpoint(TRUNCATE);"`).

A `make backup` target produces a tar.gz of `/data/` ready to ship to remote storage. Encrypted backups are the operator's responsibility (rclone, restic, etc.).

### 20.2 Updates

Yomi follows semver. Updating is:

```bash
git pull
docker compose pull        # or build if local
docker compose down
docker compose up -d
```

Migrations live in `backend/yomi/db/migrations/` and run automatically at backend startup. They are forward-only.

Breaking changes are flagged in CHANGELOG with migration steps. Major version bumps may require running `docker compose run backend python -m yomi.migrate` manually.

### 20.3 Monitoring

A `/api/health` endpoint returns DB connectivity, content.db version, instance metrics. The admin panel surfaces this. No external monitoring stack is bundled — operators can scrape `/api/health` with their existing setup.

### 20.4 Logs

Backend logs to stdout in JSON format. Audit events are duplicated to both `audit_log` (in DB) and stdout (for log aggregation). No PII beyond username and IP in standard logs.

### 20.5 Source disclosure (AGPL compliance)

A `/source` link in the footer points to the running version's git commit. The link is auto-populated at build time from the build environment.

---

## 21. Build Order

Each phase is independently usable before starting the next. Realistic timeline for a solo developer balancing other work — roughly 4–5 months to a daily-driveable v1.

### Phase 1 — Foundation (Weeks 1–2)
- [ ] Repo setup, Docker Compose, nginx config with security headers, LICENSE (AGPL), LICENSES.md, SECURITY.md
- [ ] Ingestion script: download + parse grammar JSONs + JMDict → content.db
- [ ] FastAPI skeleton with WAL mode, indexes
- [ ] Frontend skeleton: Next.js, dark theme, navigation, PWA manifest

### Phase 2 — Auth & Multi-User (Weeks 3–4)
- [ ] User/session/invite/secret/audit_log schemas
- [ ] Auth router: register-with-invite, login, logout, password change, session management
- [ ] Argon2id password hashing via pwdlib
- [ ] Session middleware, CSRF middleware, security headers, rate limiting (slowapi)
- [ ] Crypto service: Argon2id KDF + AES-GCM for API keys
- [ ] Frontend auth pages
- [ ] Bootstrap admin CLI (`python -m yomi.bootstrap_admin`)
- [ ] Admin panel skeleton (users, invites, audit log)

### Phase 3 — Core Content & SRS (Weeks 5–7)
- [ ] Grammar lesson pages (list + individual point)
- [ ] Vocabulary browser with JMDict search
- [ ] Example sentence display with browser TTS, always-on furigana
- [ ] FSRS via py-fsrs, per-user scheduling
- [ ] Card creation from lesson completions
- [ ] Daily review session UI (self-rating mode) — full keyboard support
- [ ] Conjugation engine with irregular lookup
- [ ] Progress dashboard (heatmap, stats)

### Phase 4 — AI Layer (Weeks 8–10)
- [ ] AI gateway via LiteLLM with structured outputs
- [ ] Encrypted API key storage + decryption flow
- [ ] Per-user rate limiting on AI endpoints
- [ ] Free-form sentence evaluation
- [ ] AI-powered review with one-tap override UI
- [ ] Settings UI for provider config + "test connection"

### Phase 5 — Advanced Features (Weeks 11–15)
- [ ] Parser integration (fugashi + pykakasi + cutlet)
- [ ] Parse tree visualisation
- [ ] Conjugation map UI
- [ ] Quiz mode (rule-based + AI-augmented)
- [ ] Sentence library
- [ ] Remaining AI features (explain on demand, translation breakdown)
- [ ] KANJIDIC2 ingestion + kanji browser

### Phase 6 — Polish & Release (Weeks 16–18)
- [ ] Tatoeba sentence ingestion + searchable browser
- [ ] Import/export of own progress
- [ ] Account deletion flow
- [ ] Admin reset-password flow with key-loss warning
- [ ] FSRS per-user optimizer trigger
- [ ] Performance review, query optimization
- [ ] README, screenshots, deployment guide (Caddy + Cloudflare Tunnel docs)
- [ ] Security review pass, dependency audit
- [ ] Public AGPL v3 release

---

## 22. Post-v1.0 Roadmap

In rough priority order:

### v1.1 — TOTP 2FA
Optional TOTP-based two-factor authentication. Schema already reserves columns. Adds a step to login flow; QR-code-based enrollment in settings.

### v1.2 — Pitch accent
Integrate Kanjium's pitch accent data (freely redistributable). Surface pitch patterns next to vocab entries and example sentences. Pitch-accent visualization mode for sentences.

### v1.3 — Kanji stroke order
Integrate KanjiVG (CC BY-SA 3.0) for animated SVG stroke order in the kanji browser.

### v1.4 — AnkiConnect export
"Send to Anki" button on every grammar point, vocab entry, kanji, and sentence. POSTs to user's local AnkiConnect endpoint.

### v1.5 — Yomitan dictionary export
Export Yomi's grammar database in Yomitan term-bank format.

### v1.6 — Sentence mining mode
Paste a paragraph; Yomi flags i+1 sentences relative to user's SRS history. Tap to add.

### Speculative
- Email infrastructure for password reset & email verification (optional, opt-in per instance)
- Email digests
- Custom audio source pointer (VOICEVOX, Kokoro, ElevenLabs) for self-hosted TTS
- PostgreSQL migration path if any instance scales past SQLite's comfort zone

---

## 23. Open Questions

| Question | Current thinking |
|---|---|
| Email recovery for forgotten passwords? | Out of scope v1. Admin can reset password but user loses encrypted keys. Documented tradeoff. |
| TTS quality on Linux/Firefox? | Documented limitation. v1 browser-only TTS. Custom audio source is a post-v1 setting. |
| Public landing page / discover page? | Out of scope. Self-hosted only. Static landing on ignisnet.dev links to the repo. |
| Should the admin be able to view a user's audit log? | Yes for their own admin actions on a user; no for the user's per-action history (the user sees their own). |
| Sync across devices? | Not needed. The server *is* sync. All devices hit the same instance. |
| Per-user FSRS parameter optimization UI? | Phase 6 nice-to-have. Default parameters are fine for the first few hundred reviews. |
| Single content.db for all users — fine? | Yes. content.db is read-only at runtime, JLPT data and grammar points are universal. Per-user state lives entirely in user.db. |
| Should we publish to Docker Hub? | Yes, post-v1.0 — gives one-command install. Multi-arch builds via GitHub Actions. |

---

*This document is living and will be updated as the build progresses. Current status: pre-build planning, architecture finalised for v1.0.*
