"""API smoke tests with dependency overrides (no real DB/LLM)."""

from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.db.session import get_db
from app.models.schemas import QueryResponse
from app.api.rag import get_rag_service


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value if isinstance(self._value, list) else []


class FakeSession:
    def __init__(self):
        self.added = []
        self._prompt = None

    async def execute(self, _stmt):
        # list returns empty; get returns stored prompt
        if self._prompt:
            return FakeResult(self._prompt)
        return FakeResult([])

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now
        self.added.append(obj)
        self._prompt = obj

    async def flush(self):
        return None

    async def refresh(self, obj):
        return None

    async def delete(self, obj):
        self._prompt = None

    async def commit(self):
        return None

    async def rollback(self):
        return None


@pytest.fixture
def client():
    app = create_app()
    session = FakeSession()

    async def override_db():
        yield session

    rag = AsyncMock()
    rag.query = AsyncMock(
        return_value=QueryResponse(
            answer="From curriculum context.",
            sources=[],
            model="chat-default",
            project_id="school",
        )
    )

    async def override_rag():
        return rag

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_rag_service] = override_rag

    with TestClient(app) as c:
        yield c, session, rag

    app.dependency_overrides.clear()


def test_health(client):
    c, _, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_query_endpoint(client):
    c, _, rag = client
    resp = c.post(
        "/rag/query",
        json={
            "project_id": "school",
            "question": "What is photosynthesis?",
            "metadata_filters": {"grade": "10"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "From curriculum context."
    assert body["project_id"] == "school"
    rag.query.assert_awaited()


def test_create_and_render_prompt(client):
    c, session, _ = client
    create = c.post(
        "/prompts",
        json={
            "category": "School",
            "title": "Tutor",
            "content": "Teach {{topic}} in {{language}}",
            "variables": ["topic", "language"],
            "project_id": "school",
        },
    )
    assert create.status_code == 201
    prompt_id = create.json()["id"]

    # Ensure get returns the created prompt
    session._prompt = session.added[0]

    rendered = c.post(
        f"/prompts/{prompt_id}/render",
        json={"variables": {"topic": "Math", "language": "ar"}},
    )
    assert rendered.status_code == 200
    assert rendered.json()["rendered"] == "Teach Math in ar"
