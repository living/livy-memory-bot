"""Tests for QW-3 callback idempotency."""
import pytest
from vault.qw3.callbacks import handle_confirm, handle_reject, is_confirmed, is_rejected, is_auto_write_enabled


@pytest.fixture(autouse=True)
def clean_flags(tmp_path, monkeypatch):
    """Reset QW2_BASE and clean up any existing flag files before each test."""
    # Clean any existing flags that might persist from previous runs
    import vault.qw3.callbacks as cb
    cb.QW2_BASE = tmp_path
    cb.CONFIRMED_FLAG = tmp_path / ".confirmed"
    cb.PENDING_DIR = tmp_path / "pending"
    cb.ARCHIVE_DIR = tmp_path / "archive"
    # Remove any existing flags
    if cb.CONFIRMED_FLAG.exists():
        cb.CONFIRMED_FLAG.unlink()
    auto_write = tmp_path / ".auto_write_enabled"
    if auto_write.exists():
        auto_write.unlink()
    yield
    # Cleanup after
    if cb.CONFIRMED_FLAG.exists():
        cb.CONFIRMED_FLAG.unlink()


def test_confirm_idempotent(tmp_path, monkeypatch):
    """First confirm returns 'confirmed', second returns 'already_confirmed'."""
    assert handle_confirm() == "confirmed"
    assert handle_confirm() == "already_confirmed"


def test_reject_idempotent(tmp_path, monkeypatch):
    """First reject returns 'rejected', second returns 'already_rejected'."""
    import vault.qw3.callbacks as cb
    cb.PENDING_DIR.mkdir(parents=True, exist_ok=True)
    cb.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    (cb.PENDING_DIR / "c1.json").write_text('{"id": "c1"}')

    assert handle_reject("c1") == "rejected"
    assert handle_reject("c1") == "already_rejected"
