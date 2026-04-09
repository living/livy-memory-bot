"""Causal scorer: quality-first scoring with causal_completeness as primary metric.

Quality-first formula: overall_score = 0.80 * causal_completeness + 0.20 * evidence_cross_score
Pass threshold: causal_completeness >= 0.70 AND evidence_cross_score >= 0.60 AND overall >= 0.70
"""

from typing import Any, Optional


DEFAULT_THRESHOLDS = {
    "causal_completeness_min": 0.70,
    "evidence_cross_score_min": 0.60,
    "overall_min": 0.70,
}

_WEIGHT_CAUSAL = 0.80
_WEIGHT_EVIDENCE = 0.20


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_causal_quality(
    payload: dict[str, Any],
    thresholds: Optional[dict[str, float]] = None,
) -> dict[str, Any]:
    """
    Score causal quality of a memory candidate.

    Args:
        payload: dict with optional keys:
            - causal_completeness (float, 0-1)
            - evidence_cross_score (float, 0-1)
        thresholds: optional dict overriding defaults:
            - causal_completeness_min
            - evidence_cross_score_min
            - overall_min

    Returns:
        dict with keys:
            - causal_completeness (float, clamped 0-1)
            - evidence_cross_score (float, clamped 0-1)
            - overall_score (float, 0-1)
            - passes_quality_thresholds (bool)
    """
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    cc = _clamp(payload.get("causal_completeness", 0.0))
    ec = _clamp(payload.get("evidence_cross_score", 0.0))

    overall = _clamp(_WEIGHT_CAUSAL * cc + _WEIGHT_EVIDENCE * ec)

    passes = (
        cc >= t["causal_completeness_min"]
        and ec >= t["evidence_cross_score_min"]
        and overall >= t["overall_min"]
    )

    return {
        "causal_completeness": cc,
        "evidence_cross_score": ec,
        "overall_score": overall,
        "passes_quality_thresholds": passes,
    }
