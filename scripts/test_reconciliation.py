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
from topic_rewriter import parse_topic_file, render_topic_file


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

        # Add a TLDV event so R004 fires (tldv + github confirms issue resolved)
        tldv_item = normalize_signal_event(SignalEvent(
            source="tldv", priority=2, topic_ref="tldv-pipeline-state.md",
            signal_type="decision",
            payload={"description": "PR #12 migrate whisper", "evidence": "meeting-1"},
            origin_id="mtg1",
        ))

        # Build state using the same slugification as curation_cron.py
        state_key = f"decision:{item.entity_key.split(':')[1]}"
        decisions = reconcile_topic(
            "tldv-pipeline-state.md",
            {
                "open_issues": [{"key": state_key, "title": "Whisper OOM", "status": "open"}],
                "resolved_issues": [],
            },
            [item, tldv_item],
        )
        assert len(decisions) > 0, "Reconciler should produce at least one decision with tldv+github evidence"
        DecisionLedger(path).append_many(decisions)

        content = path.read_text()
        assert "R004_resolved_bug_moves_to_history_not_erasure" in content, "Rule ID missing from ledger"
        print("OK: reconciler generated decision and wrote to ledger")

        # Test write mode guard
        from curation_cron import RECONCILIATION_WRITE_MODE
        assert RECONCILIATION_WRITE_MODE == False, "RECONCILIATION_WRITE_MODE should be False by default"
        print("OK: write mode guard is correctly disabled by default")

        # Test render against real topic file
        source = Path(__file__).resolve().parents[1] / "memory" / "curated" / "tldv-pipeline-state.md"
        if source.exists():
            content = source.read_text()
            parsed = parse_topic_file(content)
            updated = render_topic_file(parsed, decisions)
            assert "Issues Resolvidas / Superadas" in updated, "Section missing from rendered output"
            assert "regra:" in updated, "Decision explanation missing from rendered output"
            print("OK: topic rewriter parsed and updated sections")
        else:
            print(f"WARN: could not find {source} for testing")


def test_shadow_mode_reconciliation_runs_without_error():
    """Verify run_reconciliation_shadow_mode executes end-to-end without touching topic files."""
    from curation_cron import run_reconciliation_shadow_mode
    from tempfile import TemporaryDirectory
    from pathlib import Path as P

    with TemporaryDirectory() as tmp:
        fake_topic = P(tmp) / "test-topic.md"
        fake_topic.write_text("""---
name: test
---
# Test Topic

## Issues Abertas
- Whisper OOM

## Issues Resolvidas / Superadas
(nenhuma)
""")
        result = run_reconciliation_shadow_mode(
            correlation_id="test-001",
            topic_ref="test-topic.md",
            topic_path=fake_topic,
            events=[],  # no evidence → no decisions
        )

        assert result["mode"] == "shadow"
        assert result["decisions"] == 0
        assert not result.get("skipped")
        print("OK: shadow mode reconciliation runs without error")


if __name__ == "__main__":
    main()
    test_shadow_mode_reconciliation_runs_without_error()

    # Verify reconciliation report was written with all required fields
    report = Path(__file__).resolve().parents[1] / "memory" / "reconciliation-report.md"
    if report.exists():
        report_text = report.read_text()
        required_fields = ["confirmed:", "deferred:", "causal_completeness:"]
        for field in required_fields:
            assert field in report_text, f"Report missing required field: {field}"
        print("OK: reconciliation report contains all required fields")
    else:
        print("WARN: reconciliation-report.md not found (may not have been generated in this run)")
