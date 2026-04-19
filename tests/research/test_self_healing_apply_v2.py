"""Tests for vault/research/self_healing.py — SELF_HEALING_POLICY_VERSION=v2 + apply_merge_to_ssot.

RED phase: policy v2 (strict >= 0.85), idempotency, and SSOT persistence.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from vault.research.self_healing import apply_decision, apply_merge_to_ssot, load_metrics, save_metrics


METRICS_EMPTY = {
    "applied": 0,
    "queued": 0,
    "dropped": 0,
    "skipped": 0,
    "dry_run": 0,
    "last_applied_at": None,
    "last_queued_at": None,
    "last_dropped_at": None,
}


# ---------------------------------------------------------------------------
# Helpers — policy tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_metrics_file(tmp_path):
    p = tmp_path / "self_healing_metrics.json"
    p.write_text(json.dumps(dict(METRICS_EMPTY)))
    return p


# ---------------------------------------------------------------------------
# Helpers — SSOT apply tests
# ---------------------------------------------------------------------------

def _make_state(applied_merges=None):
    return {
        "processed_event_keys": {"github": [], "tldv": [], "trello": []},
        "processed_content_keys": {"github": [], "tldv": [], "trello": []},
        "last_seen_at": {"github": None, "tldv": None, "trello": None},
        "pending_conflicts": [],
        "version": 1,
        "applied_merges": applied_merges or [],
    }


def _make_decision(merge_id="abc123", decision="applied", confidence=0.90, source="github"):
    return {
        "decision": decision,
        "confidence": confidence,
        "source": source,
        "policy_version": "v2",
        "merge_id": merge_id,
        "reason": f"confidence {confidence:.2f} >= 0.85",
    }


@pytest.fixture()
def tmp_ssot(tmp_path):
    state_file = tmp_path / "state" / "identity-graph" / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(_make_state()))
    return state_file


@pytest.fixture()
def tmp_lock_path(tmp_path):
    lock_file = tmp_path / "state" / "identity-graph" / ".lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    return str(lock_file)


# =============================================================================
# PART 1 — SELF_HEALING_POLICY_VERSION=v2
# =============================================================================

def test_policy_v2_high_confidence_applies(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v2"}):
        result = apply_decision(
            hypothesis={"entity": "test"}, confidence=0.92, source="github",
            metrics_path=tmp_metrics_file,
        )
    assert result["decision"] == "applied"
    assert result["policy_version"] == "v2"


def test_policy_v2_exact_threshold_085_applies(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v2"}):
        result = apply_decision(
            hypothesis={"entity": "test"}, confidence=0.85, source="tldv",
            metrics_path=tmp_metrics_file,
        )
    assert result["decision"] == "applied"
    assert result["policy_version"] == "v2"


def test_policy_v2_070_084_is_queued(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v2"}):
        result = apply_decision(
            hypothesis={"entity": "test"}, confidence=0.75, source="trello",
            metrics_path=tmp_metrics_file,
        )
    assert result["decision"] == "queued"
    assert result["policy_version"] == "v2"


def test_policy_v2_070_084_not_applied(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v2"}):
        apply_decision(
            hypothesis={"entity": "test"}, confidence=0.80, source="github",
            metrics_path=tmp_metrics_file,
        )
    metrics = json.loads(tmp_metrics_file.read_text())
    assert metrics["applied"] == 0
    assert metrics["queued"] == 1


def test_policy_v2_069_is_queued(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v2"}):
        result = apply_decision(
            hypothesis={"entity": "test"}, confidence=0.69, source="github",
            metrics_path=tmp_metrics_file,
        )
    assert result["decision"] == "queued"


def test_policy_v2_044_is_dropped(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v2"}):
        result = apply_decision(
            hypothesis={"entity": "test"}, confidence=0.44, source="github",
            metrics_path=tmp_metrics_file,
        )
    assert result["decision"] == "dropped"


def test_policy_v1_aggressive_mode_still_applies_070_084(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v1", "SELF_HEALING_AGGRESSIVE_MODE": "true"}):
        result = apply_decision(
            hypothesis={"entity": "test"}, confidence=0.75, source="github",
            metrics_path=tmp_metrics_file,
        )
    assert result["decision"] == "applied"


def test_policy_v1_aggressive_disabled_070_084_skips(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v1", "SELF_HEALING_AGGRESSIVE_MODE": "false"}):
        result = apply_decision(
            hypothesis={"entity": "test"}, confidence=0.80, source="github",
            metrics_path=tmp_metrics_file,
        )
    assert result["decision"] == "skipped"


def test_policy_v1_high_confidence_still_applies(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v1", "SELF_HEALING_AGGRESSIVE_MODE": "false"}):
        result = apply_decision(
            hypothesis={"entity": "test"}, confidence=0.95, source="github",
            metrics_path=tmp_metrics_file,
        )
    assert result["decision"] == "applied"


def test_no_policy_version_defaults_to_v1(tmp_metrics_file):
    env_clean = {k: v for k, v in os.environ.items() if k != "SELF_HEALING_POLICY_VERSION"}
    with patch.dict(os.environ, env_clean, clear=True):
        with patch.dict(os.environ, {"SELF_HEALING_AGGRESSIVE_MODE": "true"}):
            result = apply_decision(
                hypothesis={"entity": "test"}, confidence=0.75, source="github",
                metrics_path=tmp_metrics_file,
            )
    assert result["policy_version"] == "v1"
    assert result["decision"] == "applied"


def test_apply_decision_returns_policy_version_field(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v2"}):
        result = apply_decision(
            hypothesis={"entity": "test"}, confidence=0.90, source="github",
            metrics_path=tmp_metrics_file,
        )
    assert "policy_version" in result
    assert result["policy_version"] == "v2"


def test_metrics_schema_upgrades_from_v1_on_first_write(tmp_path):
    metrics_file = tmp_path / "self_healing_metrics.json"
    metrics_file.write_text(json.dumps(dict(METRICS_EMPTY)))
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v2"}):
        apply_decision(
            hypothesis={"entity": "test"}, confidence=0.90, source="github",
            metrics_path=metrics_file,
        )
    data = json.loads(metrics_file.read_text())
    assert data.get("schema_version") == 2
    assert "hourly_24h" in data
    assert "contradictions_detected" in data
    assert data["applied"] == 1


def test_metrics_v2_file_preserves_schema_on_subsequent_writes(tmp_metrics_file):
    v2_metrics = dict(METRICS_EMPTY, schema_version=2, hourly_24h={})
    tmp_metrics_file.write_text(json.dumps(v2_metrics))
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v2"}):
        apply_decision(
            hypothesis={"entity": "test"}, confidence=0.90, source="github",
            metrics_path=tmp_metrics_file,
        )
    data = json.loads(tmp_metrics_file.read_text())
    assert data["schema_version"] == 2
    assert data["applied"] == 1


def test_apply_decision_returns_merge_id(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v2"}):
        result = apply_decision(
            hypothesis={"entity": "test"}, confidence=0.90, source="github",
            metrics_path=tmp_metrics_file,
        )
    assert result["decision"] == "applied"
    assert "merge_id" in result
    assert isinstance(result["merge_id"], str)
    assert len(result["merge_id"]) > 0


def test_merge_id_is_deterministic(tmp_metrics_file):
    kwargs = {
        "hypothesis": {"entity": "person:github:foo"},
        "confidence": 0.90,
        "source": "github",
        "metrics_path": tmp_metrics_file,
    }
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v2"}):
        r1 = apply_decision(**kwargs)
        r2 = apply_decision(**kwargs)
    assert r1["merge_id"] == r2["merge_id"]
    assert r1["decision"] == r2["decision"] == "applied"


def test_different_confidence_different_merge_id(tmp_metrics_file):
    base = {
        "hypothesis": {"entity": "person:github:foo"},
        "source": "github",
        "metrics_path": tmp_metrics_file,
    }
    with patch.dict(os.environ, {"SELF_HEALING_POLICY_VERSION": "v2"}):
        r1 = apply_decision(confidence=0.90, **base)
        r2 = apply_decision(confidence=0.91, **base)
    assert r1["merge_id"] != r2["merge_id"]


# =============================================================================
# PART 2 — apply_merge_to_ssot (idempotent, locked)
# =============================================================================

def test_apply_merge_writes_to_ssot(tmp_ssot, tmp_lock_path):
    decision = _make_decision(merge_id="merge-001", confidence=0.92, source="github")
    result = apply_merge_to_ssot(
        decision=decision,
        winner_claim={"id": "claim:1", "entity_id": "person:github:foo"},
        loser_claim={"id": "claim:2", "entity_id": "person:github:bar"},
        entity_id="person:github:foo",
        event_key="github:pr_merged:42",
        state_path=tmp_ssot,
        lock_path=tmp_lock_path,
    )
    assert result["state_changed"] is True
    assert result["merge_id"] == "merge-001"
    state = json.loads(tmp_ssot.read_text())
    assert len(state["applied_merges"]) == 1
    assert state["applied_merges"][0]["merge_id"] == "merge-001"


def test_apply_merge_idempotent_second_call_skips(tmp_ssot, tmp_lock_path):
    d1 = _make_decision(merge_id="merge-001")
    r1 = apply_merge_to_ssot(
        decision=d1,
        winner_claim={"id": "claim:1"},
        loser_claim={"id": "claim:2"},
        entity_id="person:github:foo",
        event_key="github:pr_merged:42",
        state_path=tmp_ssot,
        lock_path=tmp_lock_path,
    )
    d2 = _make_decision(merge_id="merge-001")
    r2 = apply_merge_to_ssot(
        decision=d2,
        winner_claim={"id": "claim:1"},
        loser_claim={"id": "claim:2"},
        entity_id="person:github:foo",
        event_key="github:pr_merged:42",
        state_path=tmp_ssot,
        lock_path=tmp_lock_path,
    )
    assert r1["state_changed"] is True
    assert r2["state_changed"] is False
    state = json.loads(tmp_ssot.read_text())
    assert len(state["applied_merges"]) == 1


def test_non_applied_decision_returns_state_changed_false(tmp_ssot, tmp_lock_path):
    decision = _make_decision(decision="queued")
    result = apply_merge_to_ssot(
        decision=decision,
        winner_claim={"id": "claim:1"},
        loser_claim={"id": "claim:2"},
        entity_id="person:github:foo",
        event_key="github:pr_merged:42",
        state_path=tmp_ssot,
        lock_path=tmp_lock_path,
    )
    assert result["state_changed"] is False
    assert result["reason"] == "no-apply-needed"
    state = json.loads(tmp_ssot.read_text())
    assert state["applied_merges"] == []


def test_lock_timeout_skips(tmp_ssot, tmp_lock_path):
    decision = _make_decision(merge_id="merge-001")
    with patch("vault.research.self_healing.acquire_lock", return_value=False):
        result = apply_merge_to_ssot(
            decision=decision,
            winner_claim={"id": "claim:1"},
            loser_claim=None,
            entity_id="person:github:foo",
            event_key="github:pr_merged:42",
            state_path=tmp_ssot,
            lock_path=tmp_lock_path,
            lock_ttl=1,
        )
    assert result["state_changed"] is False
    assert result["reason"] == "lock-timeout"


def test_applied_merge_record_has_required_fields(tmp_ssot, tmp_lock_path):
    decision = _make_decision(merge_id="merge-xyz", confidence=0.91, source="trello")
    apply_merge_to_ssot(
        decision=decision,
        winner_claim={"id": "claim:A", "entity_id": "person:github:foo"},
        loser_claim={"id": "claim:B", "entity_id": "person:github:bar"},
        entity_id="person:github:foo",
        event_key="trello:card:xyz",
        state_path=tmp_ssot,
        lock_path=tmp_lock_path,
    )
    state = json.loads(tmp_ssot.read_text())
    entry = state["applied_merges"][0]
    for field in ("merge_id", "applied_at", "source", "event_key", "entity_id",
                  "winner_claim_id", "confidence", "policy_version", "contradiction"):
        assert field in entry, f"missing {field}"
    assert entry["source"] == "trello"
    assert entry["confidence"] == 0.91


def test_contradiction_flag_from_decision(tmp_ssot, tmp_lock_path):
    decision = _make_decision(merge_id="m1")
    decision["contradiction"] = True
    apply_merge_to_ssot(
        decision=decision,
        winner_claim={"id": "claim:1"},
        loser_claim={"id": "claim:2"},
        entity_id="person:github:foo",
        event_key="github:pr_merged:1",
        state_path=tmp_ssot,
        lock_path=tmp_lock_path,
    )
    state = json.loads(tmp_ssot.read_text())
    assert state["applied_merges"][0]["contradiction"] is True


def test_loser_claim_optional(tmp_ssot, tmp_lock_path):
    decision = _make_decision(merge_id="solo-001")
    result = apply_merge_to_ssot(
        decision=decision,
        winner_claim={"id": "claim:1"},
        loser_claim=None,
        entity_id="person:github:foo",
        event_key="github:pr_merged:99",
        state_path=tmp_ssot,
        lock_path=tmp_lock_path,
    )
    assert result["state_changed"] is True
    state = json.loads(tmp_ssot.read_text())
    assert state["applied_merges"][0]["loser_claim_id"] is None


def test_applied_merges_pruned_older_than_180_days(tmp_ssot, tmp_lock_path):
    from datetime import datetime, timezone, timedelta
    old_entry = {
        "merge_id": "old-merge",
        "applied_at": (datetime.now(timezone.utc) - timedelta(days=200)).isoformat(),
        "source": "github",
        "event_key": "github:pr_merged:1",
        "entity_id": "person:github:foo",
        "winner_claim_id": "claim:old",
        "loser_claim_id": None,
        "confidence": 0.92,
        "contradiction": False,
        "policy_version": "v1",
        "reason": "test",
    }
    tmp_ssot.write_text(json.dumps(_make_state(applied_merges=[old_entry])))
    decision = _make_decision(merge_id="new-merge")
    apply_merge_to_ssot(
        decision=decision,
        winner_claim={"id": "claim:1"},
        loser_claim=None,
        entity_id="person:github:foo",
        event_key="github:pr_merged:99",
        state_path=tmp_ssot,
        lock_path=tmp_lock_path,
    )
    state = json.loads(tmp_ssot.read_text())
    ids = [e["merge_id"] for e in state["applied_merges"]]
    assert "old-merge" not in ids
    assert "new-merge" in ids
