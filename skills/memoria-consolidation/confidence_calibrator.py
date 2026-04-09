#!/usr/bin/env python3
"""Confidence threshold calibrator with guarded adaptation.

Guardrails:
- Max threshold movement is ±0.05 per calibration cycle
- No adaptation when sample size < min_samples (default: 20)
- Changelog is append-only and deterministic
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_ADJUSTMENT_PER_CYCLE = 0.05
DEFAULT_MIN_SAMPLES = 20
DEFAULT_CHANGELOG_PATH = Path(
    "/home/lincoln/.openclaw/workspace-livy-memory/memory/model-threshold-changelog.md"
)


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize a raw feedback entry to calibrator schema.

    Accepts two schemas:
    - Calibrator schema: {decision, outcome}
    - Feedback-log schema: {action, rating}

    Returns None for entries that lack required valid pairs.
    """
    # Calibrator schema: {decision, outcome}
    decision = entry.get("decision")
    outcome = entry.get("outcome")
    if decision is not None and outcome is not None:
        if decision in ("promote", "defer") and outcome in ("up", "down"):
            return {"decision": decision, "outcome": outcome}
        return None

    # Feedback-log schema: {action, rating}
    action = entry.get("action")
    rating = entry.get("rating")
    if action is not None and rating is not None:
        if action in ("promote", "defer") and rating in ("up", "down"):
            return {"decision": action, "outcome": rating}

    return None


def _filter_valid(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return normalized valid entries in {decision, outcome} schema."""
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        row = _normalize_entry(entry)
        if row is not None:
            normalized.append(row)
    return normalized


def load_feedback_buffer(path: Path) -> list[dict[str, Any]]:
    """Load feedback entries from JSONL file.

    - Missing file => []
    - Empty file => []
    - Malformed lines are skipped
    """
    if not path.exists():
        return []

    entries: list[dict[str, Any]] = []
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


@dataclass(frozen=True)
class ChangelogWriter:
    changelog_path: 'pathlib.Path' = DEFAULT_CHANGELOG_PATH

    def append(
        self,
        *,
        threshold_before: float,
        threshold_after: float,
        accuracy: float,
        sample_size: int,
    ) -> None:
        """Append a markdown entry (never overwrite)."""
        self.changelog_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.changelog_path.exists():
            self.changelog_path.write_text(
                "# Model Threshold Changelog\n\n"
                "| Timestamp (UTC) | Threshold Before | Threshold After | Accuracy | Sample Size |\n"
                "|---|---:|---:|---:|---:|\n"
            )

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        row = (
            f"| {timestamp} | {threshold_before:.4f} | {threshold_after:.4f} "
            f"| {accuracy:.4f} | {sample_size} |\n"
        )
        with self.changelog_path.open("a", encoding="utf-8") as handle:
            handle.write(row)


class ConfidenceCalibrator:
    def __init__(
        self,
        *,
        current_threshold: float,
        min_samples: int = DEFAULT_MIN_SAMPLES,
        max_adjustment_per_cycle: float = MAX_ADJUSTMENT_PER_CYCLE,
        changelog_writer: ChangelogWriter | None = None,
    ) -> None:
        self.current_threshold = float(current_threshold)
        self.min_samples = int(min_samples)
        self.max_adjustment_per_cycle = float(max_adjustment_per_cycle)
        self.changelog_writer = changelog_writer or ChangelogWriter()

    def _clamp_adjustment(self, desired_adjustment: float) -> float:
        if desired_adjustment > self.max_adjustment_per_cycle:
            return self.max_adjustment_per_cycle
        if desired_adjustment < -self.max_adjustment_per_cycle:
            return -self.max_adjustment_per_cycle
        return float(desired_adjustment)

    def _compute_accuracy(self, feedback_entries: list[dict[str, Any]]) -> float:
        """Compute correctness rate over entries.

        Correctness mapping:
        - promote + up => correct
        - promote + down => incorrect
        - defer + down => correct
        - defer + up => incorrect
        Unknown decision/outcome pairs are treated as incorrect but counted.
        """
        if not feedback_entries:
            return 0.0

        correct = 0
        total = len(feedback_entries)

        for entry in feedback_entries:
            decision = entry.get("decision")
            outcome = entry.get("outcome")

            is_correct = (decision == "promote" and outcome == "up") or (
                decision == "defer" and outcome == "down"
            )
            if is_correct:
                correct += 1

        return correct / total

    def calibrate(self, feedback_entries: list[dict[str, Any]]) -> dict[str, Any]:
        """Calibrate threshold from feedback entries with guardrails.

        Only entries with valid (decision, outcome) pairs are counted.
        """
        valid_entries = _filter_valid(feedback_entries)
        sample_size = len(valid_entries)
        baseline = self.current_threshold

        if sample_size < self.min_samples:
            return {
                "threshold": baseline,
                "adjusted": False,
                "reason": "insufficient_samples",
                "sample_size": sample_size,
                "accuracy": None,
                "adjustment": 0.0,
            }

        accuracy = self._compute_accuracy(valid_entries)

        # Deterministic target movement:
        # if accuracy > threshold => decrease threshold (more strict)
        # if accuracy < threshold => increase threshold (more lenient)
        desired_adjustment = baseline - accuracy
        adjustment = self._clamp_adjustment(desired_adjustment)

        new_threshold = baseline + adjustment
        # Keep thresholds in probability range.
        new_threshold = max(0.0, min(1.0, new_threshold))

        adjusted = abs(new_threshold - baseline) > 0.0
        reason = "adjusted" if adjusted else "no_change_needed"

        return {
            "threshold": new_threshold,
            "adjusted": adjusted,
            "reason": reason,
            "sample_size": sample_size,
            "accuracy": accuracy,
            "adjustment": new_threshold - baseline,
        }

    def calibrate_from_buffer(self, feedback_buffer_path: Path) -> dict[str, Any]:
        raw_entries = load_feedback_buffer(feedback_buffer_path)
        normalized_entries = _filter_valid(raw_entries)
        return self.calibrate(normalized_entries)

    def calibrate_and_log(self, feedback_entries: list[dict[str, Any]]) -> dict[str, Any]:
        """Calibrate and append changelog entry only when adaptation is allowed."""
        before = self.current_threshold
        result = self.calibrate(feedback_entries)
        if result["reason"] == "insufficient_samples":
            return result

        self.changelog_writer.append(
            threshold_before=before,
            threshold_after=result["threshold"],
            accuracy=result["accuracy"] if result["accuracy"] is not None else 0.0,
            sample_size=result["sample_size"],
        )
        return result
