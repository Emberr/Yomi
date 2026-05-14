"""Tests proving derive_key() is Argon2id-backed, not PBKDF2 or any other KDF.

Covers:
- KDF output is 32 bytes.
- Same password + same enc_salt → same key (deterministic).
- Different enc_salt → different key.
- Different password → different key.
- KDF result matches independent argon2.low_level.hash_secret_raw call with the
  documented parameters — this assertion fails if the implementation switches
  to any non-Argon2id KDF.
- Module does NOT import hashlib.pbkdf2_hmac (static guard).
- Wrong password produces a key that cannot decrypt existing AES-GCM ciphertext.
"""

from __future__ import annotations

import inspect
import secrets

import pytest
from argon2.low_level import Type as Argon2Type
from argon2.low_level import hash_secret_raw
from cryptography.exceptions import InvalidTag

import yomi.security.crypto as crypto_module
from yomi.security.crypto import (
    KEY_BYTES,
    KDF_DOMAIN,
    KDF_MEMORY_COST,
    KDF_PARALLELISM,
    KDF_TIME_COST,
    decrypt,
    derive_key,
    encrypt,
)


# ---------------------------------------------------------------------------
# KDF correctness
# ---------------------------------------------------------------------------


def test_derive_key_returns_32_bytes() -> None:
    key = derive_key("any-password", secrets.token_bytes(16))
    assert isinstance(key, bytes)
    assert len(key) == 32


def test_derive_key_is_deterministic() -> None:
    password = "stable-password"
    enc_salt = secrets.token_bytes(16)
    k1 = derive_key(password, enc_salt)
    k2 = derive_key(password, enc_salt)
    assert k1 == k2


def test_different_enc_salt_produces_different_key() -> None:
    password = "same-password"
    k1 = derive_key(password, secrets.token_bytes(16))
    k2 = derive_key(password, secrets.token_bytes(16))
    assert k1 != k2


def test_different_password_produces_different_key() -> None:
    enc_salt = secrets.token_bytes(16)
    k1 = derive_key("password-one", enc_salt)
    k2 = derive_key("password-two", enc_salt)
    assert k1 != k2


# ---------------------------------------------------------------------------
# Argon2id proof — this test fails for any non-Argon2id KDF
# ---------------------------------------------------------------------------


def test_derive_key_matches_argon2id_reference_implementation() -> None:
    """Independently compute the expected key via argon2-cffi and compare.

    If derive_key() switches to PBKDF2, bcrypt, scrypt, or any other KDF this
    test will fail because the reference computation uses Argon2id directly.
    """
    password = "reference-proof-password"
    enc_salt = b"\xde\xad\xbe\xef" * 4  # fixed 16-byte salt for reproducibility

    expected = hash_secret_raw(
        secret=KDF_DOMAIN + password.encode("utf-8"),
        salt=enc_salt,
        time_cost=KDF_TIME_COST,
        memory_cost=KDF_MEMORY_COST,
        parallelism=KDF_PARALLELISM,
        hash_len=KEY_BYTES,
        type=Argon2Type.ID,
    )
    actual = derive_key(password, enc_salt)
    assert actual == expected


def test_derive_key_uses_argon2id_type_not_argon2i_or_argon2d() -> None:
    """Verify the Type.ID constant is used, not Type.I or Type.D."""
    password = "type-check"
    enc_salt = b"\x01" * 16

    result_id = hash_secret_raw(
        secret=KDF_DOMAIN + password.encode("utf-8"),
        salt=enc_salt,
        time_cost=KDF_TIME_COST,
        memory_cost=KDF_MEMORY_COST,
        parallelism=KDF_PARALLELISM,
        hash_len=KEY_BYTES,
        type=Argon2Type.ID,
    )
    result_i = hash_secret_raw(
        secret=KDF_DOMAIN + password.encode("utf-8"),
        salt=enc_salt,
        time_cost=KDF_TIME_COST,
        memory_cost=KDF_MEMORY_COST,
        parallelism=KDF_PARALLELISM,
        hash_len=KEY_BYTES,
        type=Argon2Type.I,
    )
    # ID and I must differ (proves the type matters)
    assert result_id != result_i
    # derive_key must match ID, not I
    assert derive_key(password, enc_salt) == result_id


# ---------------------------------------------------------------------------
# Static guard: PBKDF2 must NOT appear in the crypto module
# ---------------------------------------------------------------------------


def test_derive_key_does_not_use_pbkdf2() -> None:
    """Fail if the crypto module source references pbkdf2_hmac or PBKDF2."""
    source = inspect.getsource(crypto_module)
    assert "pbkdf2_hmac" not in source, "crypto module must not use PBKDF2"
    assert "PBKDF2" not in source, "crypto module must not reference PBKDF2"


# ---------------------------------------------------------------------------
# Integration: wrong key cannot decrypt
# ---------------------------------------------------------------------------


def test_wrong_password_cannot_decrypt_ciphertext() -> None:
    enc_salt = secrets.token_bytes(16)
    correct_key = derive_key("correct-password", enc_salt)
    wrong_key = derive_key("wrong-password", enc_salt)

    nonce, ciphertext = encrypt("secret-value", correct_key)

    with pytest.raises(InvalidTag):
        decrypt(nonce, ciphertext, wrong_key)
