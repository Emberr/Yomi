# Backend Dependencies

## Production

- FastAPI
  - Purpose: HTTP API framework for the Yomi backend.
  - License: MIT.
  - Why needed: Provides the project-standard FastAPI foundation instead of hand-written ASGI routing.
  - Security/operational implications: Request validation and OpenAPI support are useful defaults; keep updated with Starlette/Pydantic security releases.

- pwdlib[argon2]
  - Purpose: Argon2id password hashing and verification.
  - License: MIT.
  - Why needed: Uses a maintained password hashing library instead of local cryptographic code.
  - Security/operational implications: Password hashes are intentionally expensive to compute; keep Argon2 parameters aligned with project security requirements and monitor dependency updates.

- Uvicorn
  - Purpose: ASGI server for running FastAPI in the backend container.
  - License: BSD-3-Clause.
  - Why needed: Standard FastAPI-compatible runtime server.
  - Security/operational implications: Exposed only inside Compose behind nginx in normal deployment.

## Test

- pytest
  - Purpose: Backend test runner.
  - License: MIT.

- HTTPX
  - Purpose: FastAPI test client dependency for endpoint tests.
  - License: BSD-3-Clause.

## Local tooling convention

Prefer `uv run pytest` and `uv run python -m compileall yomi tests` for host-side backend checks. If `uv` is unavailable, use `python3 -m pytest` and `python3 -m compileall yomi tests`.

Do not require a host `python` binary. The container command `docker compose run --rm backend python -m pytest` remains the fallback source of truth for backend test validation.
