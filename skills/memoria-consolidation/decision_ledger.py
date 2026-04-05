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

    def append_many(self, records: list[DecisionRecord]) -> None:
        if not records:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            for record in records:
                f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
