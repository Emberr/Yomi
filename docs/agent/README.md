# Yomi Agent Context Pack

This pack converts the large Yomi architecture document into a workflow coding agents can use without wasting context.

## Recommended usage

Do not paste the whole architecture document into every Codex run. Put these files into the repository and let Codex load `AGENTS.md` automatically. Then start each task with the relevant phase file.

Recommended first prompt:

```text
Read AGENTS.md, docs/agent/YOMI_CONTEXT_BRIEF.md, docs/agent/SECURITY_INVARIANTS.md, and docs/agent/phases/PHASE_0_REPO_SCAFFOLD_EXECPLAN.md.
Use plan mode first. Then implement only Phase 0. Do not begin Phase 1 until the Phase 0 verification gate passes.
```

## File map

| File | Purpose | Load frequency |
|---|---|---|
| `AGENTS.md` | Always-loaded durable repo instructions | Always |
| `docs/agent/YOMI_CONTEXT_BRIEF.md` | Compressed project architecture | Most tasks |
| `docs/agent/CONTEXT_LOADING_POLICY.md` | How to choose what context to load | When starting or reconfiguring agent workflow |
| `docs/agent/SECURITY_INVARIANTS.md` | Non-negotiable security requirements | Any auth/security/user-data/API-key work |
| `docs/agent/VALIDATION_MATRIX.md` | Test and phase gates | Any phase completion or review |
| `docs/agent/PROMPTS.md` | Copy-paste prompts for Codex/agents | When delegating tasks |
| `docs/agent/phases/*.md` | Self-contained phase ExecPlans | Current phase only |
| `docs/architecture/YOMI_ARCHITECTURE.md` | Canonical full specification | Only when details are needed |

## Development rhythm

1. Open a fresh branch for one phase or one milestone.
2. Ask Codex to read `AGENTS.md`, the context brief, security invariants if relevant, and the current phase ExecPlan.
3. Ask for a plan first.
4. Execute one milestone at a time.
5. Run the verification gate.
6. Commit.
7. Move to the next milestone or phase.

## Context principle

The full architecture document is the source of truth. The phase files are working specifications. If a conflict appears, stop, quote both conflicting requirements, make the smallest safe interpretation, and record the decision in the phase ExecPlan.
