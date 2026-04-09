"""TDD tests for confidence calibrator (Task 7).

Tests threshold adjustment constraints:
- Guardrail: no threshold movement > 0.05 per cycle
- No adaptation when sample size < 20
- Deterministic and audit-friendly
"""

import importlib.util
import sys
from pathlib import Path

CALIBRATOR_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "memoria-consolidation"
    / "confidence_calibrator.py"
)


def _load_calibrator_module():
    if not CALIBRATOR_FILE.exists():
        raise ModuleNotFoundError(f"Missing calibrator module: {CALIBRATOR_FILE}")

    spec = importlib.util.spec_from_file_location(
        "memoria_consolidation_confidence_calibrator", CALIBRATOR_FILE
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load calibrator spec from {CALIBRATOR_FILE}")

    module = importlib.util.module_from_spec(spec)
    # Register so dataclass type-annotation resolution works
    sys.modules.setdefault("memoria_consolidation_confidence_calibrator", module)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Module & API existence
# ---------------------------------------------------------------------------

def test_calibrator_module_and_api_exist():
    """Calibrator module must expose ConfidenceCalibrator and ChangelogWriter."""
    module = _load_calibrator_module()
    assert hasattr(module, "ConfidenceCalibrator")
    assert hasattr(module, "ChangelogWriter")


# ---------------------------------------------------------------------------
# Threshold movement guardrail: max ±0.05 per cycle
# ---------------------------------------------------------------------------

def test_threshold_adjustment_bounded_to_plus_0_05():
    """Adjustment above +0.05 must be clamped to +0.05."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    new_threshold = calibrator._clamp_adjustment(desired_adjustment=0.10)
    assert new_threshold <= 0.05
    assert new_threshold == 0.05


def test_threshold_adjustment_bounded_to_minus_0_05():
    """Adjustment below -0.05 must be clamped to -0.05."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    new_threshold = calibrator._clamp_adjustment(desired_adjustment=-0.10)
    assert new_threshold >= -0.05
    assert new_threshold == -0.05


def test_threshold_adjustment_within_bounds_is_unchanged():
    """Adjustment within ±0.05 must pass through unchanged."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    assert calibrator._clamp_adjustment(0.03) == 0.03
    assert calibrator._clamp_adjustment(-0.04) == -0.04
    assert calibrator._clamp_adjustment(0.0) == 0.0


def test_threshold_exactly_at_boundary_is_allowed():
    """Adjustment of exactly ±0.05 must be allowed (boundary inclusive)."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    assert calibrator._clamp_adjustment(0.05) == 0.05
    assert calibrator._clamp_adjustment(-0.05) == -0.05


def test_overshoot_adjustment_is_clamped_not_rejected():
    """Large overshoot must be clamped, not rejected."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    # Overshoot by 0.15 should clamp to 0.05
    result = calibrator._clamp_adjustment(0.15)
    assert result == 0.05


# ---------------------------------------------------------------------------
# Minimum sample size rule: >= 20
# ---------------------------------------------------------------------------

def test_calibration_blocked_when_sample_size_below_minimum():
    """No threshold change when sample size < min_samples."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    feedback = [
        {"decision": "promote", "outcome": "up"},
        {"decision": "promote", "outcome": "up"},
    ]
    result = calibrator.calibrate(feedback)
    assert result["threshold"] == 0.80
    assert result["adjusted"] is False
    assert result["reason"] == "insufficient_samples"


def test_calibration_blocked_at_exactly_19_samples():
    """Exactly 19 samples must still be blocked (must be >= 20)."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    feedback = [{"decision": "promote", "outcome": "up"}] * 19
    result = calibrator.calibrate(feedback)
    assert result["threshold"] == 0.80
    assert result["adjusted"] is False


def test_calibration_allowed_at_exactly_20_samples():
    """Exactly 20 samples must be allowed (boundary inclusive)."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    feedback = [{"decision": "promote", "outcome": "up"}] * 20
    result = calibrator.calibrate(feedback)
    assert result["adjusted"] is True


def test_calibration_allows_more_than_20_samples():
    """Sample size > 20 must be allowed."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    feedback = [{"decision": "promote", "outcome": "up"}] * 25
    result = calibrator.calibrate(feedback)
    assert result["adjusted"] is True


def test_calibration_counts_only_valid_decision_outcome_samples():
    """Gating must count only entries with valid (decision, outcome) pairs."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)

    feedback = ([{"decision": "promote", "outcome": "up"}] * 19) + [{"foo": "bar"}]
    result = calibrator.calibrate(feedback)

    assert result["adjusted"] is False
    assert result["reason"] == "insufficient_samples"
    assert result["sample_size"] == 19


