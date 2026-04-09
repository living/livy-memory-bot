"""TDD tests for reconciliation ledger entry schema.

Contract: Every line appended to memory/reconciliation-ledger.jsonl must follow:
    {
        "topic": str,
        "entity_key": str,
        "entity_type": str,
        "old_status": str | null,
        "new_status": str | null,
        "why": str,
        "rule_id": str,
        "confidence": float,
        "result": str,
        "evidence_refs": list[str],
        "observed_at": str,
    }
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest


LEDGER_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "memoria-consolidation"
    / "decision_ledger.py"
)


def _load_ledger_module():
    if not LEDGER_FILE.exists():
        raise ModuleNotFoundError(f"Missing decision_ledger module: {LEDGER_FILE}")
    spec = importlib.util.spec_from_file_location(
        "memoria_consolidation_decision_ledger", LEDGER_FILE
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load decision_ledger spec from {LEDGER_FILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("memoria_consolidation_decision_ledger", module)
    spec.loader.exec_module(module)
    return module


_REQUIRED_LEDGER_KEYS = {
    "topic",
    "entity_key",
    "entity_type",
    "old_status",
    "new_status",
    "why",
    "rule_id",
    "confidence",
    "result",
    "evidence_refs",
    "observed_at",
}

_VALID_RESULTS = {"accepted", "deferred", "conflict"}
_VALID_ENTITY_TYPES = {"issue", "decision"}


def _parse_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _assert_valid_ledger_record(record: dict) -> None:
    missing = _REQUIRED_LEDGER_KEYS - set(record.keys())
    assert not missing, f"ledger record missing required keys: {missing}"

    assert isinstance(record["topic"], str)
    assert isinstance(record["entity_key"], str)
    assert isinstance(record["entity_type"], str)
    assert record["entity_type"] in _VALID_ENTITY_TYPES
    assert record["old_status"] is None or isinstance(record["old_status"], str)
    assert record["new_status"] is None or isinstance(record["new_status"], str)
    assert isinstance(record["why"], str)
    assert isinstance(record["rule_id"], str)
    assert isinstance(record["confidence"], (int, float))
    assert 0.0 <= record["confidence"] <= 1.0
    assert isinstance(record["result"], str)
    assert record["result"] in _VALID_RESULTS
    assert isinstance(record["evidence_refs"], list)
    assert all(isinstance(x, str) for x in record["evidence_refs"])
    assert isinstance(record["observed_at"], str)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_decision_record_dataclass_fields_match_contract():
    """DecisionRecord dataclass must expose all contract fields."""
    module = _load_ledger_module()
    DecisionRecord = module.DecisionRecord

    record = DecisionRecord(
        topic="tldv-pipeline-state.md",
        entity_key="issue:vonage-timeout",
        entity_type="issue",
        old_status="open",
        new_status="resolved",
        why="Meeting claim confirmed by concrete evidence.",
        rule_id="R004_resolved_bug_moves_to_history_not_erasure",
        confidence=0.95,
        result="accepted",
        evidence_refs=["meeting:123", "github:pr-42"],
        observed_at="2026-04-09T22:00:00Z",
    )

    # Convert via asdict path used by append_many
    from dataclasses import asdict
    payload = asdict(record)
    _assert_valid_ledger_record(payload)


def test_append_many_writes_jsonl_records_conforming_to_schema(tmp_path):
    """Every appended JSONL line must satisfy ledger schema contract."""
    module = _load_ledger_module()
    DecisionLedger = module.DecisionLedger
    DecisionRecord = module.DecisionRecord

    ledger_path = tmp_path / "reconciliation-ledger.jsonl"
    ledger = DecisionLedger(ledger_path)

    records = [
        DecisionRecord(
            topic="tldv-pipeline-state.md",
            entity_key="issue:deploy-flake",
            entity_type="issue",
            old_status="open",
            new_status="resolved",
            why="Confirmed by logs + github",
            rule_id="R004_resolved_bug_moves_to_history_not_erasure",
            confidence=0.93,
            result="accepted",
            evidence_refs=["logs:abc", "github:pr-99"],
            observed_at="2026-04-09T22:05:00Z",
        ),
        DecisionRecord(
            topic="tldv-pipeline-state.md",
            entity_key="decision:migrate-vector-store",
            entity_type="decision",
            old_status=None,
            new_status="deferred",
            why="Meeting-only claim",
            rule_id="R003_advisory_decision_deferred",
            confidence=0.70,
            result="deferred",
            evidence_refs=["meeting:xyz"],
            observed_at="2026-04-09T22:10:00Z",
        ),
    ]

    ledger.append_many(records)

    rows = _parse_jsonl(ledger_path)
    assert len(rows) == 2
    for row in rows:
        _assert_valid_ledger_record(row)


def test_ledger_append_is_append_only_not_overwrite(tmp_path):
    """Second append_many call must append new records, preserving previous lines."""
    module = _load_ledger_module()
    DecisionLedger = module.DecisionLedger
    DecisionRecord = module.DecisionRecord

    ledger_path = tmp_path / "reconciliation-ledger.jsonl"
    ledger = DecisionLedger(ledger_path)

    first = DecisionRecord(
        topic="topic.md",
        entity_key="issue:first",
        entity_type="issue",
        old_status="open",
        new_status="resolved",
        why="first",
        rule_id="R001",
        confidence=0.9,
        result="accepted",
        evidence_refs=["ref1"],
        observed_at="2026-04-09T22:00:00Z",
    )
    second = DecisionRecord(
        topic="topic.md",
        entity_key="issue:second",
        entity_type="issue",
        old_status=None,
        new_status="new",
        why="second",
        rule_id="R005",
        confidence=0.6,
        result="deferred",
        evidence_refs=["ref2"],
        observed_at="2026-04-09T22:01:00Z",
    )

    ledger.append_many([first])
    size_after_first = ledger_path.stat().st_size
    lines_after_first = ledger_path.read_text().splitlines()
    assert len(lines_after_first) == 1

    ledger.append_many([second])
    size_after_second = ledger_path.stat().st_size
    lines_after_second = ledger_path.read_text().splitlines()

    assert size_after_second > size_after_first
    assert len(lines_after_second) == 2
    # first line preserved exactly
    assert lines_after_second[0] == lines_after_first[0]


def test_ledger_deduplicates_within_run_by_entity_key_and_rule_id(tmp_path):
    """Within same append_many call, duplicate (entity_key, rule_id) must be written once."""
    module = _load_ledger_module()
    DecisionLedger = module.DecisionLedger
    DecisionRecord = module.DecisionRecord

    ledger_path = tmp_path / "reconciliation-ledger.jsonl"
    ledger = DecisionLedger(ledger_path)

    dup1 = DecisionRecord(
        topic="topic.md",
        entity_key="issue:dup",
        entity_type="issue",
        old_status="open",
        new_status="resolved",
        why="first",
        rule_id="R004",
        confidence=0.95,
        result="accepted",
        evidence_refs=["ref-a"],
        observed_at="2026-04-09T22:00:00Z",
    )
    dup2 = DecisionRecord(
        topic="topic.md",
        entity_key="issue:dup",
        entity_type="issue",
        old_status="open",
        new_status="resolved",
        why="second",
        rule_id="R004",
        confidence=0.80,
        result="accepted",
        evidence_refs=["ref-b"],
        observed_at="2026-04-09T22:01:00Z",
    )

    ledger.append_many([dup1, dup2])
    rows = _parse_jsonl(ledger_path)
    assert len(rows) == 1
    _assert_valid_ledger_record(rows[0])


def test_ledger_deduplicates_across_runs_by_entity_key_and_rule_id(tmp_path):
    """If a record key already exists in file, later append_many should skip it."""
    module = _load_ledger_module()
    DecisionLedger = module.DecisionLedger
    DecisionRecord = module.DecisionRecord

    ledger_path = tmp_path / "reconciliation-ledger.jsonl"
    ledger = DecisionLedger(ledger_path)

    rec = DecisionRecord(
        topic="topic.md",
        entity_key="issue:exists",
        entity_type="issue",
        old_status="open",
        new_status="resolved",
        why="initial",
        rule_id="R004",
        confidence=0.95,
        result="accepted",
        evidence_refs=["ref"],
        observed_at="2026-04-09T22:00:00Z",
    )

    ledger.append_many([rec])
    ledger.append_many([rec])  # same key pair

    rows = _parse_jsonl(ledger_path)
    assert len(rows) == 1


def test_ledger_records_allow_nullable_old_new_status(tmp_path):
    """old_status/new_status may be null for deferred advisory decisions."""
    module = _load_ledger_module()
    DecisionLedger = module.DecisionLedger
    DecisionRecord = module.DecisionRecord

    ledger_path = tmp_path / "reconciliation-ledger.jsonl"
    ledger = DecisionLedger(ledger_path)

    rec = DecisionRecord(
        topic="topic.md",
        entity_key="decision:advisory",
        entity_type="decision",
        old_status=None,
        new_status=None,
        why="advisory only",
        rule_id="R003",
        confidence=0.7,
        result="deferred",
        evidence_refs=["meeting:1"],
        observed_at="2026-04-09T22:00:00Z",
    )

    ledger.append_many([rec])
    rows = _parse_jsonl(ledger_path)
    assert len(rows) == 1
    assert rows[0]["old_status"] is None
    assert rows[0]["new_status"] is None
    _assert_valid_ledger_record(rows[0])


def test_ledger_json_lines_are_parseable(tmp_path):
    """Each ledger line must be valid JSON (JSONL contract)."""
    module = _load_ledger_module()
    DecisionLedger = module.DecisionLedger
    DecisionRecord = module.DecisionRecord

    ledger_path = tmp_path / "reconciliation-ledger.jsonl"
    ledger = DecisionLedger(ledger_path)

    records = [
        DecisionRecord(
            topic="topic.md",
            entity_key=f"issue:{i}",
            entity_type="issue",
            old_status="open",
            new_status="resolved",
            why="ok",
            rule_id="R001",
            confidence=0.9,
            result="accepted",
            evidence_refs=["ref"],
            observed_at="2026-04-09T22:00:00Z",
        )
        for i in range(3)
    ]
    ledger.append_many(records)

    lines = ledger_path.read_text().splitlines()
    assert len(lines) == 3
    for idx, line in enumerate(lines):
        line = line.strip()
        assert line, f"line {idx} empty"
        obj = json.loads(line)
        assert isinstance(obj, dict)
        _assert_valid_ledger_record(obj)
