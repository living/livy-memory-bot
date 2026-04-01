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


# -------------------------------------------------------------------
# TLDV Collector tests
# -------------------------------------------------------------------
import os, sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/memoria-consolidation"))

from collectors.tldv_collector import TLDVCollector, build_tldv_signal

def test_build_tldv_signal():
    """Build a SignalEvent from a TLDV summary row."""
    row = {
        "meeting_id": "abc123",
        "topics": ["BAT", "Azure", "KQL"],
        "decisions": ["Usar KQL para queries"],
    }
    signal = build_tldv_signal(row, "https://tldv.io/meeting/abc123")
    assert signal.source == "tldv"
    assert signal.priority == 1
    assert signal.signal_type == "decision"
    assert "KQL" in signal.payload["description"]
    assert signal.origin_id == "abc123"
    assert signal.origin_url == "https://tldv.io/meeting/abc123"
    assert signal.topic_ref is not None  # matched via topics

def test_build_tldv_signal_with_robert():
    """Robert as participant = explicit direction signal."""
    row = {
        "meeting_id": "xyz789",
        "topics": ["Forge"],
        "decisions": ["Migrar para Forge"],
        "participant_names": ["Robert"],
    }
    signal = build_tldv_signal(row, "https://tldv.io/meeting/xyz789")
    assert signal.priority == 1
    assert signal.payload["confidence"] == 1.0  # Robert = max confidence

def test_topic_matching():
    """Topics like BAT, Forge, Delphos map to specific topic files."""
    row = {
        "meeting_id": "m1",
        "topics": ["BAT", "ConectaBot"],
        "decisions": [],
    }
    signal = build_tldv_signal(row, None)
    assert signal.topic_ref in ["bat-conectabot-observability.md", "forge-platform.md"]

def test_collector_initialization():
    collector = TLDVCollector()
    assert collector.source == "tldv"
    assert collector.priority == 1

