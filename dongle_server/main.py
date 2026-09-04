"""Application factory: mounts routers, templates, static, lifecycle."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles

from .api import device, internal, web
from .config import settings
from .db import create_all
from .storage import get_storage

log = logging.getLogger("dongle_server.boot")

# AUT-2391: log the resolved AUTOBRAIN_BACKEND_URL at boot so a typo'd env var
# (see AUT-1964) cannot hide silently across deploys. Always log the effective
# value; if the env var was missing or misspelled we fall back to the pydantic
# default and emit an ERROR so the operator sees the discrepancy.
if "AUTOBRAIN_BACKEND_URL" in os.environ:
    log.info("AUTOBRAIN_BACKEND_URL=%s", settings.AUTOBRAIN_BACKEND_URL)
else:
    log.error(
        "AUTOBRAIN_BACKEND_URL is not set; using built-in default %r. "
        "Device-edge paid verify will hit the wrong host until this is fixed.",
        settings.AUTOBRAIN_BACKEND_URL,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all()
    yield


app = FastAPI(title="autobrain-dongle-server", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


app.include_router(internal, prefix="/_internal")
app.include_router(device)
app.include_router(web)

_static = Path(__file__).resolve().parent / "static"
if _static.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static)), name="static")
