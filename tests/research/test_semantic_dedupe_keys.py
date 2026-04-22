"""Tests for Task 8 — Semantic Dedup Keys: decision_key + linkage_key.

SEMANTIC DEDUPE KEY MODEL:
  1. content_key  (primary): source:source_id:content_hash
     → already implemented (Task 6 / dual-key)
  2. decision_key (secondary, confidence>=0.7): source:entity_id:claim_id:content_hash
     → dedupes semantic DECISION claims; skipped if confidence < 0.7
  3. linkage_key  (secondary, always): source:entity_id:linkage_hash
     → dedupes LINKAGE claims; no confidence gate

State sections:
  - processed_decision_keys:  {source: [entries]}
  - processed_linkage_keys:    {source: [entries]}

Entry shape (decision):
  {"key": "...", "entity_id": "...", "claim_id": "...", "confidence": float, "event_at": iso_str}

Entry shape (linkage):
  {"key": "...", "entity_id": "...", "source_entity_id": "...", "target_entity_id": "...",
   "linkage_type": "...", "event_at": iso_str}

Coverage:
  - DEFAULT_STATE pre-allocates both new sections
  - load_state migrates legacy state (adds both sections if missing)
  - upsert_processed_decision_key: adds new key, idempotent
  - upsert_processed_decision_key: SKIPS entry if confidence < 0.7 (returns state unchanged)
  - upsert_processed_linkage_key: adds new key, idempotent
  - upsert_processed_linkage_key: runs regardless of confidence
  - compact_processed_keys cleans both new sections
  - monthly_snapshot includes both new sections
  - state_metrics reports decision_key_count + linkage_key_count
  - Both sections initialised for all three sources (github/tldv/trello)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from vault.research.state_store import (
    DEFAULT_STATE,
    load_state,
    save_state,
    upsert_processed_event_key,
    upsert_processed_content_key,
    compact_processed_keys,
    monthly_snapshot,
    state_metrics,
    upsert_processed_decision_key,
    upsert_processed_linkage_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FULL_STATE = {
    "processed_event_keys": {"github": [], "tldv": [], "trello": []},
    "processed_content_keys": {"github": [], "tldv": [], "trello": []},
    "last_seen_at": {"github": None, "tldv": None, "trello": None},
    "pending_conflicts": [],
    "version": 1,
}


@pytest.fixture()
def tmp_state_file(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps(FULL_STATE))
    return p


# ---------------------------------------------------------------------------
# DEFAULT_STATE — both new sections pre-allocated
# ---------------------------------------------------------------------------

class TestDefaultStateSemanticKeys:
    def test_default_state_has_processed_decision_keys(self):
        assert "processed_decision_keys" in DEFAULT_STATE
        assert isinstance(DEFAULT_STATE["processed_decision_keys"], dict)

    def test_default_state_has_processed_linkage_keys(self):
        assert "processed_linkage_keys" in DEFAULT_STATE
        assert isinstance(DEFAULT_STATE["processed_linkage_keys"], dict)

    def test_decision_keys_has_all_sources(self):
        for source in ("github", "tldv", "trello"):
            assert source in DEFAULT_STATE["processed_decision_keys"]
            assert DEFAULT_STATE["processed_decision_keys"][source] == []

    def test_linkage_keys_has_all_sources(self):
        for source in ("github", "tldv", "trello"):
            assert source in DEFAULT_STATE["processed_linkage_keys"]
            assert DEFAULT_STATE["processed_linkage_keys"][source] == []


# ---------------------------------------------------------------------------
# load_state — migration for legacy state
# ---------------------------------------------------------------------------

class TestLoadStateMigrationSemanticKeys:
    def test_load_state_returns_decision_keys(self, tmp_state_file):
        state = load_state(tmp_state_file)
        assert "processed_decision_keys" in state

    def test_load_state_returns_linkage_keys(self, tmp_state_file):
        state = load_state(tmp_state_file)
        assert "processed_linkage_keys" in state

    def test_load_state_adds_both_sections_to_legacy_state(self, tmp_path):
        """Legacy state without decision/linkage keys must get both added on load."""
        legacy = {
            "processed_event_keys": {"github": [], "tldv": []},
            "processed_content_keys": {"github": [], "tldv": []},
            "last_seen_at": {"github": None, "tldv": None},
            "version": 1,
        }
        p = tmp_path / "state.json"
        p.write_text(json.dumps(legacy))
        state = load_state(p)
        assert "processed_decision_keys" in state
        assert "processed_linkage_keys" in state
        for src in ("github", "tldv"):
            assert src in state["processed_decision_keys"]
            assert src in state["processed_linkage_keys"]
            assert state["processed_decision_keys"][src] == []
            assert state["processed_linkage_keys"][src] == []

    def test_load_state_adds_trello_to_both_new_sections_if_missing(self, tmp_path):
        """State that has github/tldv but not trello must get trello added to both."""
        legacy = {
            "processed_event_keys": {"github": [], "tldv": []},
            "processed_content_keys": {"github": [], "tldv": []},
            "processed_decision_keys": {"github": [], "tldv": []},
            "processed_linkage_keys": {"github": [], "tldv": []},
            "last_seen_at": {"github": None, "tldv": None},
            "version": 1,
        }
        p = tmp_path / "state.json"
        p.write_text(json.dumps(legacy))
        state = load_state(p)
        assert "trello" in state["processed_decision_keys"]
        assert "trello" in state["processed_linkage_keys"]
        assert state["processed_decision_keys"]["trello"] == []
        assert state["processed_linkage_keys"]["trello"] == []


# ---------------------------------------------------------------------------
# upsert_processed_decision_key
# ---------------------------------------------------------------------------

class TestUpsertProcessedDecisionKey:
    def test_adds_new_decision_key(self, tmp_state_file):
        """decision_key should be stored when confidence >= 0.7."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_decision_key(
            source="github",
            decision_key="github:entity_001:claim_42:abc123",
            entity_id="entity_001",
            claim_id="claim_42",
            confidence=0.85,
            event_at=event_at,
            state_path=tmp_state_file,
        )
        keys = [e["key"] for e in state["processed_decision_keys"]["github"]]
        assert "github:entity_001:claim_42:abc123" in keys

    def test_stores_metadata(self, tmp_state_file):
        """decision_key entry must store entity_id, claim_id, confidence, event_at."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_decision_key(
            source="github",
            decision_key="github:entity_002:claim_77:deadbeef",
            entity_id="entity_002",
            claim_id="claim_77",
            confidence=0.92,
            event_at=event_at,
            state_path=tmp_state_file,
        )
        entry = next(
            e for e in state["processed_decision_keys"]["github"]
            if e["key"] == "github:entity_002:claim_77:deadbeef"
        )
        assert entry["entity_id"] == "entity_002"
        assert entry["claim_id"] == "claim_77"
        assert entry["confidence"] == 0.92
        assert "2026-04-18" in entry["event_at"]

    def test_is_idempotent(self, tmp_state_file):
        """Calling twice with same decision_key must not duplicate."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_decision_key(
            "github", "github:e1:c1:hash1", "e1", "c1", 0.80, event_at, tmp_state_file
        )
        state = upsert_processed_decision_key(
            "github", "github:e1:c1:hash1", "e1", "c1", 0.80, event_at, tmp_state_file
        )
        keys = [e["key"] for e in state["processed_decision_keys"]["github"]]
        assert keys.count("github:e1:c1:hash1") == 1

    def test_skips_when_confidence_below_0_7(self, tmp_state_file):
        """confidence=0.69 must NOT be stored; state must be unchanged."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_decision_key(
            source="github",
            decision_key="github:entity_003:claim_88:lowconf",
            entity_id="entity_003",
            claim_id="claim_88",
            confidence=0.69,
            event_at=event_at,
            state_path=tmp_state_file,
        )
        keys = [e["key"] for e in state["processed_decision_keys"]["github"]]
        assert "github:entity_003:claim_88:lowconf" not in keys
        assert state["processed_decision_keys"]["github"] == []

    def test_skips_at_exactly_0_7_boundary(self, tmp_state_file):
        """confidence=0.70 must be stored (boundary: >= 0.7 required)."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_decision_key(
            source="tldv",
            decision_key="tldv:entity_004:claim_99:boundary",
            entity_id="entity_004",
            claim_id="claim_99",
            confidence=0.70,
            event_at=event_at,
            state_path=tmp_state_file,
        )
        keys = [e["key"] for e in state["processed_decision_keys"]["tldv"]]
        assert "tldv:entity_004:claim_99:boundary" in keys

    def test_creates_source_if_missing(self, tmp_state_file):
        """New source not in state should be auto-created."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_decision_key(
            source="new_src",
            decision_key="new_src:e5:c5:hash5",
            entity_id="e5",
            claim_id="c5",
            confidence=0.90,
            event_at=event_at,
            state_path=tmp_state_file,
        )
        assert "new_src" in state["processed_decision_keys"]

    def test_persists_to_file(self, tmp_state_file):
        """decision_key must survive a reload."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_decision_key(
            "github", "github:e6:c6:hash6", "e6", "c6", 0.88, event_at, tmp_state_file
        )
        reloaded = json.loads(tmp_state_file.read_text())
        keys = [e["key"] for e in reloaded["processed_decision_keys"]["github"]]
        assert "github:e6:c6:hash6" in keys

    def test_trello_source_supported(self, tmp_state_file):
        """Trello decision keys should be storable."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_decision_key(
            source="trello",
            decision_key="trello:card_42:claim_1:trello_hash",
            entity_id="card_42",
            claim_id="claim_1",
            confidence=0.95,
            event_at=event_at,
            state_path=tmp_state_file,
        )
        keys = [e["key"] for e in state["processed_decision_keys"]["trello"]]
        assert "trello:card_42:claim_1:trello_hash" in keys


# ---------------------------------------------------------------------------
# upsert_processed_linkage_key
# ---------------------------------------------------------------------------

class TestUpsertProcessedLinkageKey:
    def test_adds_new_linkage_key(self, tmp_state_file):
        """linkage_key should always be stored regardless of confidence."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_linkage_key(
            source="github",
            linkage_key="github:person_001:link_abc",
            entity_id="person_001",
            source_entity_id="gh_junior",
            target_entity_id="tldv_livia",
            linkage_type="cross_identifies",
            event_at=event_at,
            state_path=tmp_state_file,
        )
        keys = [e["key"] for e in state["processed_linkage_keys"]["github"]]
        assert "github:person_001:link_abc" in keys

    def test_stores_metadata(self, tmp_state_file):
        """linkage_key entry must store all required metadata fields."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_linkage_key(
            source="tldv",
            linkage_key="tldv:person_002:link_def",
            entity_id="person_002",
            source_entity_id="tldv_livia",
            target_entity_id="gh_junior",
            linkage_type="mentioned_with",
            event_at=event_at,
            state_path=tmp_state_file,
        )
        entry = next(
            e for e in state["processed_linkage_keys"]["tldv"]
            if e["key"] == "tldv:person_002:link_def"
        )
        assert entry["entity_id"] == "person_002"
        assert entry["source_entity_id"] == "tldv_livia"
        assert entry["target_entity_id"] == "gh_junior"
        assert entry["linkage_type"] == "mentioned_with"
        assert "2026-04-18" in entry["event_at"]

    def test_is_idempotent(self, tmp_state_file):
        """Calling twice with same linkage_key must not duplicate."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_linkage_key(
            "github", "github:p3:link_ghi", "p3", "src3", "tgt3", "rel3", event_at, tmp_state_file
        )
        state = upsert_processed_linkage_key(
            "github", "github:p3:link_ghi", "p3", "src3", "tgt3", "rel3", event_at, tmp_state_file
        )
        keys = [e["key"] for e in state["processed_linkage_keys"]["github"]]
        assert keys.count("github:p3:link_ghi") == 1

    def test_stored_regardless_of_confidence(self, tmp_state_file):
        """linkage_key must be stored even when confidence is 0.0 (no gate)."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        # upsert_processed_linkage_key does not take a confidence parameter
        state = upsert_processed_linkage_key(
            source="tldv",
            linkage_key="tldv:entity_low:link_low",
            entity_id="entity_low",
            source_entity_id="src_low",
            target_entity_id="tgt_low",
            linkage_type="weak_candidate",
            event_at=event_at,
            state_path=tmp_state_file,
        )
        keys = [e["key"] for e in state["processed_linkage_keys"]["tldv"]]
        assert "tldv:entity_low:link_low" in keys

    def test_creates_source_if_missing(self, tmp_state_file):
        """New source should be auto-created for linkage keys."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_linkage_key(
            source="new_link_src",
            linkage_key="new_link_src:e10:link_jkl",
            entity_id="e10",
            source_entity_id="src10",
            target_entity_id="tgt10",
            linkage_type="cross",
            event_at=event_at,
            state_path=tmp_state_file,
        )
        assert "new_link_src" in state["processed_linkage_keys"]

    def test_persists_to_file(self, tmp_state_file):
        """linkage_key must survive a reload."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_linkage_key(
            "github", "github:e11:link_mno", "e11", "src11", "tgt11", "rel11", event_at, tmp_state_file
        )
        reloaded = json.loads(tmp_state_file.read_text())
        keys = [e["key"] for e in reloaded["processed_linkage_keys"]["github"]]
        assert "github:e11:link_mno" in keys

    def test_trello_source_supported(self, tmp_state_file):
        """Trello linkage keys should be storable."""
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_linkage_key(
            source="trello",
            linkage_key="trello:card_99:link_trello",
            entity_id="card_99",
            source_entity_id="trello_junior",
            target_entity_id="gh_junior",
            linkage_type="mentions",
            event_at=event_at,
            state_path=tmp_state_file,
        )
        keys = [e["key"] for e in state["processed_linkage_keys"]["trello"]]
        assert "trello:card_99:link_trello" in keys


# ---------------------------------------------------------------------------
# compact_processed_keys — both new sections
# ---------------------------------------------------------------------------

class TestCompactSemanticKeys:
    def test_compact_removes_old_decision_keys(self, tmp_state_file):
        old_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        recent_at = datetime.now(timezone.utc) - timedelta(days=10)
        state = load_state(tmp_state_file)
        state["processed_decision_keys"]["github"] = [
            {"key": "github:e_old:c_old:h_old", "entity_id": "e_old", "claim_id": "c_old",
             "confidence": 0.9, "event_at": old_at.isoformat()},
            {"key": "github:e_new:c_new:h_new", "entity_id": "e_new", "claim_id": "c_new",
             "confidence": 0.9, "event_at": recent_at.isoformat()},
        ]
        save_state(state, tmp_state_file)

        compacted = compact_processed_keys(state_path=tmp_state_file, retention_days=180)
        keys = [e["key"] for e in compacted["processed_decision_keys"]["github"]]
        assert "github:e_old:c_old:h_old" not in keys
        assert "github:e_new:c_new:h_new" in keys

    def test_compact_removes_old_linkage_keys(self, tmp_state_file):
        old_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        recent_at = datetime.now(timezone.utc) - timedelta(days=10)
        state = load_state(tmp_state_file)
        state["processed_linkage_keys"]["tldv"] = [
            {"key": "tldv:p_old:link_old", "entity_id": "p_old",
             "source_entity_id": "s_old", "target_entity_id": "t_old",
             "linkage_type": "old_type", "event_at": old_at.isoformat()},
            {"key": "tldv:p_new:link_new", "entity_id": "p_new",
             "source_entity_id": "s_new", "target_entity_id": "t_new",
             "linkage_type": "new_type", "event_at": recent_at.isoformat()},
        ]
        save_state(state, tmp_state_file)

        compacted = compact_processed_keys(state_path=tmp_state_file, retention_days=180)
        keys = [e["key"] for e in compacted["processed_linkage_keys"]["tldv"]]
        assert "tldv:p_old:link_old" not in keys
        assert "tldv:p_new:link_new" in keys

    def test_compact_removes_old_keys_across_all_sections(self, tmp_state_file):
        """compact must clean event_keys, content_keys, decision_keys, AND linkage_keys."""
        old_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        recent_at = datetime.now(timezone.utc) - timedelta(days=5)
        state = load_state(tmp_state_file)
        state["processed_event_keys"]["github"] = [
            {"key": "github:old_evt", "event_at": old_at.isoformat()},
        ]
        state["processed_content_keys"]["github"] = [
            {"key": "github:old_ctn", "event_at": old_at.isoformat()},
        ]
        state["processed_decision_keys"]["github"] = [
            {"key": "github:old_dec", "entity_id": "e", "claim_id": "c",
             "confidence": 0.9, "event_at": old_at.isoformat()},
        ]
        state["processed_linkage_keys"]["github"] = [
            {"key": "github:old_lnk", "entity_id": "p",
             "source_entity_id": "s", "target_entity_id": "t",
             "linkage_type": "old", "event_at": old_at.isoformat()},
        ]
        save_state(state, tmp_state_file)

        compacted = compact_processed_keys(state_path=tmp_state_file, retention_days=180)
        assert len(compacted["processed_event_keys"]["github"]) == 0
        assert len(compacted["processed_content_keys"]["github"]) == 0
        assert len(compacted["processed_decision_keys"]["github"]) == 0
        assert len(compacted["processed_linkage_keys"]["github"]) == 0


# ---------------------------------------------------------------------------
# monthly_snapshot — both new sections included
# ---------------------------------------------------------------------------

class TestMonthlySnapshotSemanticKeys:
    def test_snapshot_includes_decision_keys(self, tmp_state_file):
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_decision_key(
            "github", "github:dec1:cl1:h1", "dec1", "cl1", 0.85, event_at, tmp_state_file
        )
        snapshot = monthly_snapshot(state_path=tmp_state_file)
        assert "processed_decision_keys" in snapshot
        assert "github" in snapshot["processed_decision_keys"]
        assert len(snapshot["processed_decision_keys"]["github"]) == 1

    def test_snapshot_includes_linkage_keys(self, tmp_state_file):
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_linkage_key(
            "tldv", "tldv:lnk1:link_h1", "lnk1", "s1", "t1", "type1", event_at, tmp_state_file
        )
        snapshot = monthly_snapshot(state_path=tmp_state_file)
        assert "processed_linkage_keys" in snapshot
        assert "tldv" in snapshot["processed_linkage_keys"]
        assert len(snapshot["processed_linkage_keys"]["tldv"]) == 1

    def test_snapshot_does_not_mutate_state(self, tmp_state_file):
        original = tmp_state_file.read_text()
        monthly_snapshot(state_path=tmp_state_file)
        assert tmp_state_file.read_text() == original


# ---------------------------------------------------------------------------
# state_metrics — decision_key_count + linkage_key_count
# ---------------------------------------------------------------------------

class TestStateMetricsSemanticKeys:
    def test_metrics_includes_decision_key_count(self, tmp_state_file):
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_decision_key(
            "github", "github:dm1:cm1:h1", "dm1", "cm1", 0.85, event_at, tmp_state_file
        )
        upsert_processed_decision_key(
            "github", "github:dm2:cm2:h2", "dm2", "cm2", 0.90, event_at, tmp_state_file
        )
        upsert_processed_decision_key(
            "tldv", "tldv:dm3:cm3:h3", "dm3", "cm3", 0.80, event_at, tmp_state_file
        )
        metrics = state_metrics(state_path=tmp_state_file)
        assert "decision_key_count" in metrics["github"]
        assert "decision_key_count" in metrics["tldv"]
        assert metrics["github"]["decision_key_count"] == 2
        assert metrics["tldv"]["decision_key_count"] == 1

    def test_metrics_includes_linkage_key_count(self, tmp_state_file):
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_linkage_key(
            "github", "github:lm1:link_x", "lm1", "s1", "t1", "rel1", event_at, tmp_state_file
        )
        upsert_processed_linkage_key(
            "github", "github:lm2:link_y", "lm2", "s2", "t2", "rel2", event_at, tmp_state_file
        )
        upsert_processed_linkage_key(
            "tldv", "tldv:lm3:link_z", "lm3", "s3", "t3", "rel3", event_at, tmp_state_file
        )
        metrics = state_metrics(state_path=tmp_state_file)
        assert "linkage_key_count" in metrics["github"]
        assert "linkage_key_count" in metrics["tldv"]
        assert metrics["github"]["linkage_key_count"] == 2
        assert metrics["tldv"]["linkage_key_count"] == 1
