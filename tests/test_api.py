"""AUT-1673: real API + schema validation tests for autobrain-dongle-server."""

from urllib.parse import urlencode

import pytest

from dongle_server.schemas import ManifestCreate, SHA256_RE


def test_sha256_is_case_insensitive():
    import re

    pat = re.compile(SHA256_RE)
    lower = "a" * 64
    upper = "A" * 64
    mixed = "0123456789abcdefABCDEF" + "0" * 42
    assert pat.match(lower)
    assert pat.match(upper)
    assert pat.match(mixed)
    assert not pat.match("g" * 64)
    assert not pat.match("a" * 63)


def test_manifest_create_validates_sha256_case():
    ManifestCreate(
        model="OBD Logging Device V1", version="1.4.2",
        sha256="A" * 64, size_bytes=2048, blob_key="dongle_firmware/x.bin",
    )
    with pytest.raises(Exception):
        ManifestCreate(
            model="m", version="v", sha256="z" * 64,
            size_bytes=1, blob_key="k",
        )


async def test_internal_publish_and_latest(client, internal_headers):
    resp = await client.post(
        "/_internal/manifests",
        json={"model": "OBD Logging Device V1", "version": "1.4.2",
              "sha256": "a" * 64, "size_bytes": 2048,
              "blob_key": "dongle_firmware/a.bin", "release_notes": "stable"},
        headers=internal_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["version"] == "1.4.2"
    assert body["sha256"] == ("a" * 64).lower()
    assert body["blob_url"].startswith("https://dongle-fake/")

    q = urlencode({"model": "OBD Logging Device V1"})
    latest = await client.get(f"/_internal/manifests/latest?{q}", headers=internal_headers)
    assert latest.status_code == 200
    assert latest.json()["version"] == "1.4.2"


async def test_internal_requires_key(client):
    resp = await client.get("/_internal/manifests/latest?model=x")
    assert resp.status_code == 401


async def test_internal_duplicate_rejected(client, internal_headers):
    payload = {"model": "m", "version": "1.0.0", "sha256": "b" * 64,
               "size_bytes": 1, "blob_key": "k1"}
    assert (await client.post("/_internal/manifests", json=payload, headers=internal_headers)).status_code == 201
    dup = await client.post("/_internal/manifests", json=payload, headers=internal_headers)
    assert dup.status_code == 409


async def test_internal_latest_404(client, internal_headers):
    q = urlencode({"model": "missing"})
    resp = await client.get(f"/_internal/manifests/latest?{q}", headers=internal_headers)
    assert resp.status_code == 404


async def test_whitelist_upsert(client, internal_headers):
    h = internal_headers
    r = await client.post(
        "/_internal/whitelist",
        data={"serial": "AB123", "device_id": "d-1", "user_id": "u-1", "paid": True},
        headers=h,
    )
    assert r.status_code == 200
    r2 = await client.post(
        "/_internal/whitelist",
        data={"serial": "AB123", "device_id": "d-1", "user_id": "u-1", "paid": False},
        headers=h,
    )
    assert r2.status_code == 200 and r2.json()["whitelisted"] is False


async def test_device_edge_rejects_unwhitelisted(client):
    r = await client.get("/firmware/latest?serial=NOPE&api_key=k")
    assert r.status_code == 403


async def test_web_admin_requires_auth(client):
    assert (await client.get("/admin")).status_code == 401


async def test_internal_invalid_key_rejected(client):
    r = await client.post(
        "/_internal/manifests",
        json={"model": "m", "version": "1.0.0", "sha256": "b" * 64,
              "size_bytes": 1, "blob_key": "k"},
        headers={"X-Internal-Api-Key": "wrong"},
    )
    assert r.status_code == 401
