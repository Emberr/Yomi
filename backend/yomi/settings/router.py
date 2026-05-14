"""User settings API routes — encrypted API key storage and retrieval status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from yomi.auth.csrf import require_csrf
from yomi.auth.dependencies import AuthenticatedUser, get_current_auth
from yomi.db.sqlite import open_user_db
from yomi.secrets.repository import delete_user_secret, list_user_secrets, upsert_user_secret
from yomi.security.crypto import encrypt
from yomi.settings.schemas import SaveApiKeyRequest

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _key_cache(request: Request):
    return request.app.state.session_key_cache


def _get_derived_key(request: Request, auth: AuthenticatedUser) -> bytes:
    key = _key_cache(request).get(auth.session.id)
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Encryption key unavailable. Please log in again.",
        )
    return key


@router.post("/api-key")
def save_api_key(
    payload: SaveApiKeyRequest,
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_auth),
    csrf: None = Depends(require_csrf),
) -> dict[str, object]:
    derived_key = _get_derived_key(request, auth)
    nonce, ciphertext = encrypt(payload.api_key, derived_key)
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        upsert_user_secret(
            connection,
            user_id=auth.user.id,
            provider=payload.provider,
            nonce=nonce,
            ciphertext=ciphertext,
        )
        connection.commit()
    return {"data": {"ok": True}, "error": None}


@router.delete("/api-key/{provider}")
def delete_api_key(
    provider: str,
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_auth),
    csrf: None = Depends(require_csrf),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        deleted = delete_user_secret(connection, user_id=auth.user.id, provider=provider)
        connection.commit()
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    return {"data": {"ok": True}, "error": None}


@router.get("/api-key/status")
def api_key_status(
    request: Request,
    auth: AuthenticatedUser = Depends(get_current_auth),
) -> dict[str, object]:
    settings = request.app.state.settings
    with open_user_db(settings.user_db_path) as connection:
        stored = list_user_secrets(connection, auth.user.id)
    return {"data": {"providers": [s.provider for s in stored]}, "error": None}
