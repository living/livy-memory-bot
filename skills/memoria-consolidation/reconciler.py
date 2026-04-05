#!/usr/bin/env python3
"""
reconciler.py — Reconcile current topic state against concrete evidence.
"""
from collections import defaultdict
from decision_ledger import DecisionRecord


RULE_MEETING_NEEDS_CONFIRMATION = "R002_meeting_claim_needs_operational_confirmation"
RULE_RESOLVED_BUG_HISTORY = "R004_resolved_bug_moves_to_history_not_erasure"


def reconcile_topic(topic: str, current_state: dict, evidence_items: list) -> list[DecisionRecord]:
    by_entity = defaultdict(list)
    for item in evidence_items:
        by_entity[item.entity_key].append(item)

    decisions = []
    open_issue_keys = {issue["key"] for issue in current_state.get("open_issues", [])}

    for entity_key, items in by_entity.items():
        sources = {item.source for item in items}
        refs = [item.evidence_ref for item in items if item.evidence_ref]
        if entity_key in open_issue_keys and "tldv" in sources and ("github" in sources or "logs" in sources):
            decisions.append(DecisionRecord(
                topic=topic,
                entity_key=entity_key,
                entity_type="issue",
                old_status="open",
                new_status="resolved",
                why="Meeting claim was confirmed by concrete non-memory evidence.",
                rule_id=RULE_RESOLVED_BUG_HISTORY,
                confidence=0.95,
                result="accepted",
                evidence_refs=refs,
                observed_at=items[-1].observed_at,
            ))
        elif entity_key in open_issue_keys and sources == {"tldv"}:
            decisions.append(DecisionRecord(
                topic=topic,
                entity_key=entity_key,
                entity_type="issue",
                old_status="open",
                new_status="open",
                why="Meeting-only claim is not enough to change operational status.",
                rule_id=RULE_MEETING_NEEDS_CONFIRMATION,
                confidence=0.7,
                result="deferred",
                evidence_refs=refs,
                observed_at=items[-1].observed_at,
            ))
    return decisions
