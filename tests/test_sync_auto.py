"""
Auto-sync tests — verify the background sync thread starts/stops
and runs sync cycles when configured.
"""
import os
import threading
import time

import pytest

from cc.base.db import database_connection_manager


def test_auto_sync_skips_when_not_configured(_db, monkeypatch):
    """Auto-sync should no-op when CC_SERVER is not set."""
    monkeypatch.delenv("CC_SERVER", raising=False)
    monkeypatch.delenv("CC_API_KEY", raising=False)

    from cc.sync.auto import start
    thread = start()
    assert thread is None


def test_auto_sync_starts_when_configured(_db, monkeypatch):
    """Auto-sync should start a thread when env vars are set."""
    monkeypatch.setenv("CC_SERVER", "http://localhost:9999")
    monkeypatch.setenv("CC_API_KEY", "test-key")

    from cc.sync import auto
    auto._stop_event.clear()
    thread = auto.start()
    assert thread is not None
    assert thread.is_alive()

    auto.stop()
    thread.join(timeout=2)


def test_auto_sync_stop_signals_thread(_db, monkeypatch):
    """stop() should signal the thread to exit."""
    monkeypatch.setenv("CC_SERVER", "http://localhost:9999")
    monkeypatch.setenv("CC_API_KEY", "test-key")

    from cc.sync import auto
    # Override interval to 0.1s so the thread wakes quickly
    original_interval = auto.SYNC_INTERVAL_MINUTES
    auto.SYNC_INTERVAL_MINUTES = 0.001  # ~60ms

    auto._stop_event.clear()
    thread = auto.start()
    assert thread.is_alive()

    auto.stop()
    thread.join(timeout=2)
    assert not thread.is_alive()

    auto.SYNC_INTERVAL_MINUTES = original_interval


def test_sync_cycle_handles_unreachable_server(_db, monkeypatch):
    """_sync_cycle should not raise even if the server is down."""
    monkeypatch.setenv("CC_SERVER", "http://localhost:1")
    monkeypatch.setenv("CC_API_KEY", "test-key")

    from cc.sync.auto import _sync_cycle
    # Should not raise — errors are caught and logged
    _sync_cycle()