def test_calibration_allows_20_valid_even_with_invalid_rows_present():
    """20 valid samples should pass gate even when invalid rows are present."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)

    feedback = (
        [{"decision": "promote", "outcome": "up"}] * 20
        + [{"decision": "promote"}, {"outcome": "up"}, {"x": 1}]
    )
    result = calibrator.calibrate(feedback)

    assert result["adjusted"] is True
    assert result["sample_size"] == 20


# ---------------------------------------------------------------------------
# Accuracy calculation
# ---------------------------------------------------------------------------

def test_accuracy_is_fraction_of_correct_outcomes():
    """Accuracy = correct / total decisions."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    feedback = [
        {"decision": "promote", "outcome": "up"},
        {"decision": "promote", "outcome": "up"},
        {"decision": "promote", "outcome": "up"},
        {"decision": "promote", "outcome": "up"},
        {"decision": "promote", "outcome": "down"},
        {"decision": "promote", "outcome": "down"},
    ]
    accuracy = calibrator._compute_accuracy(feedback)
    assert accuracy == 4 / 6


def test_accuracy_with_mixed_decisions():
    """Correct outcomes for 'defer' decisions count toward accuracy too."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    feedback = [
        {"decision": "promote", "outcome": "up"},
        {"decision": "defer", "outcome": "down"},
        {"decision": "promote", "outcome": "up"},
        {"decision": "defer", "outcome": "up"},
    ]
    accuracy = calibrator._compute_accuracy(feedback)
    assert accuracy == 3 / 4


# ---------------------------------------------------------------------------
# Directional adjustment
# ---------------------------------------------------------------------------

def test_high_accuracy_above_threshold_suggests_downward_adjustment():
    """When observed accuracy > current threshold, threshold should decrease."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    # Perfect accuracy = 1.0 > 0.80 → suggest moving threshold down
    feedback = [{"decision": "promote", "outcome": "up"}] * 20
    result = calibrator.calibrate(feedback)
    assert result["adjusted"] is True
    assert result["threshold"] < 0.80


def test_low_accuracy_below_threshold_suggests_upward_adjustment():
    """When observed accuracy < current threshold, threshold should increase."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    # All wrong: accuracy = 0 < 0.80 → suggest moving threshold up
    feedback = [{"decision": "promote", "outcome": "down"}] * 20
    result = calibrator.calibrate(feedback)
    assert result["adjusted"] is True
    assert result["threshold"] > 0.80


def test_accurate_at_threshold_means_no_significant_adjustment():
    """When observed accuracy equals current threshold, no significant adjustment."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    # Exactly 16/20 = 0.80 accuracy = current threshold
    feedback = (
        [{"decision": "promote", "outcome": "up"}] * 16
        + [{"decision": "promote", "outcome": "down"}] * 4
    )
    result = calibrator.calibrate(feedback)
    # accuracy = 0.80, desired_adjustment = 0.80 - 0.80 = 0, clamped = 0
    assert result["threshold"] == 0.80
    assert result["adjustment"] == 0.0


# ---------------------------------------------------------------------------
# Changelog append-only
# ---------------------------------------------------------------------------

def test_changelog_writer_appends_entry(tmp_path):
    """ChangelogWriter must append, not overwrite."""
    module = _load_calibrator_module()
    changelog = tmp_path / "model-threshold-changelog.md"
    writer = module.ChangelogWriter(changelog_path=changelog)
    writer.append(threshold_before=0.80, threshold_after=0.82, accuracy=0.90, sample_size=25)
    content = changelog.read_text()
    assert "0.80" in content
    assert "0.82" in content


def test_changelog_writer_append_is_idempotent(tmp_path):
    """Multiple appends must each produce a distinct entry."""
    module = _load_calibrator_module()
    changelog = tmp_path / "model-threshold-changelog.md"
    writer = module.ChangelogWriter(changelog_path=changelog)
    writer.append(threshold_before=0.80, threshold_after=0.82, accuracy=0.90, sample_size=25)
    writer.append(threshold_before=0.82, threshold_after=0.84, accuracy=0.88, sample_size=30)
    content = changelog.read_text()
    lines = [l for l in content.splitlines() if l.strip()]
    assert len(lines) >= 4  # header + separator + 2 data rows


def test_changelog_writer_creates_parent_dirs(tmp_path):
    """ChangelogWriter must create parent directories if missing."""
    module = _load_calibrator_module()
    nested = tmp_path / "deep" / "nested" / "model-threshold-changelog.md"
    writer = module.ChangelogWriter(changelog_path=nested)
    writer.append(threshold_before=0.80, threshold_after=0.82, accuracy=0.90, sample_size=25)
    assert nested.exists()


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_calibration_is_deterministic_given_same_feedback():
    """Same input feedback must always produce the same threshold."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    feedback = [{"decision": "promote", "outcome": "up"}] * 20
    result1 = calibrator.calibrate(feedback)
    result2 = calibrator.calibrate(feedback)
    assert result1["threshold"] == result2["threshold"]