@patch("collectors.tldv_collector.requests.get")
def test_collector_fetches_meetings(mock_get):
    """Collector fetches from Supabase REST API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"id": "m1", "name": "Daily", "created_at": "2026-04-01T10:00:00Z",
         "enriched_at": "2026-04-01T10:05:00Z"},
    ]
    mock_get.return_value = mock_response

    collector = TLDVCollector()
    assert collector.source == "tldv"


# -------------------------------------------------------------------
# Topic Analyzer tests
# -------------------------------------------------------------------
from pathlib import Path
import sys, tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/memoria-consolidation"))
from signal_bus import SignalEvent
from topic_analyzer import TopicAnalyzer, CandidateChange

def test_candidate_change_dataclass():
    change = CandidateChange(
        change_type="add_decision",
        description="Use Postgres",
        evidence="meeting #123",
        signal_source="tldv",
    )
    assert change.change_type == "add_decision"
    assert "Postgres" in change.description

def test_analyzer_adds_decision(tmp_path):
    """New decision from signal → add_entry candidate."""
    topic_file = tmp_path / "forge-platform.md"
    topic_file.write_text("---\nname: forge\n---\n\n# Forge\n\n## Decisões\n(nenhuma)\n")

    signal = SignalEvent(
        source="tldv",
        priority=1,
        topic_ref="forge-platform.md",
        signal_type="decision",
        payload={"description": "Usar Postgres com Neon", "evidence": "meeting #123", "confidence": 0.9},
        origin_id="m123",
        origin_url="https://tldv.io/meeting/123",
    )

    analyzer = TopicAnalyzer()
    candidates = analyzer.analyze(topic_file, [signal])
    assert len(candidates) == 1
    assert candidates[0].change_type == "add_decision"
    assert "Postgres" in candidates[0].description

def test_analyzer_skips_duplicate():
    """Decision already in topic file → no candidate."""
    content = "---\nname: forge\n---\n\n# Forge\n\n## Decisões\n- Usar Postgres com Neon\n"
    signal = SignalEvent(
        source="tldv", priority=1, topic_ref="forge-platform.md",
        signal_type="decision",
        payload={"description": "Usar Postgres com Neon", "evidence": "meeting #123", "confidence": 0.9},
        origin_id="m123", origin_url=None,
    )
    analyzer = TopicAnalyzer()
    candidates = analyzer.analyze_content("forge-platform.md", content, [signal])
    assert candidates == []

def test_analyzer_failure_signal():
    """Failure signal with confidence 1.0 → deprecate_entry candidate."""
    signal = SignalEvent(
        source="logs",
        priority=2,
        topic_ref="delphos-video-vistoria.md",
        signal_type="failure",
        payload={"description": "Job Vonage falhou 3x", "evidence": "reports/daily/2026-04-01.json", "confidence": 1.0},
        origin_id="delphos-daily-2026-04-01",
        origin_url=None,
    )
    analyzer = TopicAnalyzer()
    candidates = analyzer.analyze_content("delphos-video-vistoria.md", "# Delphos\n\n## Status\n- Vonage: em uso\n", [signal])
    assert len(candidates) == 1
    assert candidates[0].change_type == "deprecate_entry"


# -------------------------------------------------------------------
# AutoCurator tests
# -------------------------------------------------------------------
from auto_curator import AutoCurator

def test_should_apply_returns_true_for_high_confidence():
    curator = AutoCurator()
    change = CandidateChange(
        change_type="add_decision",
        description="Use Postgres",
        evidence="meeting #123",
        signal_source="tldv",
    )
    assert curator.should_apply(change) is True

def test_should_apply_returns_false_for_low_confidence():
    curator = AutoCurator()
    signal = SignalEvent(
        source="tldv", priority=1, topic_ref="test.md",
        signal_type="decision",
        payload={"description": "Test", "evidence": None, "confidence": 0.5},
        origin_id="m1", origin_url=None,
    )
    change = CandidateChange(
        change_type="add_decision",
        description="Use Postgres",
        evidence=None,
        signal_source="tldv",
    )
    # No evidence + low confidence → don't apply
    assert curator.should_apply(change) is False

def test_apply_add_decision(tmp_path):
    topic_file = tmp_path / "forge.md"
    topic_file.write_text("---\nname: forge\n---\n\n# Forge\n\n## Decisões\n(nenhuma)\n")

    curator = AutoCurator()
    change = CandidateChange(
        change_type="add_decision",
        description="Usar Postgres",
        evidence="meeting #123",
        signal_source="tldv",
    )
    result = curator.apply_change(topic_file, change)

    assert result is True
    content = topic_file.read_text()
    assert "Usar Postgres" in content
    assert "meeting #123" in content

def test_apply_deprecate_entry(tmp_path):
    topic_file = tmp_path / "delphos.md"
    topic_file.write_text("---\nname: delphos\n---\n\n# Delphos\n\n## Status\n- Vonage: em uso\n\n## Decisões\n- Usar Vonage\n")

    curator = AutoCurator()
    change = CandidateChange(
        change_type="deprecate_entry",
        description="Vonage: em uso",
        evidence="reports/daily/2026-04-01.json",
        signal_source="logs",
    )
    result = curator.apply_change(topic_file, change)

    assert result is True
    content = topic_file.read_text()
    assert "DEPRECADO" in content or "deprecated" in content.lower()
    assert "Vonage" in content


# -------------------------------------------------------------------
# Logs Collector tests (BAT/Delphos report parser)
# -------------------------------------------------------------------
from collectors.logs_collector import LogsCollector, BATReportParser

def test_bat_report_parser_success():
    """Report with total_errors=0 → no failure signal."""
    report = {"total_errors": 0, "distinct_operations": 5}
    signals = BATReportParser.parse("bat-intraday", report, "reports/intraday/2026-04-01.json")
    assert signals == []

def test_bat_report_parser_failure():
    """Report with total_errors>0 → failure signal."""
    report = {"total_errors": 3, "operations": [{"name": "query-kql", "errors": 2}]}
    signals = BATReportParser.parse("bat-intraday", report, "reports/intraday/2026-04-01.json")
    assert len(signals) == 1
    assert signals[0].signal_type == "failure"
    assert signals[0].priority == 2
    assert signals[0].topic_ref == "bat-conectabot-observability.md"
    assert "total_errors=3" in signals[0].payload["description"]

def test_collector_initialization():
    collector = LogsCollector()
    assert collector.source == "logs"
    assert collector.priority == 2