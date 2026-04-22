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
    upsert_processed_content_key,
    upsert_processed_decision_key,
    upsert_processed_linkage_key,
    compact_processed_keys,
    monthly_snapshot,
    state_metrics,
    DEFAULT_STATE,
    PENDING_CONFLICTS_ALERT_THRESHOLD,
    DECISION_KEY_MIN_CONFIDENCE,
    get_pending_conflicts,
    add_pending_conflict,
    resolve_pending_conflicts,
    count_pending_conflicts,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FULL_STATE = {
    "processed_event_keys": {"github": [], "tldv": [], "trello": []},
    "processed_content_keys": {"github": [], "tldv": [], "trello": []},
    "processed_decision_keys": {"github": [], "tldv": [], "trello": []},
    "processed_linkage_keys": {"github": [], "tldv": [], "trello": []},
    "last_seen_at": {"github": None, "tldv": None, "trello": None},
    "pending_conflicts": [],
    "version": 1,
}


@pytest.fixture()
def tmp_state_file(tmp_path):
    """Return a path to a temporary state.json pre-seeded with FULL_STATE."""
    p = tmp_path / "state.json"
    p.write_text(json.dumps(FULL_STATE))
    return p


# ---------------------------------------------------------------------------
# DEFAULT_STATE
# ---------------------------------------------------------------------------


def test_default_state_has_trello_sources():
    """Trello must be present in processed key sections and last_seen_at."""
    assert "trello" in DEFAULT_STATE["processed_event_keys"]
    assert "trello" in DEFAULT_STATE["processed_content_keys"]
    assert "trello" in DEFAULT_STATE["processed_decision_keys"]
    assert "trello" in DEFAULT_STATE["processed_linkage_keys"]
    assert "trello" in DEFAULT_STATE["last_seen_at"]
    assert DEFAULT_STATE["processed_event_keys"]["trello"] == []
    assert DEFAULT_STATE["processed_content_keys"]["trello"] == []
    assert DEFAULT_STATE["processed_decision_keys"]["trello"] == []
    assert DEFAULT_STATE["processed_linkage_keys"]["trello"] == []
    assert DEFAULT_STATE["last_seen_at"]["trello"] is None


def test_default_state_has_pending_conflicts():
    """pending_conflicts must be initialised as empty list."""
    assert "pending_conflicts" in DEFAULT_STATE
    assert DEFAULT_STATE["pending_conflicts"] == []


# ---------------------------------------------------------------------------
# PENDING_CONFLICTS_ALERT_THRESHOLD
# ---------------------------------------------------------------------------


def test_alert_threshold_is_200():
    """Alert threshold must be 200 entries."""
    assert PENDING_CONFLICTS_ALERT_THRESHOLD == 200


# ---------------------------------------------------------------------------
# load_state
# ---------------------------------------------------------------------------


def test_load_state_returns_dict_with_required_keys(tmp_state_file):
    state = load_state(tmp_state_file)
    assert isinstance(state, dict)
    assert "processed_event_keys" in state
    assert "processed_content_keys" in state
    assert "last_seen_at" in state
    assert "version" in state


def test_load_state_seeds_file_if_missing(tmp_path):
    path = tmp_path / "state.json"
    assert not path.exists()
    state = load_state(path)
    assert path.exists()
    assert "processed_event_keys" in state


def test_load_state_adds_trello_if_missing(tmp_path):
    """Legacy state without trello source should get it added on load."""
    legacy = {
        "processed_event_keys": {"github": [], "tldv": []},
        "processed_content_keys": {"github": [], "tldv": []},
        "last_seen_at": {"github": None, "tldv": None},
        "version": 1,
    }
    p = tmp_path / "state.json"
    p.write_text(json.dumps(legacy))
    state = load_state(p)
    assert "trello" in state["processed_event_keys"]
    assert "trello" in state["processed_content_keys"]
    assert "trello" in state["last_seen_at"]
    assert state["processed_event_keys"]["trello"] == []
    assert state["processed_content_keys"]["trello"] == []
    assert state["last_seen_at"]["trello"] is None


