"""AES-GCM encryption and Argon2id-based password-derived key helpers."""

from __future__ import annotations

import secrets

from argon2.low_level import Type as Argon2Type
from argon2.low_level import hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
KEY_BYTES = 32

# Argon2id KDF parameters (per Yomi architecture).
# These are intentionally separate from pwdlib's password-verification hash,
# which uses its own randomly-generated salt embedded in the PHC string.
# Domain prefix prevents KDF output from coinciding with auth-hash output
# even in degenerate scenarios.
KDF_TIME_COST = 3        # t=3
KDF_MEMORY_COST = 65536  # m=65536 KiB
KDF_PARALLELISM = 4      # p=4
KDF_DOMAIN = b"yomi-enc-kdf:"


def derive_key(password: str, enc_salt: bytes) -> bytes:
    """Derive a 32-byte AES key from a plaintext password and per-user salt.

    Uses Argon2id (t=3, m=65536 KiB, p=4) via argon2-cffi.
    Domain prefix ``yomi-enc-kdf:`` separates this KDF from password verification.
    """
    secret = KDF_DOMAIN + password.encode("utf-8")
    return hash_secret_raw(
        secret=secret,
        salt=enc_salt,
        time_cost=KDF_TIME_COST,
        memory_cost=KDF_MEMORY_COST,
        parallelism=KDF_PARALLELISM,
        hash_len=KEY_BYTES,
        type=Argon2Type.ID,
    )


def encrypt(plaintext: str, key: bytes) -> tuple[bytes, bytes]:
    """Encrypt plaintext string with AES-GCM. Returns (nonce, ciphertext)."""
    nonce = secrets.token_bytes(NONCE_BYTES)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce, ciphertext


def decrypt(nonce: bytes, ciphertext: bytes, key: bytes) -> str:
    """Decrypt AES-GCM ciphertext. Returns plaintext string.

    Raises cryptography.exceptions.InvalidTag on bad key or tampered data.
    """
    aesgcm = AESGCM(key)
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext_bytes.decode("utf-8")
