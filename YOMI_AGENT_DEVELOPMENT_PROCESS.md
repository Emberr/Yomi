# Yomi — Agent-Optimized Development Process

## Recommendation

Do not feed the full architecture document to Codex for every task. Use the full document once for initial planning and keep it in the repository as canonical reference. For day-to-day development, use layered context:

1. `AGENTS.md` — short always-loaded repository rules.
2. `YOMI_CONTEXT_BRIEF.md` — compressed architecture.
3. One phase ExecPlan — current implementation scope.
4. Focused invariant files — security, validation, API/schema where relevant.
5. Full architecture — loaded only for exact details or conflict resolution.

This gives the agent enough context to stay architecturally aligned without wasting context on unrelated sections.

## Why this structure works

Your architecture document is good as a source of truth, but it mixes many concerns: product vision, data licensing, threat model, database reasoning, Compose, routes, schemas, frontend architecture, operations, roadmap, and open questions. That is exactly the kind of document that should live in the repo, but it should not be permanently pasted into every agent turn.

The better workflow is progressive disclosure: agents get durable high-level rules by default and load detailed files only when the task needs them.

## Development loop

### Step 1 — First repo setup

Copy this context pack into the new repository root. Keep:

- `AGENTS.md` at repo root.
- `docs/agent/*` as agent workflow docs.
- `docs/architecture/YOMI_ARCHITECTURE.md` as canonical spec.

### Step 2 — Start with Phase 0

Use this prompt:

```text
Read AGENTS.md, docs/agent/YOMI_CONTEXT_BRIEF.md, docs/agent/CONTEXT_LOADING_POLICY.md, docs/agent/VALIDATION_MATRIX.md, and docs/agent/phases/PHASE_0_REPO_SCAFFOLD_EXECPLAN.md.
Use plan mode first. Then implement Phase 0 only. Do not begin Phase 1.
```

### Step 3 — Run one phase at a time

For each phase:

```text
Read AGENTS.md, docs/agent/YOMI_CONTEXT_BRIEF.md, docs/agent/VALIDATION_MATRIX.md, and docs/agent/phases/[PHASE].md.
Also read docs/agent/SECURITY_INVARIANTS.md if this phase touches auth, sessions, secrets, user data, admin, AI keys, import/export, or migrations.
Use plan mode. Implement the next milestone only. Update the ExecPlan with progress, decisions, surprises, and verification results.
```

### Step 4 — Review before moving forward

After each phase, ask for review:

```text
Review the current diff against AGENTS.md, the active phase ExecPlan, SECURITY_INVARIANTS.md, and VALIDATION_MATRIX.md. Find architecture drift, security mistakes, missing tests, and incomplete requirements. Do not write code until you produce findings.
```

### Step 5 — Update context when reality changes

When implementation choices become concrete, update the phase file and context brief. Examples:

- exact package manager chosen
- exact test commands
- migration tool
- DB model conventions
- API shape changes
- auth middleware implementation details
- accepted deviations from architecture

## What not to do

- Do not ask the agent to “build the whole thing.” It will drift.
- Do not paste the full architecture every time. It wastes context and makes the current task less salient.
- Do not keep all details in `AGENTS.md`; Codex has project-instruction size limits and long always-loaded instructions become noisy.
- Do not let the agent finish a phase without tests/checks or an explicit blocker.
- Do not move to AI features before auth/secrets are stable.

## Practical phase order

0. Repo scaffold and agent workflow.
1. Foundation.
2. Auth and multi-user.
3. Core content and SRS without AI.
4. AI layer.
5. Advanced features.
6. Polish and release.

## Ideal Codex settings/workflow

- Use plan mode for every phase or security-sensitive change.
- Use medium reasoning for normal implementation; high or extra-high for security/auth/database/AI-gateway work.
- Keep sandbox/approval conservative until the repository commands are stable.
- Prefer small branches and frequent commits.
- Ask for review against the active phase file before accepting a diff.

## Success condition

A future agent session should be able to start from only:

- the repository working tree,
- `AGENTS.md`,
- the context brief,
- the current phase ExecPlan,
- and any focused invariant file,

then continue implementation without needing prior chat history.
