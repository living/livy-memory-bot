import pytest
from vault.qw3.callbacks import handle_confirm, handle_reject, is_confirmed, is_rejected, is_auto_write_enabled

def test_confirm_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw3.callbacks.QW2_BASE", tmp_path)
    assert handle_confirm() == "confirmed"
    assert handle_confirm() == "already_confirmed"

def test_reject_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw3.callbacks.QW2_BASE", tmp_path)
    monkeypatch.setattr("vault.qw3.callbacks.PENDING_DIR", tmp_path / "pending")
    monkeypatch.setattr("vault.qw3.callbacks.ARCHIVE_DIR", tmp_path / "archive")
    (tmp_path / "pending").mkdir(parents=True)
    (tmp_path / "archive").mkdir(parents=True)
    (tmp_path / "pending" / "c1.json").write_text('{"id": "c1"}')

    assert handle_reject("c1") == "rejected"
    assert handle_reject("c1") == "already_rejected"
