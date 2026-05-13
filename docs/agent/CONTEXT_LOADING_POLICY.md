# Context Loading Policy

Goal: give the coding agent full functional context without forcing it to carry the entire 1,400-line architecture document in every turn.

## Default context set

For normal implementation tasks, load:

1. `AGENTS.md`
2. `docs/agent/YOMI_CONTEXT_BRIEF.md`
3. the current phase file in `docs/agent/phases/`
4. `docs/agent/SECURITY_INVARIANTS.md` only if the task touches auth, sessions, secrets, user data, admin, AI providers, import/export, or database migrations
5. `docs/agent/VALIDATION_MATRIX.md` before claiming done

## When to load the full architecture

Load `docs/architecture/YOMI_ARCHITECTURE.md` only when:

- a phase file says “consult full architecture section X”;
- implementation needs exact API/schema details not present in the phase file;
- the agent detects a contradiction;
- the user asks for architecture review or changes;
- security-sensitive behavior is ambiguous.

## Prompt shape for each task

Use this structure:

```text
Goal: <the thing to implement>
Context: read <specific files/sections>
Constraints: <architecture/security/product constraints>
Done when: <objective verification gate>
```

## Why not paste the whole document every time?

The full architecture is useful as a canonical source and first-pass planning input, but it is not ideal as permanent context. It contains product vision, licensing, threat model, schemas, API contract, frontend notes, operations, roadmap, and open questions. Most coding tasks only need one slice. Always-loaded context should be short, stable, and actionable.

## When to summarize vs split

- Use `YOMI_CONTEXT_BRIEF.md` for high-level continuity.
- Use phase ExecPlans for implementation.
- Use focused invariant documents for constraints that must never drift.
- Use the full architecture as a reference, not a prompt blob.

## Phase handoff rule

At the end of each phase, update the next phase file with any real implementation facts that now differ from the plan: package manager, ORM choices, exact command names, directory changes, migrations, API shapes, or known limitations.
