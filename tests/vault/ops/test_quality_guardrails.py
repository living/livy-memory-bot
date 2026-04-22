"""Tests for quality guardrails in research_consolidation_cron.

Covers:
- _compute_claim_kpis: %decision / %linkage / %status / %needs_review / %with_evidence
- _evaluate_quality_thresholds: threshold evaluation with defaults and custom config
- _count_consecutive_bad_cycles: tracks consecutive bad cycles from history
- _emit_quality_guardrail_alert: writes alert to consolidation log
- _record_quality_cycle: persists cycle result to history file
- _run_quality_guardrail: integration — returns kpis, alerts, consecutive bad count
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Ensure vault package is on path
_root = Path(__file__).resolve().parents[4]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_claims(
    *,
    decision: int = 0,
    linkage: int = 0,
    status: int = 0,
    other: int = 0,
    needs_review: int = 0,
    with_evidence: int = 0,
) -> list[dict]:
    """
    Build a synthetic claims list with the specified distribution.

    needs_review and with_evidence are taken from the decision+linkage+status+other total.
    All needs_review claims get non-empty evidence_ids.
    """
    all_types = []
    for _ in range(decision):
        all_types.append("decision")
    for _ in range(linkage):
        all_types.append("linkage")
    for _ in range(status):
        all_types.append("status")
    for _ in range(other):
        all_types.append("action_item")

    total = len(all_types)
    claims = []
    needs_review_count = min(needs_review, total)
    with_evidence_count = min(with_evidence, total)

    for i, ct in enumerate(all_types):
        needs_review_flag = i < needs_review_count
        has_evidence = i < with_evidence_count
        claims.append({
            "claim_id": f"c{i}",
            "claim_type": ct,
            "needs_review": needs_review_flag,
            "evidence_ids": [f"ev{i}"] if has_evidence else [],
        })
    return claims


# ---------------------------------------------------------------------------
# RED Phase: these tests define expected behaviour.
# Each function must not exist yet — they will fail with NameError.
# ---------------------------------------------------------------------------

class TestComputeClaimKpis:
    """Test _compute_claim_kpis on various claim distributions."""

    def test_empty_claims_returns_zero_kpis(self):
        from vault.crons import research_consolidation_cron as mod
        kpis = mod._compute_claim_kpis([])
        assert kpis["total"] == 0
        assert kpis["pct_decision"] == 0.0
        assert kpis["pct_linkage"] == 0.0
        assert kpis["pct_status"] == 0.0
        assert kpis["pct_needs_review"] == 0.0
        assert kpis["pct_with_evidence"] == 0.0

    def test_all_decision_claims(self):
        from vault.crons import research_consolidation_cron as mod
        claims = _make_claims(decision=10)
        kpis = mod._compute_claim_kpis(claims)
        assert kpis["pct_decision"] == 100.0
        assert kpis["pct_linkage"] == 0.0
        assert kpis["pct_status"] == 0.0

    def test_mixed_claims(self):
        from vault.crons import research_consolidation_cron as mod
        claims = _make_claims(decision=2, linkage=3, status=5, other=10)
        kpis = mod._compute_claim_kpis(claims)
        # total = 20
        assert kpis["pct_decision"] == 10.0     # 2/20
        assert kpis["pct_linkage"] == 15.0      # 3/20
        assert kpis["pct_status"] == 25.0       # 5/20
        assert kpis["total"] == 20

    def test_needs_review_fraction(self):
        from vault.crons import research_consolidation_cron as mod
        # 5 claims, 2 need review → 40%
        claims = _make_claims(decision=3, status=2, needs_review=2)
        kpis = mod._compute_claim_kpis(claims)
        assert kpis["pct_needs_review"] == 40.0

    def test_with_evidence_fraction(self):
        from vault.crons import research_consolidation_cron as mod
        # 10 claims, 7 have evidence → 70%
        claims = _make_claims(decision=5, status=5, with_evidence=7)
        kpis = mod._compute_claim_kpis(claims)
        assert kpis["pct_with_evidence"] == 70.0

    def test_all_need_review_when_empty_claims(self):
        from vault.crons import research_consolidation_cron as mod
        # Edge: no claims → pct_needs_review should be 0, not divide-by-zero
        kpis = mod._compute_claim_kpis([])
        assert kpis["pct_needs_review"] == 0.0


class TestEvaluateQualityThresholds:
    """Test _evaluate_quality_thresholds with various configurations."""

    def test_all_kpis_clear_defaults(self):
        from vault.crons import research_consolidation_cron as mod
        kpis = {
            "pct_decision": 20.0,
            "pct_linkage": 10.0,
            "pct_status": 30.0,
            "pct_needs_review": 5.0,
            "pct_with_evidence": 95.0,
            "total": 100,
        }
        result = mod._evaluate_quality_thresholds(kpis)
        assert result["passed"] is True
        assert result["failed_kpis"] == []

    def test_decision_below_threshold_fails(self):
        from vault.crons import research_consolidation_cron as mod
        # Default min_decision_pct = 5.0, value = 3.0 → fails
        kpis = {
            "pct_decision": 3.0,
            "pct_linkage": 10.0,
            "pct_status": 30.0,
            "pct_needs_review": 5.0,
            "pct_with_evidence": 95.0,
            "total": 100,
        }
        result = mod._evaluate_quality_thresholds(kpis)
        assert result["passed"] is False
        assert "pct_decision" in result["failed_kpis"]

    def test_needs_review_above_threshold_fails(self):
        from vault.crons import research_consolidation_cron as mod
        # Default max_needs_review_pct = 30.0, value = 45.0 → fails
        kpis = {
            "pct_decision": 20.0,
            "pct_linkage": 10.0,
            "pct_status": 25.0,
            "pct_needs_review": 45.0,
            "pct_with_evidence": 95.0,
            "total": 100,
        }
        result = mod._evaluate_quality_thresholds(kpis)
        assert result["passed"] is False
        assert "pct_needs_review" in result["failed_kpis"]

    def test_with_evidence_below_threshold_fails(self):
        from vault.crons import research_consolidation_cron as mod
        # Default min_with_evidence_pct = 80.0, value = 50.0 → fails
        kpis = {
            "pct_decision": 20.0,
            "pct_linkage": 10.0,
            "pct_status": 20.0,
            "pct_needs_review": 5.0,
            "pct_with_evidence": 50.0,
            "total": 100,
        }
        result = mod._evaluate_quality_thresholds(kpis)
        assert result["passed"] is False
        assert "pct_with_evidence" in result["failed_kpis"]

    def test_custom_thresholds(self):
        from vault.crons import research_consolidation_cron as mod
        kpis = {
            "pct_decision": 8.0,
            "pct_linkage": 5.0,
            "pct_status": 20.0,
            "pct_needs_review": 25.0,
            "pct_with_evidence": 70.0,
            "total": 100,
        }
        # Pass when all custom thresholds allow
        result = mod._evaluate_quality_thresholds(
            kpis,
            thresholds={
                "min_decision_pct": 5.0,
                "max_needs_review_pct": 30.0,
                "min_with_evidence_pct": 60.0,
                "max_consecutive_bad_cycles": 2,
            },
        )
        assert result["passed"] is True
        assert result["failed_kpis"] == []

    def test_empty_claims_uses_zero_failed_kpis(self):
        from vault.crons import research_consolidation_cron as mod
        kpis = {
            "total": 0,
            "pct_decision": 0.0,
            "pct_linkage": 0.0,
            "pct_status": 0.0,
            "pct_needs_review": 0.0,
            "pct_with_evidence": 0.0,
        }
        # Empty claims → pct_with_evidence = 0 < 80 → fails by default
        # but with empty_thresholds_treats_as_pass=True it should pass
        result = mod._evaluate_quality_thresholds(
            kpis,
            empty_thresholds_treats_as_pass=True,
        )
        assert result["passed"] is True
        assert result["failed_kpis"] == []


class TestCountConsecutiveBadCycles:
    """Test _count_consecutive_bad_cycles from cycle history."""

    def test_empty_history_returns_zero(self):
        from vault.crons import research_consolidation_cron as mod
        count = mod._count_consecutive_bad_cycles([])
        assert count == 0

    def test_single_bad_cycle_returns_one(self):
        from vault.crons import research_consolidation_cron as mod
        history = [{"passed": False, "run_at": "2026-04-21T00:00:00Z"}]
        count = mod._count_consecutive_bad_cycles(history)
        assert count == 1

    def test_two_consecutive_bad_cycles_returns_two(self):
        from vault.crons import research_consolidation_cron as mod
        history = [
            {"passed": False, "run_at": "2026-04-20T00:00:00Z"},
            {"passed": False, "run_at": "2026-04-21T00:00:00Z"},
        ]
        count = mod._count_consecutive_bad_cycles(history)
        assert count == 2

    def test_intervening_good_cycle_resets_count(self):
        from vault.crons import research_consolidation_cron as mod
        history = [
            {"passed": False, "run_at": "2026-04-19T00:00:00Z"},
            {"passed": True,  "run_at": "2026-04-20T00:00:00Z"},
            {"passed": False, "run_at": "2026-04-21T00:00:00Z"},
        ]
        count = mod._count_consecutive_bad_cycles(history)
        assert count == 1

    def test_old_bad_cycles_before_good_do_not_count(self):
        from vault.crons import research_consolidation_cron as mod
        history = [
            {"passed": False, "run_at": "2026-04-18T00:00:00Z"},
            {"passed": False, "run_at": "2026-04-19T00:00:00Z"},
            {"passed": True,  "run_at": "2026-04-20T00:00:00Z"},
        ]
        count = mod._count_consecutive_bad_cycles(history)
        assert count == 0

    def test_most_recent_is_good_returns_zero(self):
        from vault.crons import research_consolidation_cron as mod
        history = [
            {"passed": False, "run_at": "2026-04-19T00:00:00Z"},
            {"passed": True,  "run_at": "2026-04-20T00:00:00Z"},
        ]
        count = mod._count_consecutive_bad_cycles(history)
        assert count == 0


class TestEmitQualityGuardrailAlert:
    """Test _emit_quality_guardrail_alert writes to consolidation log."""

    def test_writes_alert_to_consolidation_log(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        log_path = tmp_path / "memory" / "consolidation-log.md"
        monkeypatch.setattr(mod, "CONSOLIDATION_LOG", str(log_path))

        alert = {
            "alert_type": "quality_guardrail_fail",
            "failed_kpis": ["pct_decision", "pct_needs_review"],
            "kpis": {
                "pct_decision": 2.0,
                "pct_needs_review": 50.0,
                "total": 100,
            },
            "consecutive_bad_cycles": 2,
            "message": "quality guardrail failed: pct_decision 2.0 < 5.0, pct_needs_review 50.0 > 30.0",
        }
        mod._emit_quality_guardrail_alert(alert)

        assert log_path.exists()
        content = log_path.read_text()
        assert "quality_guardrail_fail" in content
        assert "pct_decision" in content
        assert "consecutive_bad_cycles" in content

    def test_creates_parent_directories(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        log_path = tmp_path / "deeply" / "nested" / "memory" / "consolidation-log.md"
        monkeypatch.setattr(mod, "CONSOLIDATION_LOG", str(log_path))

        alert = {"alert_type": "quality_guardrail_fail", "failed_kpis": [], "kpis": {}, "consecutive_bad_cycles": 1}
        mod._emit_quality_guardrail_alert(alert)
        assert log_path.exists()


class TestRecordQualityCycle:
    """Test _record_quality_cycle persists cycle result."""

    def test_writes_cycle_record(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        hist_path = tmp_path / "quality_history.jsonl"
        monkeypatch.setattr(mod, "QUALITY_HISTORY_PATH", str(hist_path))

        cycle = {
            "run_at": "2026-04-21T07:00:00Z",
            "passed": True,
            "total": 50,
            "failed_kpis": [],
            "kpis": {
                "pct_decision": 10.0,
                "pct_linkage": 5.0,
                "pct_status": 20.0,
                "pct_needs_review": 8.0,
                "pct_with_evidence": 90.0,
            },
        }
        mod._record_quality_cycle(cycle)

        assert hist_path.exists()
        lines = hist_path.read_text().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["passed"] is True
        assert record["total"] == 50

    def test_appends_not_overwrites(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        hist_path = tmp_path / "quality_history.jsonl"
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        hist_path.write_text('{"run_at":"2026-04-20T07:00:00Z","passed":true,"total":0,"failed_kpis":[]}\n')
        monkeypatch.setattr(mod, "QUALITY_HISTORY_PATH", str(hist_path))

        cycle = {"run_at": "2026-04-21T07:00:00Z", "passed": False, "total": 10, "failed_kpis": ["pct_decision"]}
        mod._record_quality_cycle(cycle)

        lines = hist_path.read_text().splitlines()
        assert len(lines) == 2


class TestRunQualityGuardrail:
    """Integration: _run_quality_guardrail wires everything together."""

    def test_passing_kpis_no_alert(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        # Set up state with good claims
        state_path = tmp_path / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({
            "claims": _make_claims(decision=10, linkage=5, status=15, other=20, needs_review=2, with_evidence=48),
            "processed_event_keys": {},
            "processed_content_keys": {},
            "processed_decision_keys": {},
            "processed_linkage_keys": {},
            "version": 1,
        }))
        monkeypatch.setattr(mod, "STATE_PATH", str(state_path))

        hist_path = tmp_path / "quality_history.jsonl"
        monkeypatch.setattr(mod, "QUALITY_HISTORY_PATH", str(hist_path))
        monkeypatch.setattr(mod, "_utc_now", lambda: datetime(2026, 4, 21, 7, 0, 0, tzinfo=timezone.utc))

        result = mod._run_quality_guardrail()

        assert result["alert_emitted"] is False
        assert result["kpis"]["total"] == 50
        assert result["kpis"]["pct_decision"] == 20.0
        assert result["consecutive_bad_cycles"] == 0

    def test_failing_kpis_one_bad_cycle_no_alert(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        state_path = tmp_path / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({
            "claims": _make_claims(decision=1, linkage=1, status=1, other=1, needs_review=4, with_evidence=4),
            "claims_verified": [],
            "processed_event_keys": {},
            "processed_content_keys": {},
            "processed_decision_keys": {},
            "processed_linkage_keys": {},
            "version": 1,
        }))
        monkeypatch.setattr(mod, "STATE_PATH", str(state_path))

        hist_path = tmp_path / "quality_history.jsonl"
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        # No prior history
        monkeypatch.setattr(mod, "QUALITY_HISTORY_PATH", str(hist_path))
        monkeypatch.setattr(mod, "_utc_now", lambda: datetime(2026, 4, 21, 7, 0, 0, tzinfo=timezone.utc))

        result = mod._run_quality_guardrail()

        # 1/4 = 25% decision < 5% threshold, 4/4 = 100% needs_review > 30% → fails
        assert result["alert_emitted"] is False   # only 1 bad cycle, threshold is 2
        assert result["kpis"]["pct_needs_review"] == 100.0
        assert result["consecutive_bad_cycles"] == 1
        assert result["kpis"]["passed"] is False

    def test_two_consecutive_bad_cycles_emits_alert(self, monkeypatch, tmp_path):
        from vault.crons import research_consolidation_cron as mod

        state_path = tmp_path / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({
            "claims": _make_claims(decision=1, linkage=1, status=1, other=1, needs_review=4, with_evidence=4),
            "claims_verified": [],
            "processed_event_keys": {},
            "processed_content_keys": {},
            "processed_decision_keys": {},
            "processed_linkage_keys": {},
            "version": 1,
        }))
        monkeypatch.setattr(mod, "STATE_PATH", str(state_path))

        # History: one prior bad cycle
        hist_path = tmp_path / "quality_history.jsonl"
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        hist_path.write_text(
            '{"run_at":"2026-04-20T07:00:00Z","passed":false,"total":4,'
            '"failed_kpis":["pct_decision"],"kpis":{}}\n'
        )
        monkeypatch.setattr(mod, "QUALITY_HISTORY_PATH", str(hist_path))

        log_path = tmp_path / "memory" / "consolidation-log.md"
        monkeypatch.setattr(mod, "CONSOLIDATION_LOG", str(log_path))
        monkeypatch.setattr(mod, "_utc_now", lambda: datetime(2026, 4, 21, 7, 0, 0, tzinfo=timezone.utc))

        result = mod._run_quality_guardrail()

        # This is the 2nd consecutive bad cycle → alert emitted
        assert result["alert_emitted"] is True
        assert result["consecutive_bad_cycles"] == 2
        assert log_path.exists()
        assert "quality_guardrail_fail" in log_path.read_text()

    def test_empty_claims_no_history_passes_with_empty_thresholds_treats_as_pass(
        self, monkeypatch, tmp_path
    ):
        from vault.crons import research_consolidation_cron as mod

        state_path = tmp_path / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({
            "claims": [],
            "processed_event_keys": {},
            "processed_content_keys": {},
            "processed_decision_keys": {},
            "processed_linkage_keys": {},
            "version": 1,
        }))
        monkeypatch.setattr(mod, "STATE_PATH", str(state_path))

        hist_path = tmp_path / "quality_history.jsonl"
        monkeypatch.setattr(mod, "QUALITY_HISTORY_PATH", str(hist_path))
        monkeypatch.setattr(mod, "_utc_now", lambda: datetime(2026, 4, 21, 7, 0, 0, tzinfo=timezone.utc))

        result = mod._run_quality_guardrail()

        # Empty claims with empty_thresholds_treats_as_pass → passes
        assert result["kpis"]["passed"] is True
        assert result["alert_emitted"] is False
