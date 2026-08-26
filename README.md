# autobrain-dongle-server

Firmware release and distribution service for AutoBrain OBD ESP32 dongles
(**AUT-1673**). Owns the single source of truth for firmware manifests, MinIO
signed blob URLs, the serial-number whitelist, the paid-account gate, and the
ops web GUI.

## Role in the stack

The AutoBrain backend is a **thin paid-gate facade**: `/dongle/firmware/latest`
and `/dongle/firmware` (publish) enforce `require_premium` (paid account, not
admin) and proxy manifest operations to this service over the internal API
(`/_internal/*`, `X-Internal-Api-Key`). Manifest truth lives **only** here.

The device-edge (`GET /firmware/latest?serial=&api_key=`) lets a dongle fetch
its firmware: it requires the serial to be in the whitelist **and** delegates
identity + paid verification to the backend (`POST /api/v1/devices/verify`).

The **serial whitelist is the paid-account gate** at the edge: a serial is
whitelisted only when its owning account is paid (the backend upserts the
whitelist entry from `POST /dongle/firmware/report` when the user is premium).

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/_internal/manifests/latest?model=` | internal key | newest manifest + signed URL (backend facade) |
| `POST` | `/_internal/manifests` | internal key | publish a manifest |
| `POST` | `/_internal/whitelist` | internal key | upsert/revoke a serial (paid gate) |
| `GET` | `/firmware/latest?serial=&api_key=` | device key | device-edge fetch (whitelist + backend paid verify) |
| `GET` | `/admin` | HTTP Basic (ops) | web GUI: manifests + whitelist |
| `POST` | `/admin/manifest` | HTTP Basic (ops) | publish via web form |
| `GET` | `/admin/manifest/new` | HTTP Basic (ops) | publish form |

## Local dev

```bash
docker compose up --build
```

UI on http://localhost:8012/admin (admin / `WEB_UI_BASIC_PASSWORD`).

## Env

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | `sqlite+aiosqlite:///...` or `postgresql+asyncpg://...` |
| `AUTBRAIN_BACKEND_URL` | AutoBrain backend base (for device-edge paid verify) |
| `DONGLE_SERVER_API_KEY` | shared secret the backend uses for `/_internal/*` |
| `MINIO_*` / `MINIO_SECURE` / `MINIO_BUCKET` | blob storage |
| `FIRMWARE_BUCKET_PREFIX` | MinIO key prefix (default `dongle_firmware`) |
| `WEB_UI_BASIC_USER` / `WEB_UI_BASIC_PASSWORD` | ops web GUI |
| `SIGNED_URL_TTL_SECONDS` | presigned URL lifetime (default 900) |
| `ENVIRONMENT=test` | enables in-memory fake storage |
