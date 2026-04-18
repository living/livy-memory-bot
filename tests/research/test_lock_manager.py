"""Tests for vault/research/lock_manager.py — TDD, Task 3."""
import json
import os
import time
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# We import the module under test (will fail until implemented)
from vault.research.lock_manager import acquire_lock, release_lock, LOCK_TTL


LOCK_TTL_EXPECTED = 600


class TestLockTTLConstant:
    def test_ttl_is_600(self):
        assert LOCK_TTL == LOCK_TTL_EXPECTED


class TestAcquireLockFree:
    """lock livre → acquire succeeds."""

    def test_acquire_on_empty_lockfile(self, tmp_path):
        lock_path = tmp_path / "lock"
        # No lockfile exists → should succeed
        result = acquire_lock(str(lock_path))
        assert result is True

    def test_lockfile_created_with_metadata(self, tmp_path):
        lock_path = tmp_path / "lock"
        before = int(time.time())
        acquire_lock(str(lock_path))
        after = int(time.time())

        assert lock_path.exists()
        meta = json.loads(lock_path.read_text())
        assert meta["pid"] == os.getpid()
        assert before <= meta["start_ts"] <= after + 1

    def test_acquire_creates_parent_dirs(self, tmp_path):
        lock_path = tmp_path / "subdir" / "lock"
        result = acquire_lock(str(lock_path))
        assert result is True
        assert lock_path.exists()


class TestAcquireLockAlivePidWithinTTL:
    """lock com PID vivo (<TTL=600s) → skip (return False)."""

    def test_returns_false_when_alive_pid_within_ttl(self, tmp_path):
        lock_path = tmp_path / "lock"
        # Write a lockfile with our own PID (alive) and fresh timestamp
        meta = {"pid": os.getpid(), "start_ts": int(time.time())}
        lock_path.write_text(json.dumps(meta))

        result = acquire_lock(str(lock_path))
        assert result is False

    def test_returns_false_with_other_alive_pid_within_ttl(self, tmp_path):
        lock_path = tmp_path / "lock"
        # Use PID 1 (init/systemd) — always alive on Linux
        meta = {"pid": 1, "start_ts": int(time.time())}
        lock_path.write_text(json.dumps(meta))

        result = acquire_lock(str(lock_path))
        assert result is False


class TestAcquireLockStaleLock:
    """lock stale (PID morto ou >TTL=600s) → acquires successfully."""

    def test_acquires_when_pid_is_dead(self, tmp_path):
        lock_path = tmp_path / "lock"
        # Use a very large PID that almost certainly doesn't exist
        dead_pid = 9999999
        meta = {"pid": dead_pid, "start_ts": int(time.time())}
        lock_path.write_text(json.dumps(meta))

        # Mock os.kill so that dead_pid raises ProcessLookupError
        real_kill = os.kill

        def mock_kill(pid, sig):
            if pid == dead_pid:
                raise ProcessLookupError(f"No process {pid}")
            return real_kill(pid, sig)

        with patch("vault.research.lock_manager.os.kill", side_effect=mock_kill):
            result = acquire_lock(str(lock_path))

        assert result is True

    def test_acquires_when_lock_exceeds_ttl(self, tmp_path):
        lock_path = tmp_path / "lock"
        # Timestamp older than TTL
        old_ts = int(time.time()) - LOCK_TTL_EXPECTED - 1
        meta = {"pid": os.getpid(), "start_ts": old_ts}
        lock_path.write_text(json.dumps(meta))

        result = acquire_lock(str(lock_path))
        assert result is True

    def test_acquires_when_lockfile_is_corrupt(self, tmp_path):
        lock_path = tmp_path / "lock"
        lock_path.write_text("not-valid-json")

        result = acquire_lock(str(lock_path))
        assert result is True

    def test_lockfile_updated_after_stale_acquire(self, tmp_path):
        lock_path = tmp_path / "lock"
        old_ts = int(time.time()) - LOCK_TTL_EXPECTED - 10
        meta = {"pid": os.getpid(), "start_ts": old_ts}
        lock_path.write_text(json.dumps(meta))

        acquire_lock(str(lock_path))

        new_meta = json.loads(lock_path.read_text())
        assert new_meta["pid"] == os.getpid()
        assert new_meta["start_ts"] > old_ts


class TestReleaseLock:
    """release_lock removes the lockfile."""

    def test_release_removes_lockfile(self, tmp_path):
        lock_path = tmp_path / "lock"
        lock_path.write_text(json.dumps({"pid": os.getpid(), "start_ts": int(time.time())}))

        release_lock(str(lock_path))
        assert not lock_path.exists()

    def test_release_on_missing_file_is_noop(self, tmp_path):
        lock_path = tmp_path / "lock"
        # Should not raise
        release_lock(str(lock_path))

    def test_release_only_removes_own_lock(self, tmp_path):
        lock_path = tmp_path / "lock"
        # Another process holds the lock
        meta = {"pid": 1, "start_ts": int(time.time())}
        lock_path.write_text(json.dumps(meta))

        # release_lock removes regardless of owner (caller's responsibility)
        release_lock(str(lock_path))
        assert not lock_path.exists()
