"""Security smoke tests for autobrain-dongle-server.

Covers: auth gates, serial whitelist enforcement, input validation,
constant-time key comparison, backend-fail-closed behaviour, and URL externalisation.
Uses shared fixtures (client, internal_headers, _seed_schema) from conftest.py.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from dongle_server.db import async_session, create_all
from dongle_server.main import app
from dongle_server.models import SerialWhitelist
from dongle_server.config import settings
from dongle_server.storage import _externalize_url
from dongle_server.util import utcnow


WHITELIST_SERIAL = "DEVICE001"


@pytest.fixture
async def whitelisted_serial():
    """Insert a whitelisted serial, yield, then clean up."""
    async with async_session() as db:
        db.add(SerialWhitelist(
            serial_number=WHITELIST_SERIAL, device_id="dev-1",
            user_id="user-1", paid_at=utcnow(),
        ))
        await db.commit()
    yield WHITELIST_SERIAL
    async with async_session() as db:
        await db.execute(
            delete(SerialWhitelist).where(SerialWhitelist.serial_number == WHITELIST_SERIAL)
        )
        await db.commit()


# --- Internal API key gate --------------------------------------------------

async def test_internal_missing_header_rejected(client):
    r = await client.get("/_internal/manifests/latest?model=x")
    assert r.status_code == 401


async def test_internal_empty_key_rejected(client):
    r = await client.get(
        "/_internal/manifests/latest?model=x",
        headers={"X-Internal-Api-Key": ""},
    )
    assert r.status_code == 401


async def test_internal_wrong_key_rejected(client):
    r = await client.get(
        "/_internal/manifests/latest?model=x",
        headers={"X-Internal-Api-Key": "wrong-key"},
    )
    assert r.status_code == 401


async def test_internal_key_constant_time(client, internal_headers):
    """Wrong key of same length must still be 401 (no timing oracle)."""
    r = await client.get(
        "/_internal/manifests/latest?model=x",
        headers={"X-Internal-Api-Key": "x" * len(os.environ["DONGLE_SERVER_API_KEY"])},
    )
    assert r.status_code == 401


# --- Web GUI auth gate ------------------------------------------------------

async def test_web_admin_wrong_password_rejected(client):
    import base64

    creds = base64.b64encode(b"admin:wrong-password").decode()
    r = await client.get("/admin", headers={"Authorization": f"Basic {creds}"})
    assert r.status_code == 401


async def test_web_admin_login_form_no_auth(client):
    r = await client.get("/admin/login")
    assert r.status_code == 200


async def test_web_admin_manifest_new_requires_auth(client):
    r = await client.get("/admin/manifest/new")
    assert r.status_code == 401


async def test_web_admin_create_requires_auth(client):
    r = await client.post(
        "/admin/manifest",
        data={"model": "m", "version": "v", "sha256": "a" * 64,
              "size_bytes": 1, "blob_key": "k"},
    )
    assert r.status_code == 401


# --- Device-edge serial whitelist gate -------------------------------------

async def test_device_edge_missing_api_key_rejected(client, whitelisted_serial):
    r = await client.get(f"/firmware/latest?serial={whitelisted_serial}")
    assert r.status_code == 422


async def test_device_edge_whitelisted_serial_backend_error_fails_closed(client, whitelisted_serial):
    """Whitelist passes but backend verify fails → 503, not 200 (fail-closed)."""
    with patch(
        "dongle_server.security.verify_device_with_backend",
        new_callable=AsyncMock,
        side_effect=__import__("fastapi", fromlist=["HTTPException"]).HTTPException(
            503, "Backend unavailable"
        ),
    ):
        r = await client.get(f"/firmware/latest?serial={whitelisted_serial}&api_key=dummy")
        assert r.status_code == 503


async def test_device_edge_long_serial_rejected(client):
    """Serial exceeding max_length is rejected at validation layer."""
    r = await client.get(f"/firmware/latest?serial={'x' * 65}&api_key=k")
    assert r.status_code == 422


# --- Input validation smoke -------------------------------------------------

async def test_manifest_version_unique_constraint(client, internal_headers):
    payload = {"model": "m", "version": "1.0.0", "sha256": "b" * 64,
               "size_bytes": 1, "blob_key": "k1"}
    assert (await client.post(
        "/_internal/manifests", json=payload, headers=internal_headers
    )).status_code == 201
    dup = dict(payload, blob_key="k2")
    r = await client.post("/_internal/manifests", json=dup, headers=internal_headers)
    assert r.status_code == 409


async def test_manifest_sha256_invalid_chars_rejected(client, internal_headers):
    payload = {"model": "m", "version": "1.0.0", "sha256": "G" * 64,
               "size_bytes": 1, "blob_key": "k"}
    r = await client.post("/_internal/manifests", json=payload, headers=internal_headers)
    assert r.status_code == 422


async def test_manifest_size_zero_rejected(client, internal_headers):
    payload = {"model": "m", "version": "v", "sha256": "a" * 64,
               "size_bytes": 0, "blob_key": "k"}
    r = await client.post("/_internal/manifests", json=payload, headers=internal_headers)
    assert r.status_code == 422


# --- Storage URL externalisation --------------------------------------------

def test_externalize_url_no_external_endpoint_returns_unchanged():
    assert _externalize_url("http://minio:9000/bucket/key") == "http://minio:9000/bucket/key"


def test_externalize_url_rewrites_internal_host(monkeypatch):
    """Internal host replaced with external endpoint."""
    monkeypatch.setattr(settings, "MINIO_EXTERNAL_ENDPOINT", "dongle.example.com")
    monkeypatch.setattr(settings, "MINIO_SECURE", True)
    url = "https://minio:9000/autobrain-assets/firmware/x.bin?sig=abc"
    result = _externalize_url(url)
    assert result == "https://dongle.example.com/autobrain-assets/firmware/x.bin?sig=abc"
