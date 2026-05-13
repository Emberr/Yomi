# Codex Prompt Library for Yomi

Use these prompts as templates. Replace bracketed text.

## Start a new phase

```text
Read AGENTS.md, docs/agent/YOMI_CONTEXT_BRIEF.md, docs/agent/VALIDATION_MATRIX.md, and docs/agent/phases/[PHASE_FILE].md.
If this phase touches auth, sessions, user data, admin, secrets, AI keys, import/export, or migrations, also read docs/agent/SECURITY_INVARIANTS.md.
Use plan mode first. Produce a milestone plan for this phase, identify contradictions or missing decisions, then implement only the first milestone. Do not start later phases.
Done when: the milestone verification commands pass or the failure is documented with the exact blocker.
```

## Implement one milestone

```text
Continue the current phase ExecPlan. Implement milestone [N] only.
Respect AGENTS.md and all security invariants.
After implementation, run the narrowest relevant tests/checks and update the ExecPlan with progress, decisions, surprises, and next steps.
Do not broaden scope without recording the reason.
```

## Review a phase before moving on

```text
Review the current diff against AGENTS.md, docs/agent/YOMI_CONTEXT_BRIEF.md, docs/agent/VALIDATION_MATRIX.md, docs/agent/SECURITY_INVARIANTS.md, and docs/agent/phases/[PHASE_FILE].md.
Find missing tests, security regressions, architecture drift, dead code, and unimplemented phase requirements.
Do not write new code until you produce the review findings.
```

## Recover from context drift

```text
Re-read AGENTS.md, docs/agent/YOMI_CONTEXT_BRIEF.md, the active phase ExecPlan, and any files you modified.
Summarize the intended architecture, current implementation state, drift from the plan, and the smallest safe correction.
Then update the ExecPlan before coding.
```

## Ask Codex to split work safely

```text
This is a large task. Do not code yet.
Create a self-contained ExecPlan for [feature/phase] under docs/agent/phases/ or docs/agent/plans/.
The plan must include purpose, scope, non-goals, milestones, exact files likely to change, verification gates, security implications, and rollback notes.
After writing the plan, stop for review.
```
