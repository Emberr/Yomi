# Phase 3 ExecPlan — Core Content and SRS

## Purpose

Make Yomi useful without AI: ingest core content, browse grammar/vocabulary, create cards, run FSRS review sessions, self-rate answers, and show progress.

## Source context

Read:

- `AGENTS.md`
- `docs/agent/YOMI_CONTEXT_BRIEF.md`
- `docs/agent/VALIDATION_MATRIX.md`
- `docs/agent/SECURITY_INVARIANTS.md` for user-data scoping and review-history ownership

Consult full architecture sections:

- Section 4 Data Sources & Licensing
- Section 6 Database Architecture
- Section 13 SRS Engine
- Section 14 Feature Specification
- Section 17 Database Schemas
- Section 18 API Contract
- Section 19 Frontend Architecture

## Scope

- Real ingestion for initial grammar/JMDict subset or full planned data if feasible.
- `content.db` tables for grammar points, example sentences, vocab items, and FTS search.
- Grammar list/detail pages.
- Vocabulary search/detail pages.
- Always-on furigana display path.
- Browser TTS integration.
- FSRS card model and scheduling through `py-fsrs`.
- SRS card creation from content.
- Daily review queue and self-rating review UI.
- Review history and daily activity updates.
- Progress summary/heatmap basics.
- Conjugation engine backend/service with irregular lookup.

## Non-goals

- No AI grading yet.
- No parse tree UI yet.
- No KANJIDIC2 full kanji browser unless it becomes cheaper to include with ingestion.
- No advanced quiz mode beyond minimal drills if needed for tests.

## Milestones

### M3.1 — Content DB schema and ingestion

- Add content tables and indexes/FTS.
- Ingest grammar points and JMDict data.
- Add content version metadata.
- Ensure ingestion is idempotent and only touches `content.db`.

### M3.2 — Content APIs

- `/api/grammar?level=N5`
- `/api/grammar/:slug`
- `/api/grammar/:slug/sentences`
- `/api/vocab/search?q=`
- `/api/vocab/:id`

### M3.3 — Content frontend

- Grammar list/detail pages.
- Vocab search/detail pages.
- Furigana rendering component.
- Browser TTS controls.

### M3.4 — FSRS models and scheduling

- Add `srs_cards`, `review_history`, `lesson_completions`, `daily_activity` if not already present.
- Implement card creation endpoint.
- Implement due cards query.
- Implement review submission using `py-fsrs`.

### M3.5 — Review UI

- Daily review page.
- Keyboard shortcuts: reveal, 1-4 rating, enter submit, escape exit.
- Self-rating mode with model answer.
- Session summary.

### M3.6 — Progress dashboard

- Summary endpoint.
- Heatmap endpoint.
- Weak-points placeholder based on accuracy/recent lapses.

### M3.7 — Conjugation engine

- Programmatic conjugation for regular verbs/adjectives.
- Lookup handling for irregulars: 来る, する, 行く, ある, だ/です, 問う, 死ぬ, いい/良い.
- Tests for representative forms.

## Done when

- A user can browse grammar/vocab, create a card, complete a self-rated review, and see progress update.
- Content is loaded from local `content.db` at runtime.
- User data is scoped by `user_id`.
- FSRS state persists correctly.

## Verification gate

```bash
docker compose --profile tools run --rm ingestion
make test
make lint
make typecheck
docker compose up -d
# manual smoke: login, browse grammar, create card, review card, see progress
docker compose down
```

Add automated tests for:

- due-card query excludes other users' cards
- review submission cannot update another user's card
- FSRS card due date/history changes after review
- ingestion idempotency
- grammar/vocab search returns expected fixture data

## Security considerations

Every review/card/progress/sentence query must be scoped by authenticated user. Do not expose user content through admin views.

## Decision log

Record implementation decisions here.
