# Phase 4 ExecPlan — AI Layer

## Purpose

Add optional per-user AI evaluation and explanation while preserving the security model: BYO keys, encrypted at rest, no shared proxy key, no final AI authority over review ratings.

## Source context

Read:

- `AGENTS.md`
- `docs/agent/YOMI_CONTEXT_BRIEF.md`
- `docs/agent/SECURITY_INVARIANTS.md`
- `docs/agent/VALIDATION_MATRIX.md`

Consult full architecture sections:

- Section 10 Secrets Handling
- Section 11.3 AI Evaluation Flow
- Section 12 AI Layer — Provider Abstraction
- Section 13 SRS Engine
- Section 18 API Contract

## Scope

- LiteLLM-based AI gateway service.
- Provider settings UI and backend config.
- Encrypted API key save/delete/status flow.
- Provider connectivity test endpoint.
- Structured-output schemas for sentence evaluation.
- `/api/ai/evaluate`, `/api/ai/explain`, `/api/ai/translate` as scoped endpoints.
- AI-powered review feedback with one-tap override.
- Store `ai_score`, `ai_feedback`, and `ai_overridden` separately from final rating.
- Per-user AI rate limit.

## Non-goals

- No global/shared API key.
- No background AI jobs that require decrypted keys outside active sessions.
- No automatic acceptance of AI score without user confirmation.
- No claim that local small models are reliable graders.

## Milestones

### M4.1 — AI settings and secret UX

- Settings page for provider/model/base URL/temperature/max tokens.
- API key save/delete stored through existing crypto service.
- Test connection button.
- Ollama provider path requires no API key.

### M4.2 — Gateway service

- Normalize provider calls through LiteLLM.
- Retrieve/decrypt API key only inside request scope.
- Validate output against Pydantic schema.
- Drop plaintext key after provider call.

### M4.3 — Evaluation endpoint

- Define request/response schema.
- Evaluate free-form Japanese answer against target grammar/card.
- Return advisory rating proposal and structured feedback.

### M4.4 — Review integration

- In review UI, user submits answer.
- AI feedback appears when enabled and available.
- User accepts or overrides rating.
- Review history records AI score and final rating separately.

### M4.5 — Rate limits and failure modes

- Per-user AI call limits.
- Graceful fallback to self-rating when provider fails, key missing, or schema invalid.
- Clear UI errors without exposing key material.

## Done when

- User can configure an AI provider and test it.
- User can receive AI feedback during grammar production review.
- User can override AI rating.
- Review history preserves both AI and user decisions.
- API keys remain encrypted at rest.

## Verification gate

```bash
make test
make lint
make typecheck
# optional integration tests with mocked provider responses
```

Add tests for:

- provider key is encrypted in DB
- no key required for Ollama provider
- invalid AI JSON/schema is rejected gracefully
- AI endpoint rate limit triggers
- user without session encryption key cannot decrypt/use key
- final SRS rating is user-confirmed, not blindly AI-assigned

## Security considerations

This phase touches paid user secrets. Do not log API keys, decrypted payloads, or provider auth headers. Do not store raw prompts/responses unless explicitly scoped and reviewed.

## Decision log

Record implementation decisions here.
