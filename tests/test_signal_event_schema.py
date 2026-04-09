"""TDD tests for signal event schema written to signal-events.jsonl.

Contract: Every event persisted by curation_cron must conform to this schema.

Schema (signal-events.jsonl JSONL per line):
    {
        "event_id": str,        # UUID auto-generated
        "correlation_id": str,  # set per cycle
        "source": str,          # "tldv" | "logs" | "github" | "feedback"
        "priority": int,        # 1-4
        "collected_at": str,    # ISO8601
        "processed_at": str | null,
        "topic_ref": str | null,
        "signal_type": str,    # "decision" | "topic_mentioned" | "success" | "failure" | "correction"
        "payload": {
            "description": str,
            "evidence": str | null,
            "confidence": float,
        },
        "origin_id": str,
        "origin_url": str | null,
    }
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


SIGNAL_BUS_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "memoria-consolidation"
    / "signal_bus.py"
)


def _load_signal_bus_module():
    if not SIGNAL_BUS_FILE.exists():
        raise ModuleNotFoundError(f"Missing signal_bus module: {SIGNAL_BUS_FILE}")
    spec = importlib.util.spec_from_file_location(
        "memoria_consolidation_signal_bus", SIGNAL_BUS_FILE
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load signal_bus spec from {SIGNAL_BUS_FILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("memoria_consolidation_signal_bus", module)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Schema contracts
# ---------------------------------------------------------------------------

_REQUIRED_TOP_LEVEL_KEYS = {
    "event_id", "correlation_id", "source", "priority",
    "collected_at", "processed_at", "topic_ref",
    "signal_type", "payload", "origin_id", "origin_url",
}
_REQUIRED_PAYLOAD_KEYS = {"description", "evidence", "confidence"}
_VALID_SOURCES = {"tldv", "logs", "github", "feedback"}
_VALID_SIGNAL_TYPES = {
    "decision", "topic_mentioned", "success", "failure", "correction"
}


def _parse_jsonl(path: Path) -> list[dict]:
    """Parse a JSONL file, returning a list of parsed dicts."""
    if not path.exists():
        return []
    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Schema validation helpers
# ---------------------------------------------------------------------------

def _assert_valid_event(event: dict) -> None:
    """Assert a single event dict conforms to the signal-event schema."""
    # Top-level required keys
    missing = _REQUIRED_TOP_LEVEL_KEYS - set(event.keys())
    assert not missing, f"event missing required top-level keys: {missing}"

    # Top-level types
    assert isinstance(event["event_id"], str), "event_id must be str"
    assert isinstance(event["correlation_id"], str), "correlation_id must be str"
    assert isinstance(event["source"], str), "source must be str"
    assert event["source"] in _VALID_SOURCES, f"source must be one of {_VALID_SOURCES}, got {event['source']}"
    assert isinstance(event["priority"], int), "priority must be int"
    assert 1 <= event["priority"] <= 4, "priority must be 1-4"
    assert isinstance(event["collected_at"], str), "collected_at must be str"
    assert event["processed_at"] is None or isinstance(event["processed_at"], str)
    assert event["topic_ref"] is None or isinstance(event["topic_ref"], str)
    assert isinstance(event["signal_type"], str), "signal_type must be str"
    assert event["signal_type"] in _VALID_SIGNAL_TYPES, (
        f"signal_type must be one of {_VALID_SIGNAL_TYPES}, got {event['signal_type']}"
    )
    assert isinstance(event["payload"], dict), "payload must be dict"

    # Payload required keys
    payload = event["payload"]
    payload_missing = _REQUIRED_PAYLOAD_KEYS - set(payload.keys())
    assert not payload_missing, f"payload missing required keys: {payload_missing}"
    assert isinstance(payload["description"], str), "payload.description must be str"
    assert payload["evidence"] is None or isinstance(payload["evidence"], str)
    assert isinstance(payload["confidence"], (int, float)), "payload.confidence must be numeric"
    assert 0.0 <= payload["confidence"] <= 1.0, "payload.confidence must be 0-1"

    # Origin
    assert isinstance(event["origin_id"], str), "origin_id must be str"
    assert event["origin_url"] is None or isinstance(event["origin_url"], str)


# ---------------------------------------------------------------------------
# Tests: roundtrip via SignalBus.persist + SignalBus.load
# ---------------------------------------------------------------------------

def test_signal_event_roundtrip_contains_all_required_keys():
    """A SignalEvent persisted and reloaded must have all required schema keys."""
    module = _load_signal_bus_module()
    SignalEvent = module.SignalEvent
    SignalBus = module.SignalBus

    bus = SignalBus()
    bus.start_cycle()
    event = SignalEvent(
        source="tldv",
        priority=1,
        topic_ref="forge-platform.md",
        signal_type="decision",
        payload={"description": "Use Postgres", "evidence": "meeting #123", "confidence": 0.9},
        origin_id="meeting-123",
        origin_url="https://tldv.io/meeting/123",
    )
    bus.emit(event)

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        path = Path(f.name)

    try:
        bus.persist(path)
        records = _parse_jsonl(path)
        assert len(records) == 1
        _assert_valid_event(records[0])
    finally:
        path.unlink(missing_ok=True)


def test_signal_events_persisted_as_jsonl_are_valid_json_per_line():
    """Each line in signal-events.jsonl must be parseable JSON."""
    module = _load_signal_bus_module()
    SignalEvent = module.SignalEvent
    SignalBus = module.SignalBus

    bus = SignalBus()
    bus.start_cycle()
    for i, sig_type in enumerate(["decision", "success", "failure", "correction"]):
        bus.emit(
            SignalEvent(
                source="tldv",
                priority=1 + (i % 3),
                topic_ref="test.md",
                signal_type=sig_type,
                payload={"description": f"desc {i}", "evidence": None, "confidence": 0.8},
                origin_id=f"id-{i}",
                origin_url=None,
            )
        )

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        path = Path(f.name)

    try:
        bus.persist(path)
        lines = path.read_text().splitlines()
        assert len(lines) == 4
        for i, line in enumerate(lines):
            line = line.strip()
            assert line, f"line {i} is empty"
            parsed = json.loads(line)  # Must not raise
            assert isinstance(parsed, dict), f"line {i} is not a JSON object"
    finally:
        path.unlink(missing_ok=True)


def test_signal_event_schema_source_enum():
    """Only valid source values are accepted."""
    module = _load_signal_bus_module()
    SignalEvent = module.SignalEvent

    for valid_source in _VALID_SOURCES:
        event = SignalEvent(
            source=valid_source,
            priority=1,
            topic_ref="test.md",
            signal_type="decision",
            payload={"description": "test", "evidence": None, "confidence": 0.8},
            origin_id="id",
            origin_url=None,
        )
        assert event.source == valid_source


def test_signal_event_schema_signal_type_enum():
    """Only valid signal_type values are accepted."""
    module = _load_signal_bus_module()
    SignalEvent = module.SignalEvent

    for sig_type in _VALID_SIGNAL_TYPES:
        event = SignalEvent(
            source="tldv",
            priority=1,
            topic_ref="test.md",
            signal_type=sig_type,
            payload={"description": "test", "evidence": None, "confidence": 0.8},
            origin_id="id",
            origin_url=None,
        )
        assert event.signal_type == sig_type


def test_signal_event_payload_confidence_can_exceed_1_without_pydantic_validation():
    """SignalEvent currently accepts payload.confidence > 1.0 because payload is a plain dict.

    This is a known gap: schema validation for payload.confidence range is not enforced
    by SignalEvent Pydantic model. Tests that rely on Pydantic validation for this field
    will fail. Callers are responsible for validating payload.confidence before persisting.
    """
    module = _load_signal_bus_module()
    SignalEvent = module.SignalEvent

    # Must NOT raise — SignalEvent does not validate payload contents
    event = SignalEvent(
        source="tldv",
        priority=1,
        topic_ref="test.md",
        signal_type="decision",
        payload={"description": "test", "evidence": None, "confidence": 1.5},
        origin_id="id",
        origin_url=None,
    )
    # Payload confidence IS set (no field-level validation in SignalEvent)
    assert event.payload["confidence"] == 1.5


def test_signal_event_priority_range():
    """Priority must be 1-4 (inclusive)."""
    module = _load_signal_bus_module()
    SignalEvent = module.SignalEvent

    for valid_p in [1, 2, 3, 4]:
        event = SignalEvent(
            source="tldv",
            priority=valid_p,
            topic_ref="test.md",
            signal_type="decision",
            payload={"description": "test", "evidence": None, "confidence": 0.8},
            origin_id="id",
            origin_url=None,
        )
        assert event.priority == valid_p

    for invalid_p in [0, 5, -1]:
        with pytest.raises(Exception):
            SignalEvent(
                source="tldv",
                priority=invalid_p,
                topic_ref="test.md",
                signal_type="decision",
                payload={"description": "test", "evidence": None, "confidence": 0.8},
                origin_id="id",
                origin_url=None,
            )


def test_signal_events_from_multiple_sources_all_conform():
    """Events from all 4 sources must all validate against the same schema."""
    module = _load_signal_bus_module()
    SignalEvent = module.SignalEvent
    SignalBus = module.SignalBus

    bus = SignalBus()
    bus.start_cycle()
    for src in _VALID_SOURCES:
        bus.emit(
            SignalEvent(
                source=src,
                priority=2,
                topic_ref="test.md",
                signal_type="decision",
                payload={"description": f"from {src}", "evidence": None, "confidence": 0.75},
                origin_id=f"id-{src}",
                origin_url=None,
            )
        )

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        path = Path(f.name)

    try:
        bus.persist(path)
        records = _parse_jsonl(path)
        assert len(records) == 4
        for record in records:
            _assert_valid_event(record)
    finally:
        path.unlink(missing_ok=True)


def test_signal_event_optional_fields_can_be_null():
    """topic_ref and origin_url may be null without breaking schema."""
    module = _load_signal_bus_module()
    SignalEvent = module.SignalEvent

    event = SignalEvent(
        source="logs",
        priority=3,
        topic_ref=None,
        signal_type="failure",
        payload={"description": "job failed", "evidence": None, "confidence": 1.0},
        origin_id="log-123",
        origin_url=None,
    )
    assert event.topic_ref is None
    assert event.origin_url is None
    # Must still round-trip cleanly
    data = event.model_dump()
    assert data["topic_ref"] is None
    assert data["origin_url"] is None


def test_signal_event_json_serialization_matches_schema():
    """model_dump_json must produce JSON that validates against the schema."""
    module = _load_signal_bus_module()
    SignalEvent = module.SignalEvent

    event = SignalEvent(
        source="github",
        priority=2,
        topic_ref="bat-conectabot.md",
        signal_type="correction",
        payload={"description": "PR merged", "evidence": "https://github.com/pr/123", "confidence": 0.95},
        origin_id="pr-123",
        origin_url="https://github.com/pr/123",
    )

    json_str = event.model_dump_json()
    parsed = json.loads(json_str)
    _assert_valid_event(parsed)