def test_load_state_adds_pending_conflicts_if_missing(tmp_path):
    """Legacy state without pending_conflicts should get it added on load."""
    legacy = {
        "processed_event_keys": {"github": [], "tldv": [], "trello": []},
        "processed_content_keys": {"github": [], "tldv": [], "trello": []},
        "last_seen_at": {"github": None, "tldv": None, "trello": None},
        "version": 1,
    }
    p = tmp_path / "state.json"
    p.write_text(json.dumps(legacy))
    state = load_state(p)
    assert "pending_conflicts" in state
    assert state["pending_conflicts"] == []


def test_load_state_adds_decision_and_linkage_sections_if_missing(tmp_path):
    """Legacy state without decision/linkage sections should get them added on load."""
    legacy = {
        "processed_event_keys": {"github": [], "tldv": [], "trello": []},
        "processed_content_keys": {"github": [], "tldv": [], "trello": []},
        "last_seen_at": {"github": None, "tldv": None, "trello": None},
        "pending_conflicts": [],
        "version": 1,
    }
    p = tmp_path / "state.json"
    p.write_text(json.dumps(legacy))
    state = load_state(p)
    assert "processed_decision_keys" in state
    assert "processed_linkage_keys" in state
    assert state["processed_decision_keys"] == {"github": [], "tldv": [], "trello": []}
    assert state["processed_linkage_keys"] == {"github": [], "tldv": [], "trello": []}


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
    save_state(FULL_STATE, nested)
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


def test_upsert_trello_source(tmp_state_file):
    """Trello keys should be storable just like github/tldv."""
    event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    state = upsert_processed_event_key("trello", "trello:card:42", event_at, tmp_state_file)
    keys = [e["key"] for e in state["processed_event_keys"]["trello"]]
    assert "trello:card:42" in keys


# ---------------------------------------------------------------------------
# upsert_processed_decision_key
# ---------------------------------------------------------------------------


def test_decision_key_gate_below_threshold_is_skipped(tmp_state_file):
    """Decision key below DECISION_KEY_MIN_CONFIDENCE is not persisted."""
    event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    state = upsert_processed_decision_key("github", "decision:github:42:abc", event_at, 0.5, tmp_state_file)
    keys = [e["key"] for e in state["processed_decision_keys"]["github"]]
    assert "decision:github:42:abc" not in keys


def test_decision_key_gate_at_threshold_is_persisted(tmp_state_file):
    """Decision key at exactly DECISION_KEY_MIN_CONFIDENCE is persisted."""
    event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    state = upsert_processed_decision_key("github", "decision:github:42:abc", event_at, DECISION_KEY_MIN_CONFIDENCE, tmp_state_file)
    keys = [e["key"] for e in state["processed_decision_keys"]["github"]]
    assert "decision:github:42:abc" in keys


def test_decision_key_is_idempotent(tmp_state_file):
    """Duplicate decision_key entries are not created."""
    event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    upsert_processed_decision_key("github", "decision:github:99:def", event_at, 0.9, tmp_state_file)
    state = upsert_processed_decision_key("github", "decision:github:99:def", event_at, 0.9, tmp_state_file)
    keys = [e["key"] for e in state["processed_decision_keys"]["github"]]
    assert keys.count("decision:github:99:def") == 1


# ---------------------------------------------------------------------------
# upsert_processed_linkage_key
# ---------------------------------------------------------------------------


def test_linkage_key_is_persisted_unconditionally(tmp_state_file):
    """Linkage key has no confidence gate and is always persisted."""
    event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    state = upsert_processed_linkage_key("github", "linkage:github:42:xyz", event_at, tmp_state_file)
    keys = [e["key"] for e in state["processed_linkage_keys"]["github"]]
    assert "linkage:github:42:xyz" in keys


def test_linkage_key_is_idempotent(tmp_state_file):
    """Duplicate linkage_key entries are not created."""
    event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
    upsert_processed_linkage_key("github", "linkage:github:99:uvw", event_at, tmp_state_file)
    state = upsert_processed_linkage_key("github", "linkage:github:99:uvw", event_at, tmp_state_file)
    keys = [e["key"] for e in state["processed_linkage_keys"]["github"]]
    assert keys.count("linkage:github:99:uvw") == 1


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


# ---------------------------------------------------------------------------
# pending_conflicts API
# ---------------------------------------------------------------------------


