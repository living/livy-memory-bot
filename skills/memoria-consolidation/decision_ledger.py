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
        Remove within-run duplicates (same entity_key + rule_id).
        Keeps the first occurrence within this call.
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
        """
        Append records to the ledger, skipping:
        1. Within-run duplicates (same entity_key + rule_id in the incoming list)
        2. Cross-run duplicates (same entity_key + rule_id already in the ledger file)
        """
        if not records:
            return
        records = self.deduplicate_records(records)
        if not records:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing keys for cross-run dedup
        existing_keys: set[tuple[str, str]] = set()
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    try:
                        obj = json.loads(line)
                        existing_keys.add((obj["entity_key"], obj["rule_id"]))
                    except json.JSONDecodeError:
                        pass  # Skip malformed lines

        # Only write records not already in the ledger
        new_records = [
            r for r in records
            if (r.entity_key, r.rule_id) not in existing_keys
        ]
        if not new_records:
            return

        with self.path.open("a") as f:
            for record in new_records:
                f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
