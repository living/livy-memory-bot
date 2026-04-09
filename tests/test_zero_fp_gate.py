"""Zero false-positive safety tests for strict promotion policy gate (Task 4)."""

import importlib.util
from pathlib import Path

import pytest

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


def _strict_gate(case: dict):
    return _load_classifier_module().strict_promotion_gate(case)


def _valid_case() -> dict:
    return {
        "causal_completeness": 0.9,
        "evidence_cross_sources": 3,
        "tier": "A",
        "active_conflict": False,
        "historical_divergence_alert": False,
    }


def test_gate_api_exists():
    module = _load_classifier_module()
    assert hasattr(module, "strict_promotion_gate")


def test_policy_gate_requires_all_five_criteria_for_promotion():
    result = _strict_gate(_valid_case())
    assert result["promoted"] is True

    for missing_key in [
        "causal_completeness",
        "evidence_cross_sources",
        "tier",
        "active_conflict",
        "historical_divergence_alert",
    ]:
        case = _valid_case()
        case.pop(missing_key)
        rejected = _strict_gate(case)
        assert rejected["promoted"] is False, (
            f"Must reject when missing mandatory criterion: {missing_key}. Got: {rejected}"
        )


@pytest.mark.parametrize(
    "override",
    [
        {"causal_completeness": 0.84},
        {"evidence_cross_sources": 1},
        {"tier": "B"},
        {"active_conflict": True},
        {"historical_divergence_alert": True},
    ],
)
def test_any_failed_mandatory_criterion_causes_rejection(override):
    case = _valid_case()
    case.update(override)

    result = _strict_gate(case)

    assert result["promoted"] is False
    assert "criteria_met" in result
