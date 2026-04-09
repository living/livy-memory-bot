"""TDD tests for causal scorer (quality-first, causal-completeness-primary)."""

import importlib.util
from pathlib import Path

import pytest

SCORER_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "memoria-consolidation"
    / "causal_scorer.py"
)


def _load_scorer_module():
    if not SCORER_FILE.exists():
        raise ModuleNotFoundError(f"Missing production scorer module: {SCORER_FILE}")

    spec = importlib.util.spec_from_file_location("memoria_consolidation_causal_scorer", SCORER_FILE)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load scorer module spec from {SCORER_FILE}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _score(payload, thresholds=None):
    module = _load_scorer_module()
    return module.score_causal_quality(payload, thresholds=thresholds)


def test_scorer_module_and_api_exist():
    module = _load_scorer_module()
    assert hasattr(module, "score_causal_quality")


def test_scoring_formula_weights_causal_completeness_as_primary_metric():
    result = _score({"causal_completeness": 0.9, "evidence_cross_score": 0.5})

    assert result["causal_completeness"] == pytest.approx(0.9)
    assert result["evidence_cross_score"] == pytest.approx(0.5)
    # quality-first formula: 80% causal completeness + 20% evidence cross-score
    assert result["overall_score"] == pytest.approx(0.82)


def test_high_evidence_does_not_compensate_low_causal_completeness():
    result = _score({"causal_completeness": 0.69, "evidence_cross_score": 1.0})

    # Despite decent overall score, below-threshold primary metric must fail.
    assert result["overall_score"] > 0.7
    assert result["passes_quality_thresholds"] is False


def test_missing_metrics_default_to_zero_and_fail_closed():
    result = _score({})

    assert result["causal_completeness"] == 0.0
    assert result["evidence_cross_score"] == 0.0
    assert result["overall_score"] == 0.0
    assert result["passes_quality_thresholds"] is False


def test_scores_are_clamped_to_unit_interval():
    result = _score({"causal_completeness": 1.8, "evidence_cross_score": -0.2})

    assert result["causal_completeness"] == 1.0
    assert result["evidence_cross_score"] == 0.0
    assert result["overall_score"] == pytest.approx(0.8)


def test_custom_thresholds_are_supported():
    result = _score(
        {"causal_completeness": 0.65, "evidence_cross_score": 0.65},
        thresholds={"causal_completeness_min": 0.6, "evidence_cross_score_min": 0.6, "overall_min": 0.6},
    )

    assert result["passes_quality_thresholds"] is True
