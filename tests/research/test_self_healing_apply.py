"""Tests for vault/research/self_healing.py — apply_decision with confidence thresholds."""

import json
import os
from unittest.mock import patch

import pytest

from vault.research.self_healing import apply_decision, load_metrics, save_metrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

METRICS_DEFAULT = {
    "applied": 0,
    "queued": 0,
    "dropped": 0,
    "skipped": 0,
    "dry_run": 0,
    "last_applied_at": None,
    "last_queued_at": None,
    "last_dropped_at": None,
}


@pytest.fixture()
def tmp_metrics_file(tmp_path):
    p = tmp_path / "self_healing_metrics.json"
    p.write_text(json.dumps(METRICS_DEFAULT))
    return p



# ---------------------------------------------------------------------------
# Confidence threshold: >= 0.85 → applied
# ---------------------------------------------------------------------------

def test_apply_high_confidence_applies(tmp_metrics_file):
    result = apply_decision(
        hypothesis={"entity": "test", "change": "update_name"},
        confidence=0.90,
        source="github",
        metrics_path=tmp_metrics_file,
    )
    assert result["decision"] == "applied"
    assert result["confidence"] == 0.90
    assert result["source"] == "github"
    assert "reason" in result


def test_apply_exact_threshold_85_applies(tmp_metrics_file):
    result = apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.85,
        source="tldv",
        metrics_path=tmp_metrics_file,
    )
    assert result["decision"] == "applied"


# ---------------------------------------------------------------------------
# Confidence threshold: 0.70–0.84 → applied + verbose log
# ---------------------------------------------------------------------------

def test_apply_aggressive_range_applies(tmp_metrics_file):
    result = apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.75,
        source="trello",
        metrics_path=tmp_metrics_file,
    )
    assert result["decision"] == "applied"


def test_apply_aggressive_range_emits_verbose_entry(tmp_metrics_file, caplog):
    import logging
    with caplog.at_level(logging.INFO):
        with patch.dict(os.environ, {"SELF_HEALING_AGGRESSIVE_MODE": "true"}):
            result = apply_decision(
                hypothesis={"entity": "test"},
                confidence=0.72,
                source="github",
                metrics_path=tmp_metrics_file,
                    )
    assert result["decision"] == "applied"
    assert any("0.72" in r.message or "AGGRESSIVE" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Confidence threshold: 0.70–0.84 → skipped when aggressive mode disabled
# ---------------------------------------------------------------------------

def test_apply_aggressive_disabled_skips_70_84(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_AGGRESSIVE_MODE": "false"}):
        result = apply_decision(
            hypothesis={"entity": "test"},
            confidence=0.80,
            source="github",
            metrics_path=tmp_metrics_file,
            )
    assert result["decision"] == "skipped"


# ---------------------------------------------------------------------------
# Confidence threshold: 0.45–0.69 → queued
# ---------------------------------------------------------------------------

def test_apply_mid_confidence_queues(tmp_metrics_file):
    result = apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.60,
        source="github",
        metrics_path=tmp_metrics_file,
    )
    assert result["decision"] == "queued"


def test_apply_exact_threshold_45_queues(tmp_metrics_file):
    result = apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.45,
        source="tldv",
        metrics_path=tmp_metrics_file,
    )
    assert result["decision"] == "queued"


def test_apply_exact_threshold_69_queues(tmp_metrics_file):
    result = apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.69,
        source="tldv",
        metrics_path=tmp_metrics_file,
    )
    assert result["decision"] == "queued"


# ---------------------------------------------------------------------------
# Confidence threshold: < 0.45 → dropped
# ---------------------------------------------------------------------------

def test_apply_low_confidence_drops(tmp_metrics_file):
    result = apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.30,
        source="github",
        metrics_path=tmp_metrics_file,
    )
    assert result["decision"] == "dropped"


def test_apply_exact_threshold_044_drops(tmp_metrics_file):
    result = apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.44,
        source="github",
        metrics_path=tmp_metrics_file,
    )
    assert result["decision"] == "dropped"


# ---------------------------------------------------------------------------
# SELF_HEALING_WRITE_ENABLED=false → dry-run (skipped, not applied)
# ---------------------------------------------------------------------------

