#!/usr/bin/env python3
"""
Functional pilot test for the reconciliation pipeline.
Run from the worktree root: python3 scripts/test_reconciliation.py
"""
import sys
from pathlib import Path

# Add skills directory to path so we can import modules directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "memoria-consolidation"))

from signal_bus import SignalEvent
from evidence_normalizer import normalize_signal_event
from fact_snapshot_builder import build_topic_snapshots
from tempfile import TemporaryDirectory
from decision_ledger import DecisionLedger
from reconciler import reconcile_topic


def main():
    event = SignalEvent(
        source="github",
        priority=3,
        topic_ref="tldv-pipeline-state.md",
        signal_type="decision",
        payload={
            "description": "PR #12 migrate whisper",
            "evidence": "https://github.com/living/livy-tldv-jobs/pull/12",
            "confidence": 0.8,
        },
        origin_id="PR#12",
        origin_url="https://github.com/living/livy-tldv-jobs/pull/12",
    )
    item = normalize_signal_event(event)
    snapshots = build_topic_snapshots([item])

    assert "tldv-pipeline-state.md" in snapshots, "Snapshot not built for TLDV topic"
    snapshot = snapshots["tldv-pipeline-state.md"]
    assert len(snapshot.evidence) == 1
    assert item.entity_key in snapshot.claims_by_entity
    print("OK: reconciliation snapshot built for tldv-pipeline-state.md")

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "ledger.jsonl"
        decisions = reconcile_topic(
            "tldv-pipeline-state.md",
            {"open_issues": [{"key": item.entity_key, "title": "Whisper OOM", "status": "open"}], "resolved_issues": []},
            [item],
        )
        DecisionLedger(path).append_many(decisions)

        # The reconciler rules check for "tldv" combined with "github"/"logs" or "tldv" alone.
        # Since our mock item only has "github", no decisions will be generated right now.
        # Let's add a tldv event to trigger the rule:
        tldv_item = normalize_signal_event(SignalEvent(
            source="tldv", priority=2, topic_ref="tldv-pipeline-state.md", signal_type="decision",
            payload={"description": "PR #12 migrate whisper", "evidence": "meeting-1"}, origin_id="mtg1"
        ))

        decisions_with_both = reconcile_topic(
            "tldv-pipeline-state.md",
            {"open_issues": [{"key": item.entity_key, "title": "Whisper OOM", "status": "open"}], "resolved_issues": []},
            [item, tldv_item],
        )
        DecisionLedger(path).append_many(decisions_with_both)
        assert path.exists(), "Decision ledger file was not created"

        content = path.read_text()
        assert "R004_resolved_bug_moves_to_history_not_erasure" in content, "Rule ID missing from ledger"
        print("OK: reconciler generated decision and wrote to ledger")


if __name__ == "__main__":
    main()
