#!/usr/bin/env python3
"""
fact_snapshot_builder.py — Build per-topic fact snapshots from normalized evidence.
"""
from dataclasses import dataclass, field
from collections import defaultdict
from evidence_normalizer import EvidenceItem


@dataclass
class TopicFactSnapshot:
    topic: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    claims_by_entity: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def add_evidence(self, item: EvidenceItem) -> None:
        self.evidence.append(item)
        self.claims_by_entity[item.entity_key].append(item.claim_type)

    def add_claim(self, entity_key: str, claim_type: str) -> None:
        self.claims_by_entity[entity_key].append(claim_type)


def build_topic_snapshots(items: list[EvidenceItem]) -> dict[str, TopicFactSnapshot]:
    snapshots: dict[str, TopicFactSnapshot] = {}
    for item in items:
        if not item.topic_ref:
            continue
        snapshot = snapshots.setdefault(item.topic_ref, TopicFactSnapshot(topic=item.topic_ref))
        snapshot.add_evidence(item)
    return snapshots
