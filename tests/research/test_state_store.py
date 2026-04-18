"""Tests for vault/research/state_store.py — SSOT state store with 180d retention."""
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from vault.research.state_store import (
    load_state,
    save_state,
    upsert_processed_event_key,
    compact_processed_keys,
    monthly_snapshot,
    state_metrics,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EMPTY_STATE = {
    "processed_event_keys": {"github": [], "tldv": []},
    "last_seen_at": {"github": None, "tldv": None},
    "version": 1,
}


@pytest.fixture()
def tmp_state_file(tmp_path):
    """Return a path to a temporary state.json pre-seeded with EMPTY_STATE."""
    p = tmp_path / "state.json"
    p.write_text(json.dumps(EMPTY_STATE))
    return p


# ---------------------------------------------------------------------------
# load_state
# ---------------------------------------------------------------------------


def test_load_state_returns_dict_with_required_keys(tmp_state_file):
    state = load_state(tmp_state_file)
    assert isinstance(state, dict)
    assert "processed_event_keys" in state
    assert "last_seen_at" in state
    assert "version" in state


def test_load_state_seeds_file_if_missing(tmp_path):
    path = tmp_path / "state.json"
    assert not path.exists()
    state = load_state(path)
    assert path.exists()
    assert "processed_event_keys" in state


# ---------------------------------------------------------------------------
# save_state
# ---------------------------------------------------------------------------


def test_save_state_persists_data(tmp_state_file):
    state = load_state(tmp_state_file)
    state["processed_event_keys"]["github"].append("github:pr_merged:1")
    save_state(state, tmp_state_file)

    reloaded = json.loads(tmp_state_file.read_text())
    assert "github:pr_merged:1" in reloaded["processed_event_keys"]["github"]


def test_save_state_creates_parent_dirs(tmp_path):
    nested = tmp_path / "a" / "b" / "state.json"
    save_state(EMPTY_STATE, nested)
    assert nested.exists()


# ---------------------------------------------------------------------------
# upsert_processed_event_key
# ---------------------------------------------------------------------------


def test_upsert_adds_new_key(tmp_state_file):
    event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    state = upsert_processed_event_key("github", "github:pr_merged:42", event_at, tmp_state_file)
    keys = [e["key"] for e in state["processed_event_keys"]["github"]]
    assert "github:pr_merged:42" in keys


def test_upsert_is_idempotent(tmp_state_file):
    event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    upsert_processed_event_key("github", "github:pr_merged:42", event_at, tmp_state_file)
    state = upsert_processed_event_key("github", "github:pr_merged:42", event_at, tmp_state_file)
    keys = [e["key"] for e in state["processed_event_keys"]["github"]]
    assert keys.count("github:pr_merged:42") == 1


def test_upsert_creates_source_if_missing(tmp_state_file):
    event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    state = upsert_processed_event_key("new_source", "new_source:evt:1", event_at, tmp_state_file)
    assert "new_source" in state["processed_event_keys"]


def test_upsert_stores_event_at_as_iso(tmp_state_file):
    event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    state = upsert_processed_event_key("github", "github:pr_merged:99", event_at, tmp_state_file)
    entry = next(e for e in state["processed_event_keys"]["github"] if e["key"] == "github:pr_merged:99")
    assert "event_at" in entry
    assert "2026-04-18" in entry["event_at"]


# ---------------------------------------------------------------------------
# compact_processed_keys
# ---------------------------------------------------------------------------


def test_compact_removes_keys_older_than_retention(tmp_state_file):
    old_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    recent_at = datetime.now(timezone.utc) - timedelta(days=10)
    state = load_state(tmp_state_file)
    state["processed_event_keys"]["github"] = [
        {"key": "github:pr_merged:old", "event_at": old_at.isoformat()},
        {"key": "github:pr_merged:recent", "event_at": recent_at.isoformat()},
    ]
    save_state(state, tmp_state_file)

    compacted = compact_processed_keys(state_path=tmp_state_file, retention_days=180)
    keys = [e["key"] for e in compacted["processed_event_keys"]["github"]]
    assert "github:pr_merged:old" not in keys
    assert "github:pr_merged:recent" in keys


def test_compact_persists_result(tmp_state_file):
    old_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    state = load_state(tmp_state_file)
    state["processed_event_keys"]["github"] = [
        {"key": "github:pr_merged:old", "event_at": old_at.isoformat()},
    ]
    save_state(state, tmp_state_file)
    compact_processed_keys(state_path=tmp_state_file, retention_days=180)
    reloaded = json.loads(tmp_state_file.read_text())
    assert len(reloaded["processed_event_keys"]["github"]) == 0


# ---------------------------------------------------------------------------
# monthly_snapshot
# ---------------------------------------------------------------------------


def test_monthly_snapshot_returns_clean_dict(tmp_state_file):
    snapshot = monthly_snapshot(state_path=tmp_state_file)
    assert isinstance(snapshot, dict)
    assert "processed_event_keys" in snapshot
    assert "snapshot_at" in snapshot


def test_monthly_snapshot_does_not_mutate_state_file(tmp_state_file):
    original = tmp_state_file.read_text()
    monthly_snapshot(state_path=tmp_state_file)
    assert tmp_state_file.read_text() == original


# ---------------------------------------------------------------------------
# state_metrics
# ---------------------------------------------------------------------------


def test_state_metrics_returns_per_source_counts(tmp_state_file):
    event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    upsert_processed_event_key("github", "github:pr_merged:1", event_at, tmp_state_file)
    upsert_processed_event_key("github", "github:pr_merged:2", event_at, tmp_state_file)
    upsert_processed_event_key("tldv", "tldv:meeting:1", event_at, tmp_state_file)

    metrics = state_metrics(state_path=tmp_state_file)
    assert metrics["github"]["key_count"] == 2
    assert metrics["tldv"]["key_count"] == 1


def test_state_metrics_includes_size_bytes(tmp_state_file):
    metrics = state_metrics(state_path=tmp_state_file)
    for source_data in metrics.values():
        assert "size_bytes" in source_data
        assert isinstance(source_data["size_bytes"], int)
