"""Simple API-key authentication via X-API-Key header."""

from __future__ import annotations

import hmac

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings


def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Reject requests that do not present the configured RAG_SERVICE_API_KEY."""
    expected = (settings.rag_service_api_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG_SERVICE_API_KEY is not configured on the server",
        )
    provided = (x_api_key or "").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
