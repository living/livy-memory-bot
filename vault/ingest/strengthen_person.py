"""Person identity strengthening via participation signals (Wave C Phase C2).

Adds derived source_keys and conservative confidence increments to person entities
without auto-merging identities.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

MAPPER_VERSION = "external-ingest-person-strengthen-v1"

# Conservative confidence behavior:
# - low can be strengthened to medium
# - medium stays medium
# - high stays high
_CONFIDENCE_CEILING = {
    "low": "medium",
    "medium": "medium",
    "high": "high",
}
_CONFIDENCE_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
}


def _normalized_source_keys(entity: dict[str, Any]) -> list[str]:
    keys = entity.get("source_keys")
    if isinstance(keys, list):
        return [k for k in keys if isinstance(k, str)]
    return []


def _strengthen_confidence(current_confidence: str) -> str:
    current = current_confidence if current_confidence in _CONFIDENCE_ORDER else "low"
    ceiling = _CONFIDENCE_CEILING.get(current, "medium")
    if _CONFIDENCE_ORDER[current] < _CONFIDENCE_ORDER[ceiling]:
        return ceiling
    return current


def strengthen_person(
    entity: dict[str, Any],
    signal: dict[str, Any],
    run_id: str | None = None,
) -> dict[str, Any]:
    """Add a participation-derived source_key to a person entity.

    Idempotent source_keys behavior:
    - same signal source_key applied multiple times does not duplicate keys

    Conservative confidence behavior:
    - confidence is strengthened conservatively and never stacked above ceiling

    Schema safety:
    - does not inject transient/private fields into canonical entity payload

    Args:
        entity: Existing person entity dict.
        signal: Participation signal with a `source_key` field.
        run_id: Optional run id (accepted for API stability; not written to entity).

    Returns:
        New entity dict (input is not mutated).
    """
    # Keep API-compatible timestamp creation for callers that pass/expect run context.
    if run_id is None:
        run_id = datetime.now(timezone.utc).isoformat()

    derived_key = signal.get("source_key")
    if not isinstance(derived_key, str) or not derived_key.strip():
        return dict(entity)
    derived_key = derived_key.strip()

    new_keys = _normalized_source_keys(entity)
    if derived_key not in new_keys:
        new_keys.append(derived_key)

    current_conf = entity.get("confidence", "low")
    new_conf = _strengthen_confidence(current_conf)

    return {
        **entity,
        "source_keys": new_keys,
        "confidence": new_conf,
    }


def strengthen_from_signals(
    entity: dict[str, Any],
    signals: list[dict[str, Any]],
    run_id: str | None = None,
) -> dict[str, Any]:
    """Apply multiple strengthening signals sequentially.

    Idempotent by composition with strengthen_person.
    """
    result = dict(entity)
    for sig in signals:
        result = strengthen_person(result, sig, run_id=run_id)
    return result
