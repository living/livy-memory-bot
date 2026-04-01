import sys, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/memoria-consolidation"))

from signal_bus import SignalEvent, SignalBus

def test_signal_event_dataclass():
    event = SignalEvent(
        source="tldv",
        priority=1,
        topic_ref="forge-platform.md",
        signal_type="decision",
        payload={"description": "Use Postgres", "evidence": "meeting #123", "confidence": 0.9},
        origin_id="meeting-123",
        origin_url="https://tldv.io/meeting/123",
    )
    assert event.source == "tldv"
    assert event.priority == 1
    assert event.signal_type == "decision"
    assert event.event_id is not None  # auto-generated
    assert event.correlation_id is not None  # auto-generated
    assert event.collected_at is not None  # auto-generated

def test_signal_event_serialization():
    event = SignalEvent(
        source="logs",
        priority=2,
        topic_ref="bat-conectabot.md",
        signal_type="failure",
        payload={"description": "Job failed", "evidence": None, "confidence": 1.0},
        origin_id="bat-daily-2026-04-01",
        origin_url=None,
    )
    data = event.model_dump()
    assert data["source"] == "logs"
    assert data["priority"] == 2
    assert "event_id" in data
    assert "correlation_id" in data

def test_signal_bus_initial_state():
    bus = SignalBus()
    assert bus.events == []
    assert bus.correlation_id is None

def test_signal_bus_set_correlation_id():
    bus = SignalBus()
    cid = bus.start_cycle()
    assert bus.correlation_id == cid
    assert uuid.UUID(cid)  # valid UUID

def test_signal_bus_emit():
    bus = SignalBus()
    bus.start_cycle()
    event = SignalEvent(
        source="tldv",
        priority=1,
        topic_ref="forge-platform.md",
        signal_type="decision",
        payload={"description": "Test", "evidence": None, "confidence": 0.8},
        origin_id="m123",
        origin_url=None,
    )
    emitted = bus.emit(event)
    assert emitted.event_id == event.event_id
    assert len(bus.events) == 1

def test_signal_bus_get_by_topic():
    bus = SignalBus()
    bus.start_cycle()
    for i in range(3):
        e = SignalEvent(source="tldv", priority=1, topic_ref="forge.md",
                        signal_type="decision",
                        payload={"description": f"d{i}", "evidence": None, "confidence": 0.8},
                        origin_id=f"m{i}", origin_url=None)
        bus.emit(e)
    bus.emit(SignalEvent(source="logs", priority=2, topic_ref="other.md",
                         signal_type="failure",
                         payload={"description": "fail", "evidence": None, "confidence": 1.0},
                         origin_id="l1", origin_url=None))
    forge_events = bus.get_by_topic("forge.md")
    assert len(forge_events) == 3
    assert all(e.topic_ref == "forge.md" for e in forge_events)

def test_signal_bus_persist_and_load(tmp_path):
    import json
    bus = SignalBus()
    bus.start_cycle()
    bus.emit(SignalEvent(source="tldv", priority=1, topic_ref="test.md",
                         signal_type="decision",
                         payload={"description": "persist test", "evidence": None, "confidence": 0.9},
                         origin_id="m1", origin_url=None))
    events_file = tmp_path / "events.jsonl"
    bus.persist(events_file)

    # Load into new bus
    bus2 = SignalBus()
    bus2.load(events_file)
    assert len(bus2.events) == 1
    assert bus2.events[0].source == "tldv"