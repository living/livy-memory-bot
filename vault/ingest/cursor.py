"""Cursor management — atomic read/write, shared lock, circuit breaker."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict


# Lock is stale after 20 min — 2x the cron timeout (10 min).
LOCK_STALE_SECONDS = 1200
# Circuit breaker cooldown after 3 consecutive failures: 1 hour.
CIRCUIT_COOLDOWN_SECONDS = 3600


class CursorState(TypedDict):
    last_run_at: str | None
    last_run_id: str | None
    watermark: dict


class RunSummary(TypedDict):
    last_run_at: str | None
    last_run_id: str | None
    watermark: dict


def _cursors_dir(vault_root: Path) -> Path:
    """Return the .cursors directory, creating it if needed."""
    d = vault_root / ".cursors"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cursor_path(vault_root: Path, source: str) -> Path:
    return _cursors_dir(vault_root) / f"{source}.json"


def _lock_path(vault_root: Path) -> Path:
    return _cursors_dir(vault_root) / "vault.lock"


def _failure_path(vault_root: Path, source: str) -> Path:
    return _cursors_dir(vault_root) / f"{source}_failures.json"


# ---------------------------------------------------------------------------
# Cursor read / write
# ---------------------------------------------------------------------------


def read_cursor(vault_root: Path, source: str) -> CursorState:
    """Read cursor state for a source.

    Returns empty cursor if file is missing or corrupted.
    """
    path = _cursor_path(vault_root, source)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return CursorState(
            last_run_at=data.get("last_run_at"),
            last_run_id=data.get("last_run_id"),
            watermark=data.get("watermark", {}),
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return CursorState(last_run_at=None, last_run_id=None, watermark={})


def write_cursor(vault_root: Path, source: str, data: CursorState | RunSummary) -> None:
    """Write cursor state atomically (write-to-temp + rename)."""
    path = _cursor_path(vault_root, source)
    # Atomic write: write to a temp file in the same directory, then rename.
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=".writing_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up the temp file if anything goes wrong.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Shared lock management
# ---------------------------------------------------------------------------


def is_locked(vault_root: Path) -> bool:
    """Return True if a vault lock file currently exists."""
    return _lock_path(vault_root).exists()


def _is_lock_stale(lock_data: dict) -> bool:
    """Return True if the lock was created more than LOCK_STALE_SECONDS ago."""
    started_at = lock_data.get("started_at", "")
    try:
        started = datetime.fromisoformat(started_at)
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - started
        return age.total_seconds() > LOCK_STALE_SECONDS
    except (ValueError, TypeError):
        # Malformed timestamp → treat as stale.
        return True


def acquire_lock(vault_root: Path, job: str, pid: int | None = None) -> bool:
    """Acquire a shared lock for the vault.

    Returns True if the lock was acquired; False if already locked
    by a recent process (or stale lock was removed and re-acquired).
    """
    lock_path = _lock_path(vault_root)

    # Check for existing lock.
    if lock_path.exists():
        try:
            lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Corrupted or unreadable lock → remove it.
            try:
                lock_path.unlink()
            except OSError:
                pass
            lock_data = {}

        if not _is_lock_stale(lock_data):
            return False  # Still held by a recent process.

        # Stale — remove it and proceed to acquire.
        try:
            lock_path.unlink()
        except OSError:
            pass

    # Atomically create lock file using O_CREAT|O_EXCL to prevent race.
    if pid is None:
        pid = os.getpid()
    lock_data = {
        "job": job,
        "pid": pid,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        fd = os.open(
            str(lock_path),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o644,
        )
    except FileExistsError:
        # Another process created it between our stale check and now.
        return False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(lock_data, fh)
    except Exception:
        try:
            os.unlink(str(lock_path))
        except OSError:
            pass
        raise
    return True


def release_lock(vault_root: Path) -> None:
    """Release the vault lock (remove the lock file)."""
    lock_path = _lock_path(vault_root)
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


def check_circuit_breaker(
    vault_root: Path,
    source: str,
    max_failures: int = 3,
) -> bool:
    """Return True if the circuit is open (too many recent failures).

    The circuit is open when:
      - failure count >= max_failures AND
      - last failure occurred within CIRCUIT_COOLDOWN_SECONDS.
    """
    failure_file = _failure_path(vault_root, source)
    try:
        data = json.loads(failure_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False  # No failures recorded → circuit closed.

    count = data.get("count", 0)
    if count < max_failures:
        return False  # Not enough failures → circuit closed.

    last_failure = data.get("last_failure", "")
    try:
        ts = datetime.fromisoformat(last_failure)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - ts
        if age.total_seconds() < CIRCUIT_COOLDOWN_SECONDS:
            return True  # Recent failures, within cooldown → open.
    except (ValueError, TypeError):
        # Malformed timestamp → treat as if recent → open.
        return True

    # Old failures (past cooldown) → circuit closed, caller can retry.
    return False


def record_failure(vault_root: Path, source: str) -> None:
    """Increment the failure counter for a source."""
    failure_file = _failure_path(vault_root, source)
    try:
        data = json.loads(failure_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {"count": 0}

    data["count"] = data.get("count", 0) + 1
    data["last_failure"] = datetime.now(timezone.utc).isoformat()

    fd, tmp_path = tempfile.mkstemp(
        dir=failure_file.parent,
        prefix=".writing_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp_path, failure_file)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def record_success(vault_root: Path, source: str) -> None:
    """Reset the failure counter for a source (on successful run)."""
    failure_file = _failure_path(vault_root, source)
    try:
        failure_file.unlink()
    except FileNotFoundError:
        pass
