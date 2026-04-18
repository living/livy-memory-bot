"""Tests for vault/research/self_healing.py — append-only rollback engine."""

import json
import os

import pytest

from vault.research.self_healing import rollback_append


@pytest.fixture()
def tmp_log_dir(tmp_path):
    return tmp_path / "logs"


@pytest.fixture()
def tmp_log_file(tmp_log_dir):
    p = tmp_log_dir / "experiments.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    # Pre-populate with existing lines to verify append-only invariant
    existing = [
        json.dumps({"event_type": "rollback_append", "event_key": "ev/001", "supersedes": None, "reason": "initial", "breaker_mode": True, "timestamp": "2026-04-01T10:00:00Z"}),
        json.dumps({"event_type": "rollback_append", "event_key": "ev/002", "supersedes": "ev/001", "reason": "correction", "breaker_mode": False, "timestamp": "2026-04-01T11:00:00Z"}),
    ]
    p.write_text("\n".join(existing) + "\n")
    return p


# ---------------------------------------------------------------------------
# rollback_append — core behaviour
# ---------------------------------------------------------------------------

def test_rollback_append_writes_jsonl_line(tmp_log_dir):
    log_path = tmp_log_dir / "experiments.jsonl"
    rollback_append(
        log_path=log_path,
        event_key="ev/003",
        supersedes="ev/002",
        reason="reverted bad change",
        breaker_mode=True,
    )
    lines = log_path.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event_key"] == "ev/003"
    assert record["supersedes"] == "ev/002"
    assert record["reason"] == "reverted bad change"
    assert record["breaker_mode"] is True
    assert "timestamp" in record
    assert record["event_type"] == "rollback_append"


def test_rollback_append_preserves_existing_lines(tmp_log_file):
    """Invariant: never edit existing lines; only append."""
    original_content = tmp_log_file.read_text()
    rollback_append(
        log_path=tmp_log_file,
        event_key="ev/003",
        supersedes="ev/002",
        reason="another rollback",
        breaker_mode=False,
    )
    # Original lines must be unchanged
    assert tmp_log_file.read_text().startswith(original_content.rstrip("\n"))


def test_rollback_append_never_edits_existing_lines(tmp_log_file):
    """The core append-only invariant: existing lines are never modified."""
    original_lines = tmp_log_file.read_text().splitlines()
    rollback_append(
        log_path=tmp_log_file,
        event_key="ev/999",
        supersedes="ev/888",
        reason="breaker test",
        breaker_mode=True,
    )
    final_lines = tmp_log_file.read_text().splitlines()
    # First two lines must be exactly as before
    assert final_lines[:2] == original_lines
    # And exactly one new line was added
    assert len(final_lines) == len(original_lines) + 1
    # The new line is well-formed JSON
    new_record = json.loads(final_lines[-1])
    assert new_record["event_key"] == "ev/999"


def test_rollback_append_supersedes_none(tmp_log_dir):
    log_path = tmp_log_dir / "experiments.jsonl"
    rollback_append(
        log_path=log_path,
        event_key="ev/first",
        supersedes=None,
        reason="first event",
        breaker_mode=True,
    )
    lines = log_path.read_text().splitlines()
    record = json.loads(lines[0])
    assert record["supersedes"] is None


def test_rollback_append_creates_parent_dirs(tmp_path):
    log_path = tmp_path / "brand_new" / "logs" / "experiments.jsonl"
    rollback_append(
        log_path=log_path,
        event_key="ev/new",
        supersedes=None,
        reason="new path",
        breaker_mode=True,
    )
    assert log_path.exists()
    record = json.loads(log_path.read_text().splitlines()[0])
    assert record["event_key"] == "ev/new"
