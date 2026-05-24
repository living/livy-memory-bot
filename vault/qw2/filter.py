"""Quality filters for QW-2 RAW → Topic File pipeline."""
from __future__ import annotations

import re
from typing import Any

def should_skip(claim: dict[str, Any]) -> tuple[bool, str]:
    """Return (skip, reason). False = process this claim."""
    text = claim.get("text", "")
    confidence = claim.get("confidence", 0)
    is_status = claim.get("_is_status_meeting", False)

    # Status meetings need higher confidence (>= 0.92) to be processed
    if is_status:
        if confidence >= 0.92:
            return False, ""
        return True, f"status meeting low confidence {confidence}"

    # Check for explicit decision phrases (bypass length for short meaningful content)
    decision_pattern = re.compile(
        r"\b(foi?\s+decidido|decidimos|ser[áa]\s+implementado|vai\s+ser|vamos\s+fazer)\b",
        re.IGNORECASE
    )
    if decision_pattern.search(text):
        return False, ""

    # No-decisions placeholder check
    if "sem decisões registradas" in text.lower():
        return True, "no decisions in transcript"

    # Length threshold: 50 chars minimum
    if len(text) < 50:
        return True, f"text too short ({len(text)} chars)"

    # Confidence threshold
    if confidence < 0.75:
        return True, f"low confidence {confidence}"

    return False, ""
