# Backend Dependencies

## Production

- FastAPI
  - Purpose: HTTP API framework for the Yomi backend.
  - License: MIT.
  - Why needed: Provides the project-standard FastAPI foundation instead of hand-written ASGI routing.
  - Security/operational implications: Request validation and OpenAPI support are useful defaults; keep updated with Starlette/Pydantic security releases.

- pwdlib[argon2]
  - Purpose: Argon2id password hashing and verification (auth). The bundled `argon2-cffi` dependency is also used directly via `argon2.low_level.hash_secret_raw` as a KDF to derive per-user AES-256 encryption keys from login passwords.
  - License: MIT (pwdlib); MIT (argon2-cffi).
  - Why needed: Uses a maintained password hashing library instead of local cryptographic code. Reusing the same Argon2id implementation for both auth and KDF avoids introducing an additional cryptographic primitive.
  - KDF parameters: Argon2id, t=3, m=65536 KiB, p=4, output=32 bytes, domain prefix `yomi-enc-kdf:`. Domain prefix provides separation between auth hashes and KDF output even under degenerate salt conditions.
  - Security/operational implications: Password hashes are intentionally expensive to compute; keep Argon2 parameters aligned with project security requirements and monitor dependency updates. Encryption keys are derived on every login and cached in memory only for the duration of the active session.

- cryptography
  - Purpose: AES-GCM authenticated encryption for per-user API key storage.
  - License: Apache-2.0 / BSD.
  - Why needed: `cryptography.hazmat.primitives.ciphers.aead.AESGCM` provides AES-GCM with proper nonce handling. Used only for data-at-rest encryption of user API keys; not used for auth or TLS.
  - Security/operational implications: Nonces are 12-byte random values (generated via `secrets.token_bytes`). Each encrypt call generates a fresh nonce; reuse would break confidentiality. Ciphertext includes a 16-byte GCM authentication tag that detects tampering. No global master key — all keys are per-user, derived from the user's login password via Argon2id KDF. No plaintext secrets are ever written to disk.

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
