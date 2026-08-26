"""Shared test environment for autobrain-dongle-server.

Forces an on-disk SQLite DB + the in-memory fake storage so the full API can be
exercised without MinIO. The internal API key is a fixed test value.
"""

import os

# FORCE test env: override any inherited production DATABASE_URL (e.g. the
# Paperclip control-plane postgres URL leaked into the process env).
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_dongle.db"
os.environ["ENVIRONMENT"] = "test"
os.environ["DONGLE_SERVER_API_KEY"] = "test-internal-key"
os.environ["AUTOBRIAN_BACKEND_URL"] = "http://backend.test"
os.environ["MINIO_BUCKET"] = "autobrain-assets"
os.environ.pop("DONGLE_SERVER_API_KEY_FILE", None)
os.environ.pop("MINIO_ACCESS_KEY_FILE", None)
os.environ.pop("MINIO_SECRET_KEY_FILE", None)
os.environ.pop("WEB_UI_BASIC_PASSWORD_FILE", None)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from dongle_server.db import engine, create_all, async_session, Base
from dongle_server.main import app
from dongle_server.models import FirmwareManifest, SerialWhitelist


@pytest.fixture(autouse=True, scope="session")
async def _ensure_schema():
    """Drop + recreate all tables so schema changes (e.g. new constraints)
    are picked up even when the on-disk SQLite file persists between runs."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await create_all()
    yield


@pytest.fixture(autouse=True)
async def _seed_schema():
    await create_all()
    async with async_session() as db:
        await db.execute(delete(SerialWhitelist.__table__))
        await db.execute(delete(FirmwareManifest.__table__))
        await db.commit()
    yield


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def internal_headers():
    return {"X-Internal-Api-Key": os.environ["DONGLE_SERVER_API_KEY"]}
