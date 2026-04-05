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


if __name__ == "__main__":
    main()