def test_get_pending_conflicts_returns_list(tmp_state_file):
    result = get_pending_conflicts(state_path=tmp_state_file)
    assert isinstance(result, list)


def test_add_pending_conflict_appends_entry(tmp_state_file):
    entry = {
        "entity_id": "person_001",
        "candidates": [
            {"source": "github", "identifier": "gh_001", "event_at": "2026-04-01T00:00:00Z"},
            {"source": "tldv", "identifier": "tldv_001", "event_at": "2026-04-10T00:00:00Z"},
        ],
        "event_key": "tldv:meeting:42",
        "status": "pending",
        "added_at": "2026-04-18T00:00:00+00:00",
    }
    state = add_pending_conflict(entry, state_path=tmp_state_file)
    assert len(state["pending_conflicts"]) == 1
    assert state["pending_conflicts"][0]["entity_id"] == "person_001"
    assert state["pending_conflicts"][0]["status"] == "pending"


def test_add_pending_conflict_persists(tmp_state_file):
    entry = {
        "entity_id": "person_002",
        "candidates": [],
        "event_key": "github:pr:1",
        "status": "pending",
        "added_at": "2026-04-18T00:00:00+00:00",
    }
    add_pending_conflict(entry, state_path=tmp_state_file)
    reloaded = json.loads(tmp_state_file.read_text())
    assert len(reloaded["pending_conflicts"]) == 1
    assert reloaded["pending_conflicts"][0]["entity_id"] == "person_002"


def test_add_pending_conflict_is_idempotent(tmp_state_file):
    """Same entity_id + event_key should not duplicate entries."""
    entry1 = {
        "entity_id": "person_003",
        "candidates": [],
        "event_key": "github:pr:2",
        "status": "pending",
        "added_at": "2026-04-18T00:00:00+00:00",
    }
    entry2 = {
        "entity_id": "person_003",
        "candidates": [],
        "event_key": "github:pr:2",
        "status": "pending",
        "added_at": "2026-04-18T01:00:00+00:00",
    }
    add_pending_conflict(entry1, state_path=tmp_state_file)
    state = add_pending_conflict(entry2, state_path=tmp_state_file)
    ids = [e["entity_id"] for e in state["pending_conflicts"]]
    assert ids.count("person_003") == 1


def test_count_pending_conflicts_returns_int(tmp_state_file):
    assert isinstance(count_pending_conflicts(state_path=tmp_state_file), int)


def test_count_pending_conflicts_returns_correct_count(tmp_state_file):
    for i in range(5):
        add_pending_conflict({
            "entity_id": f"person_{i}",
            "candidates": [],
            "event_key": f"github:pr:{i}",
            "status": "pending",
            "added_at": "2026-04-18T00:00:00+00:00",
        }, state_path=tmp_state_file)
    assert count_pending_conflicts(state_path=tmp_state_file) == 5


# ---------------------------------------------------------------------------
# resolve_pending_conflicts
# ---------------------------------------------------------------------------


def test_resolve_pending_conflicts_resolves_by_source_priority(tmp_state_file):
    """GitHub (priority=3) should win over TLDV (priority=2)."""
    add_pending_conflict({
        "entity_id": "person_github_wins",
        "candidates": [
            {"source": "github", "identifier": "gh_001", "event_at": "2026-04-01T00:00:00Z"},
            {"source": "tldv", "identifier": "tldv_001", "event_at": "2026-04-15T00:00:00Z"},
        ],
        "event_key": "resolve_key_gh",
        "status": "pending",
        "added_at": "2026-04-18T00:00:00+00:00",
    }, state_path=tmp_state_file)

    result = resolve_pending_conflicts(state_path=tmp_state_file)
    assert len(result["resolved"]) == 1
    assert result["resolved"][0]["entity_id"] == "person_github_wins"
    assert result["resolved"][0]["status"] == "resolved"
    assert result["resolved"][0]["winner_identifier"] == "gh_001"
    assert "resolved_by_event_key" in result["resolved"][0]


