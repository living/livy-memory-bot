#!/usr/bin/env python3
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from conflict_queue import CONFLICT_QUEUE_FILE, ConflictQueue
from signal_bus import SignalBus, SignalEvent


def test_signal_bus_persist_append_mode_preserves_existing_lines(tmp_path):
    path = tmp_path / "signal-events.jsonl"
    existing = '{"event_id":"existing"}\n'
    path.write_text(existing)

    bus = SignalBus()
    bus.emit(
        SignalEvent(
            source="logs",
            priority=2,
            signal_type="failure",
            origin_id="log-1",
            payload={"description": "new event"},
        )
    )

    bus.persist(path, mode="append")

    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert lines[0] == existing.strip()
    assert "new event" in lines[1]


def test_conflict_queue_default_file_points_to_workspace_memory():
    from conflict_queue import CONFLICT_QUEUE_FILE
    assert CONFLICT_QUEUE_FILE.name == "conflict-queue.md"
    assert CONFLICT_QUEUE_FILE.parent.name == "memory"
    assert CONFLICT_QUEUE_FILE.parents[1].name not in ("skills", "memoria-consolidation")


def test_conflict_queue_list_pending_parses_topic_and_status(tmp_path):
    queue_file = tmp_path / "conflict-queue.md"
    queue_file.write_text(
        "# Conflict Queue — 2026-04-05\n\n"
        "## CONFLITO-001 · memory/curated/topic-a.md\n"
        "**Detectado:** 2026-04-05 10:00 UTC\n"
        "**Status:** AWAITING_REVIEW\n"
        "**Resolução Lincoln:** ___________________________\n\n"
        "## CONFLITO-002 · memory/curated/topic-b.md\n"
        "**Detectado:** 2026-04-05 11:00 UTC\n"
        "**Status:** RESOLVED\n"
        "**Resolução Lincoln:** revisado\n"
    )

    queue = ConflictQueue(queue_file=queue_file)

    assert queue.list_pending() == [
        {
            "id": "CONFLITO-001",
            "topic": "memory/curated/topic-a.md",
            "status": "AWAITING_REVIEW",
        },
        {
            "id": "CONFLITO-002",
            "topic": "memory/curated/topic-b.md",
            "status": "RESOLVED",
        },
    ]


def test_signal_bus_persist_load_roundtrip(tmp_path):
    from signal_bus import SignalBus, SignalEvent
    from pathlib import Path
    path = tmp_path / "events.jsonl"
    bus = SignalBus()
    bus.emit(SignalEvent(
        source="tldv", priority=1, signal_type="decision", origin_id="t-1",
        topic_ref="memory/curated/foo.md", payload={"description": "x"}
    ))
    bus.persist(path)
    bus2 = SignalBus()
    bus2.load(path)
    assert len(bus2.events) == 1
    assert bus2.events[0].source == "tldv"
    assert bus2.events[0].topic_ref == "memory/curated/foo.md"
    assert bus2.events[0].payload["description"] == "x"


from evidence_normalizer import normalize_signal_event
from fact_snapshot_builder import TopicFactSnapshot
from signal_bus import SignalEvent


def test_normalize_signal_event_maps_to_entity_claim():
    event = SignalEvent(
        source="logs",
        priority=2,
        topic_ref="tldv-pipeline-state.md",
        signal_type="failure",
        payload={"description": "gw.tldv.io 502", "evidence": "/tmp/report.json", "confidence": 1.0},
        origin_id="report-1",
        origin_url=None,
    )
    item = normalize_signal_event(event)
    assert item.entity_type == "issue"
    assert item.claim_type == "failure"
    assert item.topic_ref == "tldv-pipeline-state.md"
    assert item.evidence_ref == "/tmp/report.json"
    assert item.entity_key == "issue:gw.tldv.io-502"
    assert item.confidence == 1.0


def test_normalize_signal_event_empty_payload():
    event = SignalEvent(
        source="logs",
        priority=2,
        topic_ref="tldv-pipeline-state.md",
        signal_type="failure",
        payload={},
        origin_id="report-1",
        origin_url=None,
    )
    item = normalize_signal_event(event)
    assert item.entity_key == "issue:report-1"
    assert item.confidence == 0.0


def test_topic_fact_snapshot_groups_claims_by_entity_key():
    snapshot = TopicFactSnapshot(topic="tldv-pipeline-state.md")
    snapshot.add_claim(entity_key="issue:gw-tldv-502", claim_type="failure")
    snapshot.add_claim(entity_key="issue:gw-tldv-502", claim_type="decision")
    assert set(snapshot.claims_by_entity["issue:gw-tldv-502"]) == {"failure", "decision"}

from reconciler import reconcile_topic
from evidence_normalizer import EvidenceItem


def test_reconciler_marks_issue_resolved_when_context_and_concrete_evidence_agree():
    current = {
        "open_issues": [{"key": "issue:whisper-oom", "title": "Whisper OOM", "status": "open"}],
        "resolved_issues": [],
    }
    evidence = [
        EvidenceItem("tldv-pipeline-state.md", "issue", "issue:whisper-oom", "decision", "tldv", 0.9, "meeting-1", "meeting-1", "2026-04-05T10:00:00Z"),
        EvidenceItem("tldv-pipeline-state.md", "issue", "issue:whisper-oom", "decision", "github", 0.8, "pr-12", "PR#12", "2026-04-05T10:01:00Z"),
    ]
    decisions = reconcile_topic("tldv-pipeline-state.md", current, evidence)
    assert decisions[0].result == "accepted"
    assert decisions[0].new_status == "resolved"
    assert decisions[0].rule_id == "R004_resolved_bug_moves_to_history_not_erasure"


def test_reconciler_defers_meeting_only_claim_without_operational_confirmation():
    current = {"open_issues": [{"key": "issue:cron-missing", "title": "Cron missing", "status": "open"}], "resolved_issues": []}
    evidence = [
        EvidenceItem("tldv-pipeline-state.md", "issue", "issue:cron-missing", "decision", "tldv", 0.9, "meeting-2", "meeting-2", "2026-04-05T10:00:00Z"),
    ]
    decisions = reconcile_topic("tldv-pipeline-state.md", current, evidence)
    assert decisions[0].result == "deferred"
    assert decisions[0].rule_id == "R002_meeting_claim_needs_operational_confirmation"

from topic_rewriter import parse_topic_file, render_topic_file
from decision_ledger import DecisionRecord


def test_render_topic_file_moves_resolved_issue_to_resolved_section():
    original = """---
name: tldv-pipeline-state
description: test
type: project
status: active
---

# TLDV Pipeline

## Issues Abertas
- Whisper OOM

## Issues Resolvidas / Superadas
(nenhuma)
"""
    parsed = parse_topic_file(original)
    decision = DecisionRecord(
        topic="tldv-pipeline-state.md",
        entity_key="issue:whisper-oom",
        entity_type="issue",
        old_status="open",
        new_status="resolved",
        why="PR #12 + meeting confirm migration.",
        rule_id="R004_resolved_bug_moves_to_history_not_erasure",
        confidence=0.95,
        result="accepted",
        evidence_refs=["meeting-1", "pr-12"],
        observed_at="2026-04-05T10:00:00Z",
    )
    updated = render_topic_file(parsed, [decision])
    assert "## Issues Resolvidas / Superadas" in updated
    assert "Whisper OOM" in updated
    assert "R004_resolved_bug_moves_to_history_not_erasure" in updated
