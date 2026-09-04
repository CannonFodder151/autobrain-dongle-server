"""AUT-2391: dongle-server must log the resolved AUTOBRAIN_BACKEND_URL at boot.

Prevents recurrence of the AUT-1964 typo (renamed env var went unlogged across
multiple deploys). The boot log line is the observability hook the post-mortem
called for.
"""

import importlib
import logging
import sys

import pytest


@pytest.fixture
def reloaded_app(monkeypatch):
    """Re-import dongle_server.main after patching AUTOBRAIN_BACKEND_URL.

    The boot log is emitted at module-import (process start), so we have to
    re-import to capture it under the patched env.
    """
    import dongle_server.config as cfg_mod

    def _do():
        sys.modules.pop("dongle_server.main", None)
        sys.modules.pop("dongle_server.config", None)
        importlib.import_module("dongle_server.config")
        return importlib.import_module("dongle_server.main")

    return _do


def test_boot_logs_resolved_backend_url(monkeypatch, caplog, reloaded_app):
    monkeypatch.setenv("AUTOBRAIN_BACKEND_URL", "http://backend:8000")
    with caplog.at_level(logging.INFO, logger="dongle_server.boot"):
        reloaded_app()
    assert any(
        "AUTOBRAIN_BACKEND_URL=http://backend:8000" in rec.getMessage()
        for rec in caplog.records
    )


def test_boot_logs_error_when_backend_url_missing(monkeypatch, caplog, reloaded_app):
    monkeypatch.delenv("AUTOBRAIN_BACKEND_URL", raising=False)
    with caplog.at_level(logging.INFO, logger="dongle_server.boot"):
        reloaded_app()
    msgs = [(rec.getMessage(), rec.levelno) for rec in caplog.records]
    matched = [
        (m, lvl) for m, lvl in msgs
        if "AUTOBRAIN_BACKEND_URL" in m and lvl >= logging.ERROR
    ]
    assert matched, f"expected ERROR log for missing AUTOBRAIN_BACKEND_URL, got {msgs}"