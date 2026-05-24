import pytest
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[3]))
from vault.qw2.lock import acquire_lock, release_lock, is_locked, LOCK_FILE

def test_acquire_lock_succeeds_when_no_lock():
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
    result = acquire_lock()
    assert result is True
    assert LOCK_FILE.exists()
    release_lock()

def test_acquire_lock_fails_when_fresh_lock_exists():
    acquire_lock()
    result = acquire_lock()
    assert result is False
    release_lock()

def test_acquire_lock_succeeds_when_stale_lock():
    acquire_lock()
    LOCK_FILE.write_text(f"9999|deadbeef12345678|{time.time() - 700}")
    result = acquire_lock()
    assert result is True
    release_lock()

def test_release_lock_removes_file():
    acquire_lock()
    result = release_lock()
    assert result is True
    assert not LOCK_FILE.exists()

def test_is_locked_true_when_fresh():
    acquire_lock()
    assert is_locked() is True
    release_lock()

def test_is_locked_false_when_no_lock():
    if LOCK_FILE.exists():
        release_lock()
    assert is_locked() is False
