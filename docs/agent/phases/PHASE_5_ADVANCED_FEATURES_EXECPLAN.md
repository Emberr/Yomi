# Phase 5 ExecPlan — Advanced Features

## Purpose

Add the richer learning features after the core system works: parser, parse tree visualization, conjugation map UI, quiz mode, sentence library, remaining AI utilities, and kanji browser.

## Source context

Read:

- `AGENTS.md`
- `docs/agent/YOMI_CONTEXT_BRIEF.md`
- `docs/agent/VALIDATION_MATRIX.md`
- `docs/agent/SECURITY_INVARIANTS.md` for sentence library/user scoping and AI features

Consult full architecture sections:

- Section 14 Feature Specification
- Section 18 API Contract
- Section 19 Frontend Architecture
- Section 4 Data Sources & Licensing for KANJIDIC2/KRADFILE

## Scope

- Parser service with `fugashi`, `pykakasi`, and `cutlet` as planned.
- `/api/parser/parse`, `/api/parser/furigana`, `/api/parser/romaji`.
- Parse tree visualization.
- Conjugation map UI.
- Quiz mode: grammar, vocabulary, conjugation, particle challenge.
- Sentence library: save/search/tag/annotate/convert to SRS card.
- Remaining AI features: explain differently, translation breakdown.
- KANJIDIC2/KRADFILE ingestion and kanji browser.

## Non-goals

- No D3-heavy renderer unless the simple renderer is inadequate.
- No custom TTS provider; browser TTS remains v1.
- No pitch accent or stroke order; those are post-v1.

## Milestones

### M5.1 — Parser service

- Implement tokenization/readings/romaji.
- Add tests using fixed Japanese sentences.
- Ensure parser output is stable enough for frontend ruby rendering.

### M5.2 — Parse tree UI

- Left-to-right tree layout.
- POS-colored nodes.
- Hover/selection shows reading, dictionary form, meaning.
- Side panel lookup against local content DB/JMDict.

### M5.3 — Conjugation map UI

- Select verb, display full table.
- Clicking cell creates SRS card.
- Irregular forms covered by tests.

### M5.4 — Quiz mode

- Implement rule-based quiz generation.
- Record `quiz_attempts`.
- Add optional AI-generated custom topic only if Phase 4 is stable.

### M5.5 — Sentence library

- Save sentences from analyser, Tatoeba, AI generation, or review flagging.
- Tag/annotate/search.
- Convert saved sentence to SRS card.
- Enforce ownership.

### M5.6 — Kanji browser

- Ingest KANJIDIC2 and KRADFILE/RADKFILE.
- Filter by JLPT/grade/frequency/radical.
- Show readings, meanings, stroke count, decomposition, example words/sentences.

### M5.7 — Remaining AI utilities

- Explain grammar differently.
- Translation with particle-by-particle breakdown.
- Naturalness check.
- Clear fallback when AI disabled.

## Done when

- Parser and parse tree work on representative Japanese sentences.
- Quiz attempts are saved.
- Sentence library is fully user-scoped.
- Kanji browser uses local data only.
- No advanced feature breaks core review flow.

## Verification gate

```bash
make test
make lint
make typecheck
docker compose --profile tools run --rm ingestion
```

Add tests for:

- parser output fixtures
- sentence library ownership
- quiz attempt persistence
- kanji lookup from ingested fixtures
- conjugation map creates correct card metadata

## Security considerations

Sentence library and quiz attempts are user-owned. Admin must not gain content visibility through convenience routes. AI utilities must follow the Phase 4 secret-handling model.

## Decision log

Record implementation decisions here.