def test_apply_write_disabled_does_dry_run(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_WRITE_ENABLED": "false"}):
        result = apply_decision(
            hypothesis={"entity": "test"},
            confidence=0.90,
            source="github",
            metrics_path=tmp_metrics_file,
            )
    assert result["decision"] == "skipped"
    assert result["reason"] == "dry-run"


# ---------------------------------------------------------------------------
# SELF_HEALING_AGGRESSIVE_MODE=false → skips 0.70-0.84 auto-apply
# ---------------------------------------------------------------------------

def test_aggressive_mode_env_disables_70_84_auto_apply(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_AGGRESSIVE_MODE": "false"}):
        result = apply_decision(
            hypothesis={"entity": "test"},
            confidence=0.75,
            source="github",
            metrics_path=tmp_metrics_file,
            )
    assert result["decision"] == "skipped"


def test_aggressive_mode_env_still_applies_high_confidence(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_AGGRESSIVE_MODE": "false"}):
        result = apply_decision(
            hypothesis={"entity": "test"},
            confidence=0.95,
            source="github",
            metrics_path=tmp_metrics_file,
            )
    assert result["decision"] == "applied"


# ---------------------------------------------------------------------------
# SELF_HEALING_BREAKER_ENABLED=false → skipped with reason "breaker-disabled"
# ---------------------------------------------------------------------------

def test_breaker_disabled_skips_with_reason(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_BREAKER_ENABLED": "false"}):
        result = apply_decision(
            hypothesis={"entity": "test"},
            confidence=0.90,
            source="github",
            metrics_path=tmp_metrics_file,
            )
    assert result["decision"] == "skipped"
    assert result["reason"] == "breaker-disabled"


# ---------------------------------------------------------------------------
# Metrics tracking
# ---------------------------------------------------------------------------

def test_metrics_applied_increments(tmp_metrics_file):
    apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.90,
        source="github",
        metrics_path=tmp_metrics_file,
    )
    metrics = json.loads(tmp_metrics_file.read_text())
    assert metrics["applied"] == 1
    assert metrics["last_applied_at"] is not None


def test_metrics_queued_increments(tmp_metrics_file):
    apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.60,
        source="github",
        metrics_path=tmp_metrics_file,
    )
    metrics = json.loads(tmp_metrics_file.read_text())
    assert metrics["queued"] == 1
    assert metrics["last_queued_at"] is not None


def test_metrics_dropped_increments(tmp_metrics_file):
    apply_decision(
        hypothesis={"entity": "test"},
        confidence=0.30,
        source="github",
        metrics_path=tmp_metrics_file,
    )
    metrics = json.loads(tmp_metrics_file.read_text())
    assert metrics["dropped"] == 1
    assert metrics["last_dropped_at"] is not None


def test_metrics_dry_run_increments(tmp_metrics_file):
    with patch.dict(os.environ, {"SELF_HEALING_WRITE_ENABLED": "false"}):
        apply_decision(
            hypothesis={"entity": "test"},
            confidence=0.90,
            source="github",
            metrics_path=tmp_metrics_file,
            )
    metrics = json.loads(tmp_metrics_file.read_text())
    assert metrics["skipped"] == 1
    assert metrics["dry_run"] == 1


# ---------------------------------------------------------------------------
# Returns complete decision dict
# ---------------------------------------------------------------------------

def test_returns_complete_decision_dict(tmp_metrics_file):
    result = apply_decision(
        hypothesis={"entity": "test", "field": "name", "value": "newname"},
        confidence=0.88,
        source="github",
        metrics_path=tmp_metrics_file,
    )
    assert isinstance(result, dict)
    assert set(result.keys()) == {"decision", "confidence", "reason", "source"}
    assert result["decision"] == "applied"
    assert result["confidence"] == 0.88
    assert result["source"] == "github"
    assert isinstance(result["reason"], str)


# ---------------------------------------------------------------------------
# load_metrics / save_metrics
# ---------------------------------------------------------------------------

def test_load_metrics_returns_defaults(tmp_path):
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps({}))
    metrics = load_metrics(path)
    assert metrics["applied"] == 0
    assert metrics["queued"] == 0
    assert metrics["dropped"] == 0


def test_save_metrics_creates_file(tmp_path):
    path = tmp_path / "metrics.json"
    save_metrics({"applied": 5}, path)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["applied"] == 5
