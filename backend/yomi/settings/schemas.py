"""Request and response schemas for settings routes."""

from __future__ import annotations

from pydantic import BaseModel


class SaveApiKeyRequest(BaseModel):
    provider: str
    api_key: str
