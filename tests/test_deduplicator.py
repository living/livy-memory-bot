"""TDD tests for semantic deduplicator with temporal window."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest


DEDUP_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "memoria-consolidation"
    / "deduplicator.py"
)


def _load_dedup_module():
    if not DEDUP_FILE.exists():
        raise ModuleNotFoundError(f"Missing production deduplicator module: {DEDUP_FILE}")

    spec = importlib.util.spec_from_file_location("memoria_consolidation_deduplicator", DEDUP_FILE)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load dedup module spec from {DEDUP_FILE}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_fingerprint(topic: str, entity_key: str, rule_id: str) -> str:
    """Compute fingerprint the same way the dedup module should."""
    module = _load_dedup_module()
    return module.make_fingerprint(topic, entity_key, rule_id)


def _is_duplicate(fingerprint: str, ledger: list[dict[str, Any]], now: datetime | None = None) -> bool:
    """Check if fingerprint is a duplicate within 7-day window."""
    module = _load_dedup_module()
    return module.is_duplicate(fingerprint, ledger, now=now)


def _filter_duplicate_signals(signals: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    """Filter duplicate signals, returning only non-duplicates."""
    module = _load_dedup_module()
    return module.filter_duplicate_signals(signals, now=now)


class TestFingerprintCollisionSafety:
    """Fingerprints must be unique per (topic, entity_key, rule_id) triple."""

    def test_same_inputs_produce_same_fingerprint(self):
        fp = _make_fingerprint("machine learning", "entity_123", "R001")
        fp2 = _make_fingerprint("machine learning", "entity_123", "R001")
        assert fp == fp2

    def test_different_topics_produce_different_fingerprints(self):
        fp1 = _make_fingerprint("machine learning", "entity_123", "R001")
        fp2 = _make_fingerprint("deep learning", "entity_123", "R001")
        assert fp1 != fp2

    def test_different_entity_keys_produce_different_fingerprints(self):
        fp1 = _make_fingerprint("machine learning", "entity_123", "R001")
        fp2 = _make_fingerprint("machine learning", "entity_456", "R001")
        assert fp1 != fp2

    def test_different_rule_ids_produce_different_fingerprints(self):
        fp1 = _make_fingerprint("machine learning", "entity_123", "R001")
        fp2 = _make_fingerprint("machine learning", "entity_123", "R002")
        assert fp1 != fp2

    def test_fingerprint_is_deterministic_not_random(self):
        """Same inputs always produce same output across multiple calls."""
        fp1 = _make_fingerprint("topic", "key", "rule")
        fp2 = _make_fingerprint("topic", "key", "rule")
        fp3 = _make_fingerprint("topic", "key", "rule")
        assert fp1 == fp2 == fp3


class TestSevenDayTemporalWindow:
    """Decisions newer than 7 days count as duplicates."""

    def test_signal_within_7_days_is_duplicate(self):
        now = datetime(2026, 4, 9, 22, 0, 0, tzinfo=timezone.utc)
        ledger = [
            {
                "fingerprint": _make_fingerprint("ml", "e1", "R001"),
                "decided_at": "2026-04-09T10:00:00Z",  # Same day
            }
        ]
        assert _is_duplicate(_make_fingerprint("ml", "e1", "R001"), ledger, now=now) is True

    def test_signal_at_exactly_7_days_old_is_not_duplicate(self):
        now = datetime(2026, 4, 9, 22, 0, 0, tzinfo=timezone.utc)
        # 7 days ago exactly - boundary case
        ledger = [
            {
                "fingerprint": _make_fingerprint("ml", "e1", "R001"),
                "decided_at": "2026-04-02T22:00:00Z",
            }
        ]
        assert _is_duplicate(_make_fingerprint("ml", "e1", "R001"), ledger, now=now) is False

    def test_signal_older_than_7_days_is_not_duplicate(self):
        now = datetime(2026, 4, 9, 22, 0, 0, tzinfo=timezone.utc)
        ledger = [
            {
                "fingerprint": _make_fingerprint("ml", "e1", "R001"),
                "decided_at": "2026-04-01T10:00:00Z",  # 8+ days ago
            }
        ]
        assert _is_duplicate(_make_fingerprint("ml", "e1", "R001"), ledger, now=now) is False

    def test_signal_at_6_days_23_hours_is_duplicate(self):
        now = datetime(2026, 4, 9, 22, 0, 0, tzinfo=timezone.utc)
        # 6 days, 23 hours, 59 minutes ago - still within window
        ledger = [
            {
                "fingerprint": _make_fingerprint("ml", "e1", "R001"),
                "decided_at": "2026-04-02T22:01:00Z",
            }
        ]
        assert _is_duplicate(_make_fingerprint("ml", "e1", "R001"), ledger, now=now) is True


class TestIsDuplicateAPI:
    """is_duplicate API behavior."""

    def test_empty_ledger_returns_false(self):
        assert _is_duplicate(_make_fingerprint("ml", "e1", "R001"), []) is False

    def test_mismatched_fingerprint_returns_false(self):
        ledger = [
            {"fingerprint": "different_fingerprint", "decided_at": "2026-04-09T10:00:00Z"}
        ]
        assert _is_duplicate("other_fingerprint", ledger) is False

    def test_missing_fingerprint_in_ledger_returns_false(self):
        ledger = [
            {"decided_at": "2026-04-09T10:00:00Z"}  # No fingerprint key
        ]
        assert _is_duplicate(_make_fingerprint("ml", "e1", "R001"), ledger) is False


class TestFilterDuplicateSignals:
    """filter_duplicate_signals removes duplicates, keeps unique signals."""

    def test_single_unique_signal_passes_through(self):
        now = datetime(2026, 4, 9, 22, 0, 0, tzinfo=timezone.utc)
        signals = [
            {"topic": "ml", "entity_key": "e1", "rule_id": "R001", "decided_at": "2026-04-09T10:00:00Z"}
        ]
        result = _filter_duplicate_signals(signals, now=now)
        assert len(result) == 1
        assert result[0]["entity_key"] == "e1"

    def test_duplicate_signal_is_removed(self):
        now = datetime(2026, 4, 9, 22, 0, 0, tzinfo=timezone.utc)
        signals = [
            {"topic": "ml", "entity_key": "e1", "rule_id": "R001", "decided_at": "2026-04-09T10:00:00Z"},
            {"topic": "ml", "entity_key": "e1", "rule_id": "R001", "decided_at": "2026-04-09T11:00:00Z"},
        ]
        result = _filter_duplicate_signals(signals, now=now)
        assert len(result) == 1  # Only one should survive

    def test_multiple_different_signals_all_pass(self):
        now = datetime(2026, 4, 9, 22, 0, 0, tzinfo=timezone.utc)
        signals = [
            {"topic": "ml", "entity_key": "e1", "rule_id": "R001", "decided_at": "2026-04-09T10:00:00Z"},
            {"topic": "dl", "entity_key": "e2", "rule_id": "R001", "decided_at": "2026-04-09T10:00:00Z"},
            {"topic": "ml", "entity_key": "e3", "rule_id": "R002", "decided_at": "2026-04-09T10:00:00Z"},
        ]
        result = _filter_duplicate_signals(signals, now=now)
        assert len(result) == 3  # All unique

    def test_signals_beyond_window_are_not_duplicates(self):
        now = datetime(2026, 4, 9, 22, 0, 0, tzinfo=timezone.utc)
        signals = [
            {"topic": "ml", "entity_key": "e1", "rule_id": "R001", "decided_at": "2026-04-01T10:00:00Z"},  # 8 days old
            {"topic": "ml", "entity_key": "e1", "rule_id": "R001", "decided_at": "2026-04-09T10:00:00Z"},  # Today
        ]
        result = _filter_duplicate_signals(signals, now=now)
        # Both should pass since the old one is beyond the 7-day window
        assert len(result) == 2

    def test_preserves_original_signal_data(self):
        now = datetime(2026, 4, 9, 22, 0, 0, tzinfo=timezone.utc)
        signals = [
            {"topic": "machine learning", "entity_key": "entity_xyz", "rule_id": "R005",
             "decided_at": "2026-04-09T10:00:00Z", "confidence": 0.95, "extra_field": "preserved"}
        ]
        result = _filter_duplicate_signals(signals, now=now)
        assert len(result) == 1
        assert result[0]["extra_field"] == "preserved"
        assert result[0]["confidence"] == 0.95


class TestDeduplicatorModule:
    """Module-level requirements."""

    def test_module_exists(self):
        module = _load_dedup_module()
        assert module is not None

    def test_module_exports_required_functions(self):
        module = _load_dedup_module()
        assert hasattr(module, "make_fingerprint")
        assert hasattr(module, "is_duplicate")
        assert hasattr(module, "filter_duplicate_signals")
