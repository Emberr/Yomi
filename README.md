# Yomi

Yomi is a planned self-hosted, invite-only Japanese language learning platform.

Current status: Phase 1 foundation skeleton. The stack can build and run with
minimal FastAPI, Next.js, ingestion, and nginx foundations. Product features are
not implemented yet.

## Phase 1 Commands

```bash
make test
make lint
make typecheck
make dev
```

`make dev` starts the current Docker Compose stack on
`http://localhost:8888`. `make bootstrap` and `make backup` are still explicit
stubs until auth/admin setup and backup flows are implemented in later phases.

See `AGENTS.md` and the phase plans under `docs/agent/` for agent workflow context. These agent and architecture documents are local planning context and are ignored by git in this workspace.
