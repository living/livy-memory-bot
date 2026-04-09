"""TDD tests for risk tier classifier (Task 4)."""

import importlib.util
from pathlib import Path

CLASSIFIER_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "memoria-consolidation"
    / "tier_classifier.py"
)


def _load_classifier_module():
    if not CLASSIFIER_FILE.exists():
        raise ModuleNotFoundError(f"Missing production classifier module: {CLASSIFIER_FILE}")

    spec = importlib.util.spec_from_file_location("memoria_consolidation_tier_classifier", CLASSIFIER_FILE)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load classifier module spec from {CLASSIFIER_FILE}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _classify(payload):
    module = _load_classifier_module()
    return module.classify_risk_tier(payload)


def test_classifier_module_and_api_exist():
    module = _load_classifier_module()
    assert hasattr(module, "classify_risk_tier")
    assert hasattr(module, "strict_promotion_gate")


def test_classifies_tier_a_for_high_completeness_and_cross_source_evidence():
    tier = _classify(
        {
            "causal_completeness": 0.92,
            "evidence_cross_sources": 3,
            "active_conflict": False,
            "historical_divergence_alert": False,
        }
    )
    assert tier == "A"


def test_classifies_tier_b_for_medium_signal_quality():
    tier = _classify(
        {
            "causal_completeness": 0.80,
            "evidence_cross_sources": 2,
            "active_conflict": False,
            "historical_divergence_alert": False,
        }
    )
    assert tier == "B"


def test_exact_tier_a_thresholds_are_inclusive():
    tier = _classify(
        {
            "causal_completeness": 0.85,
            "evidence_cross_sources": 2,
            "active_conflict": False,
            "historical_divergence_alert": False,
        }
    )
    assert tier == "A"


def test_exact_tier_b_thresholds_are_inclusive():
    tier = _classify(
        {
            "causal_completeness": 0.70,
            "evidence_cross_sources": 1,
            "active_conflict": False,
            "historical_divergence_alert": False,
        }
    )
    assert tier == "B"


def test_evidence_threshold_below_tier_a_drops_to_tier_b_when_otherwise_safe():
    tier = _classify(
        {
            "causal_completeness": 0.85,
            "evidence_cross_sources": 1,
            "active_conflict": False,
            "historical_divergence_alert": False,
        }
    )
    assert tier == "B"


def test_evidence_threshold_below_tier_b_drops_to_tier_c():
    tier = _classify(
        {
            "causal_completeness": 0.70,
            "evidence_cross_sources": 0,
            "active_conflict": False,
            "historical_divergence_alert": False,
        }
    )
    assert tier == "C"


def test_missing_active_conflict_key_is_fail_safe_to_tier_c():
    tier = _classify(
        {
            "causal_completeness": 0.95,
            "evidence_cross_sources": 3,
            "historical_divergence_alert": False,
        }
    )
    assert tier == "C"


def test_missing_historical_divergence_key_is_fail_safe_to_tier_c():
    tier = _classify(
        {
            "causal_completeness": 0.95,
            "evidence_cross_sources": 3,
            "active_conflict": False,
        }
    )
    assert tier == "C"


def test_conflict_toggle_blocks_tier_a_near_thresholds():
    safe = _classify(
        {
            "causal_completeness": 0.85,
            "evidence_cross_sources": 2,
            "active_conflict": False,
            "historical_divergence_alert": False,
        }
    )
    conflicted = _classify(
        {
            "causal_completeness": 0.85,
            "evidence_cross_sources": 2,
            "active_conflict": True,
            "historical_divergence_alert": False,
        }
    )
    assert safe == "A"
    assert conflicted == "C"


def test_divergence_toggle_blocks_tier_b_near_thresholds():
    safe = _classify(
        {
            "causal_completeness": 0.70,
            "evidence_cross_sources": 1,
            "active_conflict": False,
            "historical_divergence_alert": False,
        }
    )
    divergent = _classify(
        {
            "causal_completeness": 0.70,
            "evidence_cross_sources": 1,
            "active_conflict": False,
            "historical_divergence_alert": True,
        }
    )
    assert safe == "B"
    assert divergent == "C"


def test_classifies_tier_c_for_low_or_risky_signal_quality():
    tier = _classify(
        {
            "causal_completeness": 0.61,
            "evidence_cross_sources": 1,
            "active_conflict": True,
            "historical_divergence_alert": True,
        }
    )
    assert tier == "C"
