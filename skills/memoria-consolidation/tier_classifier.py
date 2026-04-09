"""Risk tier classifier (A/B/C) and strict promotion gate.

Tier A: High causal completeness AND multi-source evidence, no conflicts.
Tier B: Medium signal quality, generally acceptable.
Tier C: Low or risky signals, conflicts, or divergence alerts.

Strict promotion gate: ALL 5 criteria are mandatory for promotion.
Policy gate criteria:
    1) causal_completeness >= 0.85
    2) evidence_cross_sources >= 2
    3) tier == "A"
    4) no active conflict
    5) no historical divergence alert
"""

from typing import Any, Literal

# Tier thresholds
_TIER_A_CC_MIN = 0.85
_TIER_A_SOURCES_MIN = 2
_TIER_B_CC_MIN = 0.70
_TIER_B_SOURCES_MIN = 1


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def classify_risk_tier(payload: dict[str, Any]) -> Literal["A", "B", "C"]:
    """
    Classify a memory candidate into Tier A/B/C based on signal quality and risk factors.

    Tier A: causal_completeness >= 0.85 AND evidence_cross_sources >= 2
            AND no active conflict AND no historical divergence alert
    Tier B: causal_completeness >= 0.70 AND evidence_cross_sources >= 1
            AND no active conflict AND no historical divergence alert
    Tier C: anything not meeting Tier A or Tier B criteria

    Args:
        payload: dict with keys:
            - causal_completeness (float, 0-1)
            - evidence_cross_sources (int >= 0)
            - active_conflict (bool)
            - historical_divergence_alert (bool)

    Returns:
        "A", "B", or "C"
    """
    has_conflict_key = "active_conflict" in payload
    has_divergence_key = "historical_divergence_alert" in payload

    # Fail-safe: missing risk keys must not allow Tier A/B.
    if not (has_conflict_key and has_divergence_key):
        return "C"

    cc = _clamp(payload.get("causal_completeness", 0.0))
    sources = max(0, int(payload.get("evidence_cross_sources", 0)))
    has_conflict = bool(payload.get("active_conflict", False))
    has_divergence = bool(payload.get("historical_divergence_alert", False))

    if (
        cc >= _TIER_A_CC_MIN
        and sources >= _TIER_A_SOURCES_MIN
        and not has_conflict
        and not has_divergence
    ):
        return "A"

    if (
        cc >= _TIER_B_CC_MIN
        and sources >= _TIER_B_SOURCES_MIN
        and not has_conflict
        and not has_divergence
    ):
        return "B"

    return "C"


# Promotion gate thresholds
_POLICY_CC_MIN = 0.85
_POLICY_SOURCES_MIN = 2


def strict_promotion_gate(case: dict[str, Any]) -> dict[str, Any]:
    """
    Strict promotion gate: ALL 5 criteria are mandatory.

    Criteria:
        1) causal_completeness >= 0.85
        2) evidence_cross_sources >= 2
        3) tier == "A"
        4) no active conflict
        5) no historical divergence alert

    Args:
        case: dict with keys:
            - causal_completeness (float, 0-1)
            - evidence_cross_sources (int >= 0)
            - tier (Literal["A", "B", "C"])
            - active_conflict (bool)
            - historical_divergence_alert (bool)

    Returns:
        dict with keys:
            - promoted (bool): True only if ALL 5 criteria pass
            - criteria_met (dict): per-criterion pass/fail breakdown
            - reason (str): human-readable summary
    """
    has_cc_key = "causal_completeness" in case
    has_sources_key = "evidence_cross_sources" in case
    has_tier_key = "tier" in case
    has_conflict_key = "active_conflict" in case
    has_divergence_key = "historical_divergence_alert" in case

    cc = _clamp(case.get("causal_completeness", 0.0))
    sources = max(0, int(case.get("evidence_cross_sources", 0)))
    tier = str(case.get("tier", ""))
    has_conflict = bool(case.get("active_conflict", False))
    has_divergence = bool(case.get("historical_divergence_alert", False))

    criteria = {
        "causal_completeness_gte_085": has_cc_key and cc >= _POLICY_CC_MIN,
        "evidence_cross_sources_gte_2": has_sources_key and sources >= _POLICY_SOURCES_MIN,
        "tier_is_a": has_tier_key and tier == "A",
        "no_active_conflict": has_conflict_key and not has_conflict,
        "no_historical_divergence": has_divergence_key and not has_divergence,
    }

    promoted = all(criteria.values())
    failed = [k for k, v in criteria.items() if not v]
    reason = f"promoted" if promoted else f"rejected: {', '.join(failed)}"

    return {
        "promoted": promoted,
        "criteria_met": criteria,
        "reason": reason,
    }
