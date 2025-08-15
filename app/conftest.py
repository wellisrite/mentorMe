import pytest
import asyncio
import json
import datetime
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
from app.main import app

pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

class DummyCacheBackend:
    async def get_with_ttl(self, key):
        return None, None
    async def set(self, key, value, expire):
        return None

class DummyCoder:
    def encode(self, value):
        def to_dict(obj):
            if hasattr(obj, "model_dump"):
                return obj.model_dump(mode="json")
            elif hasattr(obj, "dict"):
                return obj.dict()
            elif isinstance(obj, list):
                return [to_dict(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: to_dict(v) for k, v in obj.items()}
            elif isinstance(obj, datetime.datetime):
                return obj.isoformat()
            return obj
        return json.dumps(to_dict(value))
    def decode(self, value):
        return json.loads(value)

@pytest.fixture(autouse=True)
def patch_fastapi_cache(monkeypatch):
    monkeypatch.setattr("fastapi_cache.decorator.cache", lambda *a, **kw: lambda f: f)
    monkeypatch.setattr("fastapi_cache.FastAPICache.init", lambda *a, **kw: None)
    monkeypatch.setattr("fastapi_cache.FastAPICache.get_coder", lambda *a, **kw: DummyCoder())
    monkeypatch.setattr("fastapi_cache.FastAPICache.get_backend", lambda *a, **kw: DummyCacheBackend())
    monkeypatch.setattr("fastapi_cache.FastAPICache.get_key_builder", lambda: lambda *a, **kw: "dummy-key")

@pytest.fixture
def mock_database():
    """Mock database for testing."""
    with patch('app.db.database') as mock_db:
        yield mock_db

@pytest.fixture
async def async_client():
    """Get async client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def sync_client():
    """Get sync client for testing."""
    with TestClient(app) as client:
        yield client

# Shared mock data fixtures
@pytest.fixture
def mock_profile_data():
    return {
        "id": 1,
        "cv_text": "Python developer with 5 years experience",
        "linkedin_url": None,
        "skills": '["python", "django", "postgresql"]',
        "created_at": "2024-01-15T10:00:00"
    }

@pytest.fixture
def mock_job_data():
    return {
        "id": 1,
        "job_description": "Senior Python Developer needed",
        "title": "Senior Python Developer",
        "company": "TechCorp",
        "must_have_skills": '["python", "django"]',
        "nice_to_have_skills": '["redis", "docker"]',
        "created_at": "2024-01-15T10:00:00"
    }

@pytest.fixture
def mock_match_data():
    return {
        "profile_id": 1,
        "job_id": 1,
        "match_score": 85.5,
        "reasons": '[]',
        "suggestions": '[]',
        "created_at": "2024-01-15T10:00:00"
    }