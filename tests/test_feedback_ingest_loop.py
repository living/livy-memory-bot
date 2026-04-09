"""TDD tests for feedback ingest loop (Task 7).

Tests that the calibrator integrates with the feedback buffer from learn_from_feedback.py.
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
    sys.modules.setdefault("memoria_consolidation_confidence_calibrator", module)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Feedback buffer ingestion integration
# ---------------------------------------------------------------------------

def test_load_feedback_buffer_from_jsonl(tmp_path):
    """Calibrator must be able to load structured feedback from a JSONL buffer."""
    module = _load_calibrator_module()
    feedback_file = tmp_path / "feedback-buffer.jsonl"
    feedback_file.write_text(
        '{"decision": "promote", "outcome": "up"}\n'
        '{"decision": "promote", "outcome": "up"}\n'
        '{"decision": "defer", "outcome": "down"}\n'
    )

    entries = module.load_feedback_buffer(feedback_file)
    assert len(entries) == 3
    assert entries[0]["decision"] == "promote"
    assert entries[0]["outcome"] == "up"


def test_load_feedback_buffer_empty_file_returns_empty_list(tmp_path):
    """Empty JSONL file must return empty list."""
    module = _load_calibrator_module()
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("")
    entries = module.load_feedback_buffer(empty_file)
    assert entries == []


def test_load_feedback_buffer_missing_file_returns_empty_list():
    """Missing file must return empty list without raising."""
    module = _load_calibrator_module()
    missing = Path("/nonexistent/feedback-buffer.jsonl")
    entries = module.load_feedback_buffer(missing)
    assert entries == []


def test_load_feedback_buffer_skips_malformed_lines(tmp_path):
    """Malformed JSON lines must be skipped silently."""
    module = _load_calibrator_module()
    feedback_file = tmp_path / "mixed.jsonl"
    feedback_file.write_text(
        '{"decision": "promote", "outcome": "up"}\n'
        'NOT JSON\n'
        '{"decision": "defer"}\n'
        '{"decision": "promote", "outcome": "down"}\n'
    )

    entries = module.load_feedback_buffer(feedback_file)
    assert len(entries) == 3


# ---------------------------------------------------------------------------
# Integration: calibrate from feedback buffer
# ---------------------------------------------------------------------------

def test_calibrate_from_feedback_buffer(tmp_path):
    """Full cycle: load buffer → calibrate → return result."""
    module = _load_calibrator_module()
    feedback_file = tmp_path / "feedback-buffer.jsonl"

    lines = ['{"decision": "promote", "outcome": "up"}\n' for _ in range(20)]
    feedback_file.write_text("".join(lines))

    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    result = calibrator.calibrate_from_buffer(feedback_file)

    assert "threshold" in result
    assert "adjusted" in result


def test_calibrate_from_feedback_buffer_insufficient_samples(tmp_path):
    """Buffer with < 20 entries must not trigger adjustment."""
    module = _load_calibrator_module()
    feedback_file = tmp_path / "small-buffer.jsonl"
    feedback_file.write_text(
        '{"decision": "promote", "outcome": "up"}\n'
        '{"decision": "promote", "outcome": "up"}\n'
    )

    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    result = calibrator.calibrate_from_buffer(feedback_file)

    assert result["adjusted"] is False
    assert result["reason"] == "insufficient_samples"


def test_calibrate_from_feedback_buffer_normalizes_action_rating_schema(tmp_path):
    """calibrate_from_buffer must normalize raw action/rating logs into decision/outcome."""
    module = _load_calibrator_module()
    feedback_file = tmp_path / "raw-feedback-buffer.jsonl"

    lines = ['{"action": "promote", "rating": "up"}\n' for _ in range(20)]
    feedback_file.write_text("".join(lines))

    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    result = calibrator.calibrate_from_buffer(feedback_file)

    assert result["adjusted"] is True
    assert result["sample_size"] == 20
    assert result["accuracy"] == 1.0


def test_calibrate_from_feedback_buffer_ignores_invalid_rows_for_min_samples(tmp_path):
    """Min-samples gate must use valid normalized rows, not total JSONL lines."""
    module = _load_calibrator_module()
    feedback_file = tmp_path / "mixed-raw-feedback-buffer.jsonl"

    valid_lines = ['{"action": "promote", "rating": "up"}\n' for _ in range(19)]
    invalid_lines = ['{"action": "promote"}\n', '{"action": "other", "rating": "up"}\n']
    feedback_file.write_text("".join(valid_lines + invalid_lines))

    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)
    result = calibrator.calibrate_from_buffer(feedback_file)

    assert result["adjusted"] is False
    assert result["reason"] == "insufficient_samples"
    assert result["sample_size"] == 19


# ---------------------------------------------------------------------------
# learn_from_feedback.py integration: expose feedback buffer
# ---------------------------------------------------------------------------

def test_learn_from_feedback_exposes_get_feedback_buffer():
    """learn_from_feedback module must expose get_feedback_buffer function."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "memoria-consolidation"))
    import learn_from_feedback
    assert hasattr(learn_from_feedback, "get_feedback_buffer")


def test_get_feedback_buffer_loads_jsonl(tmp_path, monkeypatch):
    """get_feedback_buffer must read and return entries from feedback log."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "memoria-consolidation"))
    import learn_from_feedback

    test_file = tmp_path / "test-feedback.jsonl"
    test_file.write_text(
        '{"action": "promote", "rating": "up"}\n'
        '{"action": "defer", "rating": "down"}\n'
    )

    monkeypatch.setattr(learn_from_feedback, "FEEDBACK_LOG", test_file)
    entries = learn_from_feedback.get_feedback_buffer()
    assert len(entries) == 2


def test_get_feedback_buffer_returns_empty_on_missing_file(monkeypatch, tmp_path):
    """get_feedback_buffer must return [] when file does not exist."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "memoria-consolidation"))
    import learn_from_feedback

    missing = tmp_path / "nonexistent-feedback.jsonl"
    monkeypatch.setattr(learn_from_feedback, "FEEDBACK_LOG", missing)
    entries = learn_from_feedback.get_feedback_buffer()
    assert entries == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_calibrate_with_mixed_correct_and_incorrect_outcomes():
    """Calibrator must handle a realistic mix of correct/incorrect outcomes."""
    module = _load_calibrator_module()
    calibrator = module.ConfidenceCalibrator(current_threshold=0.80, min_samples=20)

    # 20 entries: 14 correct, 6 wrong
    feedback = (
        [{"decision": "promote", "outcome": "up"}] * 10
        + [{"decision": "promote", "outcome": "down"}] * 5
        + [{"decision": "defer", "outcome": "down"}] * 4
        + [{"decision": "defer", "outcome": "up"}] * 1
    )
    result = calibrator.calibrate(feedback)
    assert result["sample_size"] == 20
    assert result["accuracy"] == 14 / 20
