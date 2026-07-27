"""Unit tests for X-API-Key auth helper."""

import pytest
from fastapi import HTTPException

from app.auth import verify_api_key
from app.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_missing_key_raises_401(monkeypatch):
    monkeypatch.setenv("RAG_SERVICE_API_KEY", "secret-key")
    settings = get_settings()
    with pytest.raises(HTTPException) as exc:
        verify_api_key(x_api_key=None, settings=settings)
    assert exc.value.status_code == 401


def test_wrong_key_raises_401(monkeypatch):
    monkeypatch.setenv("RAG_SERVICE_API_KEY", "secret-key")
    settings = get_settings()
    with pytest.raises(HTTPException) as exc:
        verify_api_key(x_api_key="nope", settings=settings)
    assert exc.value.status_code == 401


def test_correct_key_passes(monkeypatch):
    monkeypatch.setenv("RAG_SERVICE_API_KEY", "secret-key")
    settings = get_settings()
    assert verify_api_key(x_api_key="secret-key", settings=settings) is None


def test_unconfigured_key_raises_503(monkeypatch):
    monkeypatch.setenv("RAG_SERVICE_API_KEY", "")
    settings = get_settings()
    with pytest.raises(HTTPException) as exc:
        verify_api_key(x_api_key="anything", settings=settings)
    assert exc.value.status_code == 503