def test_resolve_pending_conflicts_resolves_by_recency_on_tie(tmp_state_file):
    """Same source priority → most recent event_at wins."""
    add_pending_conflict({
        "entity_id": "person_recency",
        "candidates": [
            {"source": "github", "identifier": "gh_old", "event_at": "2026-04-01T00:00:00Z"},
            {"source": "github", "identifier": "gh_new", "event_at": "2026-04-15T00:00:00Z"},
        ],
        "event_key": "resolve_key_recency",
        "status": "pending",
        "added_at": "2026-04-18T00:00:00+00:00",
    }, state_path=tmp_state_file)

    result = resolve_pending_conflicts(state_path=tmp_state_file)
    assert len(result["resolved"]) == 1
    assert result["resolved"][0]["winner_identifier"] == "gh_new"


def test_resolve_pending_conflicts_keeps_pending_on_full_tie(tmp_state_file):
    """Identical priority + event_at → status stays pending."""
    add_pending_conflict({
        "entity_id": "person_tie",
        "candidates": [
            {"source": "github", "identifier": "gh_a", "event_at": "2026-04-01T00:00:00Z"},
            {"source": "github", "identifier": "gh_b", "event_at": "2026-04-01T00:00:00Z"},
        ],
        "event_key": "resolve_key_tie",
        "status": "pending",
        "added_at": "2026-04-18T00:00:00+00:00",
    }, state_path=tmp_state_file)

    result = resolve_pending_conflicts(state_path=tmp_state_file)
    assert len(result["resolved"]) == 0
    assert len(result["still_pending"]) == 1
    assert result["still_pending"][0]["entity_id"] == "person_tie"


def test_resolve_pending_conflicts_skips_already_resolved(tmp_state_file):
    """Entries with status=resolved should be skipped."""
    state = load_state(tmp_state_file)
    state["pending_conflicts"].append({
        "entity_id": "person_already_resolved",
        "candidates": [],
        "event_key": "github:pr:99",
        "status": "resolved",
        "added_at": "2026-04-17T00:00:00+00:00",
    })
    save_state(state, tmp_state_file)

    result = resolve_pending_conflicts(state_path=tmp_state_file)
    assert len(result["resolved"]) == 0
    assert len(result["still_pending"]) == 0


def test_resolve_pending_conflicts_persists_changes(tmp_state_file):
    """Resolved entries should have status updated in the state file."""
    add_pending_conflict({
        "entity_id": "person_persist",
        "candidates": [
            {"source": "github", "identifier": "gh_persist", "event_at": "2026-04-01T00:00:00Z"},
            {"source": "tldv", "identifier": "tldv_persist", "event_at": "2026-04-10T00:00:00Z"},
        ],
        "event_key": "resolve_key_persist",
        "status": "pending",
        "added_at": "2026-04-18T00:00:00+00:00",
    }, state_path=tmp_state_file)

    resolve_pending_conflicts(state_path=tmp_state_file)

    reloaded = json.loads(tmp_state_file.read_text())
    resolved = [e for e in reloaded["pending_conflicts"] if e["entity_id"] == "person_persist"]
    assert len(resolved) == 1
    assert resolved[0]["status"] == "resolved"
    assert "resolved_by_event_key" in resolved[0]


def test_resolve_pending_conflicts_returns_summary(tmp_state_file):
    """Result must include resolved_count, still_pending_count, total_count."""
    result = resolve_pending_conflicts(state_path=tmp_state_file)
    assert "resolved_count" in result
    assert "still_pending_count" in result
    assert "total_count" in result
    assert result["total_count"] == result["resolved_count"] + result["still_pending_count"]


def test_resolve_pending_conflicts_trello_wins_over_unknown(tmp_state_file):
    """Trello (priority=1) should win over unknown source (priority=0)."""
    add_pending_conflict({
        "entity_id": "person_trello_wins",
        "candidates": [
            {"source": "unknown", "identifier": "unk_001", "event_at": "2026-04-20T00:00:00Z"},
            {"source": "trello", "identifier": "tre_001", "event_at": "2026-04-01T00:00:00Z"},
        ],
        "event_key": "resolve_key_trello",
        "status": "pending",
        "added_at": "2026-04-18T00:00:00+00:00",
    }, state_path=tmp_state_file)

    result = resolve_pending_conflicts(state_path=tmp_state_file)
    assert len(result["resolved"]) == 1
    assert result["resolved"][0]["winner_identifier"] == "tre_001"
