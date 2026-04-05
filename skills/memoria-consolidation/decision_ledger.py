#!/usr/bin/env python3
"""
decision_ledger.py — Append-only ledger for explainable memory decisions.
"""
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class DecisionRecord:
    topic: str
    entity_key: str
    entity_type: str
    old_status: str | None
    new_status: str | None
    why: str
    rule_id: str
    confidence: float
    result: str
    evidence_refs: list[str]
    observed_at: str


class DecisionLedger:
    def __init__(self, path: Path):
        self.path = path

    def deduplicate_records(self, records: list[DecisionRecord]) -> list[DecisionRecord]:
        """
        Remove duplicate records (same entity_key + rule_id) from the list.
        Keeps the first occurrence.
        """
        seen: set[tuple[str, str]] = set()
        deduped: list[DecisionRecord] = []
        for record in records:
            key = (record.entity_key, record.rule_id)
            if key not in seen:
                seen.add(key)
                deduped.append(record)
        return deduped

    def append_many(self, records: list[DecisionRecord]) -> None:
        if not records:
            return
        records = self.deduplicate_records(records)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            for record in records:
                f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
