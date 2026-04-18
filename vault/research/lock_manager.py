"""Lock manager with stale-lock cleanup for the research pipeline.

Lock path format: `.research/<source>/lock`
Lock TTL: 600 seconds
Lockfile is JSON: `{"pid": <int>, "start_ts": <unix_ts>}`

Uses `fcntl.flock` for exclusive locking and `os.kill(pid, 0)` to check
whether a process is still alive.

Usage
-----
    lock_path = f".research/{source}/lock"
    acquired = acquire_lock(lock_path)
    if acquired:
        try:
            ...
        finally:
            release_lock(lock_path)
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

LOCK_TTL: int = 600  # seconds

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_meta(lock_path: str) -> dict | None:
    """Load and parse the lockfile metadata, or return None on error."""
    path = Path(lock_path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _is_process_alive(pid: int) -> bool:
    """Return True if the process with the given PID is alive."""
    try:
        # signal 0 does not send anything, it only checks existence/permission
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # EPERM means the process exists, but we lack permission to signal it.
        return True
    except OSError as exc:
        # ESRCH means no such process. EPERM means process exists.
        if exc.errno == errno.ESRCH:
            return False
        if exc.errno == errno.EPERM:
            return True
        return False


def _is_lock_stale(meta: dict, ttl: int = LOCK_TTL) -> bool:
    """Return True when a lock should be considered stale.

    A lock is stale when:
    - its recorded PID has no living process, OR
    - its recorded timestamp is older than ``ttl`` seconds.
    """
    pid = meta.get("pid")
    start_ts = meta.get("start_ts")

    if not isinstance(pid, int) or not isinstance(start_ts, (int, float)):
        return True  # malformed meta → treat as stale so we can reclaim

    if _is_process_alive(pid):
        age = time.time() - start_ts
        if age < ttl:
            # process alive and within TTL → active lock
            return False

    # Either process is dead or lock exceeded TTL
    return True


def _write_meta(lock_path: str, meta: dict) -> None:
    """Write lock metadata, creating parent dirs if needed."""
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def acquire_lock(lock_path: str | Path, ttl: int = LOCK_TTL) -> bool:
    """Acquire an exclusive lock at *lock_path*.

    The conventional path is ``.research/<source>/lock``.

    Returns True when the lock was acquired.  Returns False when an active
    (non-stale) lock already exists.

    A lock is considered stale when:
    - the recorded PID has no living process, OR
    - the recorded timestamp is older than *ttl* seconds (default 600).
    """
    lock_path = str(lock_path)
    lock_path_obj = Path(lock_path)

    # Ensure parent directory exists before opening.
    lock_path_obj.parent.mkdir(parents=True, exist_ok=True)

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    except OSError:
        return False

    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False

        # Check existing lock metadata while holding the exclusive fd.
        meta = _load_meta(lock_path)
        if meta is not None and not _is_lock_stale(meta, ttl=ttl):
            # Active lock held — release and report skip.
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
            return False

        # Write fresh metadata (reclaiming stale lock or brand-new file).
        now = int(time.time())
        _write_meta(lock_path, {"pid": os.getpid(), "start_ts": now})

        # Keep the advisory lock held so concurrent acquire() calls are blocked
        # for the lifetime of this process.  Callers release via release_lock().
        return True

    except Exception:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            os.close(fd)
        except Exception:
            pass
        raise


def release_lock(lock_path: str | Path) -> None:
    """Release (delete) the lock at *lock_path*.

    Removes the lockfile entirely.  Callers are responsible for ensuring they
    only release their own lock.  A missing lockfile is silently ignored.
    """
    try:
        Path(lock_path).unlink(missing_ok=True)
    except OSError:
        pass
