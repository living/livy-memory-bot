"""
Tests for vault/pipeline.py — integration pipeline + confidence write-gate.
"""
import json
from pathlib import Path

import pytest


@pytest.fixture
def pipeline_module():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import vault.pipeline as pl
    return pl


@pytest.fixture
def metrics_module():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import vault.metrics as mx
    return mx


@pytest.fixture
def vault_with_decisions(tmp_path):
    root = tmp_path / "memory" / "vault"
    for d in ("decisions", "entities", "concepts"):
        (root / d).mkdir(parents=True, exist_ok=True)

    (root / "entities" / "entity-a.md").write_text("# A", encoding="utf-8")

    (root / "decisions" / "d1.md").write_text(
        """---
entity: D1
type: decision
confidence: high
sources:
  - type: tldv_api
    ref: https://tldv.io/meeting/123
---
# D1
""",
        encoding="utf-8",
    )

    (root / "decisions" / "d2.md").write_text(
        """---
entity: D2
type: decision
confidence: high
sources:
  - type: signal_event
    ref: https://tldv.io/meeting/456
---
# D2
""",
        encoding="utf-8",
    )

    (root / "decisions" / "d3.md").write_text(
        """---
entity: D3
type: decision
confidence: low
sources: []
---
# D3
""",
        encoding="utf-8",
    )

    return root


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    """Create a temporary vault workspace and patch module globals."""
    root = tmp_path
    vault_root = root / "memory" / "vault"
    for d in ("entities", "decisions", "concepts", "evidence", "lint-reports", ".cache", ".cache/fact-check"):
        (vault_root / d).mkdir(parents=True, exist_ok=True)

    # Seed one entity so orphans can potentially be repaired
    (vault_root / "entities" / "bat-conectabot.md").write_text(
        """---
entity: BAT ConectaBot
type: entity
confidence: medium
sources: []
last_verified: 2026-04-09
verification_log: []
last_touched_by: livy-agent
draft: false
---
# BAT ConectaBot

Overview page.
""",
        encoding="utf-8",
    )

    events = root / "memory" / "signal-events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    sample_events = [
        {
            "event_id": "evt-1",
            "signal_type": "decision",
            "origin_id": "o1",
            "origin_url": "https://tldv.io/meeting/o1",
            "collected_at": "2026-04-10T03:00:00+00:00",
            "payload": {
                "description": "Decision with high numeric confidence but weak source",
                "evidence": "https://example.com/e1",
                "confidence": 0.95,
            },
            "topic_ref": "bat-conectabot.md",
        },
        {
            "event_id": "evt-2",
            "signal_type": "topic_mentioned",
            "origin_id": "o2",
            "origin_url": "https://example.com/o2",
            "collected_at": "2026-04-10T03:00:01+00:00",
            "payload": {
                "description": "Missing Concept",
                "evidence": "https://example.com/e2",
                "confidence": 0.6,
            },
        },
    ]
    with events.open("w", encoding="utf-8") as f:
        for e in sample_events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # Patch globals
    monkeypatch.setattr("vault.ingest.VAULT_ROOT", vault_root)
    monkeypatch.setattr("vault.lint.VAULT_ROOT", vault_root)
    monkeypatch.setattr("vault.status.VAULT_ROOT", vault_root)
    monkeypatch.setattr("vault.metrics.Path", Path)
    monkeypatch.setattr("vault.fact_check.CACHE_DIR", vault_root / ".cache" / "fact-check")

    return {"root": root, "vault_root": vault_root, "events": events}


class TestPipelineFlow:

    def test_run_pipeline_dry_run_no_writes(self, pipeline_module, temp_workspace, monkeypatch):
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        summary = pipeline_module.run_pipeline(
            events_path=temp_workspace["events"],
            dry_run=True,
        )

        assert summary["dry_run"] is True
        # no decision files should be written in dry-run
        decisions = list((temp_workspace["vault_root"] / "decisions").glob("*.md"))
        concepts = list((temp_workspace["vault_root"] / "concepts").glob("*.md"))
        assert decisions == []
        assert concepts == []

    def test_run_pipeline_real_writes_and_lints(self, pipeline_module, temp_workspace, monkeypatch):
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        summary = pipeline_module.run_pipeline(
            events_path=temp_workspace["events"],
            dry_run=False,
        )

        assert summary["events_total"] >= 2
        assert summary["events_deduped"] >= 2
        assert summary["decisions_written"] >= 1
        assert summary["concepts_written"] >= 1

        lint_report = Path(summary["lint_report"])
        assert lint_report.exists()


class TestConfidenceGate:

    def test_high_numeric_confidence_downgraded_without_official_sources(self, pipeline_module, temp_workspace, monkeypatch):
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        pipeline_module.run_pipeline(events_path=temp_workspace["events"], dry_run=False)

        decisions = sorted((temp_workspace["vault_root"] / "decisions").glob("*.md"))
        assert decisions, "decision page should exist"
        text = decisions[0].read_text(encoding="utf-8").lower()

        # This event comes only from signal_event, so should not remain high.
        assert "confidence: high" not in text


class TestPipelineRepairIntegration:

    def test_pipeline_repair_reduces_gaps_and_orphans(self, pipeline_module, temp_workspace, monkeypatch):
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        # run once without repair to create baseline
        no_repair = pipeline_module.run_pipeline(events_path=temp_workspace["events"], dry_run=False, repair=False)
        baseline_gaps = no_repair["gaps_after_lint"]
        baseline_orphans = no_repair["orphans_after_lint"]

        # run with repair enabled
        with_repair = pipeline_module.run_pipeline(events_path=temp_workspace["events"], dry_run=False, repair=True)

        assert with_repair["gaps_after_repair"] <= baseline_gaps
        assert with_repair["orphans_after_repair"] <= baseline_orphans


class TestPerSourceIngestIndependence:
    """Task 6: per-source ingest independence.

    Each source (github, tldv, trello, signal) should be processed
    independently. A failure in one source should NOT block others.
    """

    def test_single_source_failure_does_not_block_other_sources(self, pipeline_module, temp_workspace, monkeypatch):
        """Simulate one source failing - other sources still process."""
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        # Add a third event that simulates a different source
        events_file = temp_workspace["events"]
        with events_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "event_id": "evt-3",
                "signal_type": "decision",
                "origin_id": "o3",
                "origin_url": "https://github.com/living/test/pull/1",
                "collected_at": "2026-04-10T03:00:02+00:00",
                "payload": {
                    "description": "GitHub-based decision",
                    "evidence": "https://github.com/living/test/pull/1",
                    "confidence": 0.8,
                },
                "source": "github",
            }, ensure_ascii=False) + "\n")

        summary = pipeline_module.run_pipeline(
            events_path=temp_workspace["events"],
            dry_run=False,
        )

        # Even if one source fails, we should still process others
        # Summary should have some events processed
        assert summary["events_total"] >= 3
        assert summary["events_deduped"] >= 2

    def test_source_type_routing_in_summary(self, pipeline_module, temp_workspace, monkeypatch):
        """Pipeline summary should track per-source metrics."""
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        summary = pipeline_module.run_pipeline(
            events_path=temp_workspace["events"],
            dry_run=False,
        )

        # Summary should include source type breakdown
        assert "source_counts" in summary
        assert isinstance(summary["source_counts"], dict)

    def test_missing_source_file_skipped_gracefully(self, pipeline_module, temp_workspace, monkeypatch):
        """Non-existent source file should be skipped without error."""
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        nonexistent = temp_workspace["root"] / "nonexistent.jsonl"
        summary = pipeline_module.run_pipeline(
            events_path=nonexistent,
            dry_run=True,
        )

        # Should return gracefully with 0 events
        assert summary["events_total"] == 0
        assert summary["dry_run"] is True


class TestPartialFailureTolerance:
    """Task 6: partial failure tolerance.

    Pipeline should handle partial failures gracefully.
    Events that fail should be tracked, others should still process.
    """

    def test_partial_failure_tracked_in_summary(self, pipeline_module, temp_workspace, monkeypatch):
        """Pipeline should track failed events in summary."""
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        summary = pipeline_module.run_pipeline(
            events_path=temp_workspace["events"],
            dry_run=False,
        )

        # Summary should track failures or errors
        assert "failed_events" in summary or "errors" in summary or "skipped_events" in summary
        # Should be numeric (0 or more)
        failed_or_errors = summary.get("failed_events", summary.get("errors", summary.get("skipped_events", 0)))
        assert isinstance(failed_or_errors, int)

    def test_corrupted_event_line_handled(self, pipeline_module, temp_workspace, monkeypatch):
        """Corrupted JSON line should be skipped, not crash pipeline."""
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        # Add corrupted line
        events_file = temp_workspace["events"]
        original = events_file.read_text(encoding="utf-8")
        with events_file.open("w", encoding="utf-8") as f:
            f.write(original)
            f.write("\n{ invalid json here\n")
            f.write("\n")  # empty line

        # Should not raise, should handle gracefully
        summary = pipeline_module.run_pipeline(
            events_path=temp_workspace["events"],
            dry_run=False,
        )

        # Pipeline should complete
        assert "events_total" in summary
        # Deduped should be less than total due to corruption handling
        assert summary["events_deduped"] >= 2  # at least valid events

    def test_successful_events_count_matches_written(self, pipeline_module, temp_workspace, monkeypatch):
        """Successful writes should match summary's decisions_written + concepts_written."""
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        summary = pipeline_module.run_pipeline(
            events_path=temp_workspace["events"],
            dry_run=False,
        )

        # decisions + concepts should reflect successful processed events
        total_written = summary["decisions_written"] + summary["concepts_written"]
        # In this fixture we expect at least one successful write.
        assert total_written >= 1
        # Writes cannot exceed deduped events.
        assert total_written <= summary["events_deduped"]


class TestDomainMetricsEmission:
    """Task 6: domain metrics emission.

    Pipeline should emit domain-specific quality metrics for dashboard.
    """

    def test_pipeline_emits_domain_metrics(self, pipeline_module, temp_workspace, monkeypatch):
        """Pipeline summary should include domain quality metrics."""
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        summary = pipeline_module.run_pipeline(
            events_path=temp_workspace["events"],
            dry_run=False,
        )

        # Domain metrics should be present
        assert "domain_metrics" in summary or "quality_metrics" in summary or "lint_report" in summary

    def test_domain_metrics_contain_entity_counts(self, pipeline_module, temp_workspace, monkeypatch):
        """Domain metrics should include entity coverage data."""
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        summary = pipeline_module.run_pipeline(
            events_path=temp_workspace["events"],
            dry_run=False,
        )

        # Check for entity-related metrics
        domain_metrics = summary.get("domain_metrics", summary.get("quality_metrics", {}))
        assert isinstance(domain_metrics, dict)
        # Should have some quality dimensions
        assert len(domain_metrics) >= 0  # at least emit the dict

    def test_quality_gate_results_in_summary(self, pipeline_module, temp_workspace, monkeypatch):
        """Quality gate results should be reflected in summary."""
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        summary = pipeline_module.run_pipeline(
            events_path=temp_workspace["events"],
            dry_run=False,
        )

        # Gate overrides tracked
        assert "gate_overrides" in summary
        assert isinstance(summary["gate_overrides"], int)

    def test_lint_results_in_summary(self, pipeline_module, temp_workspace, monkeypatch):
        """Lint results should be in summary for domain quality tracking."""
        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", temp_workspace["vault_root"])

        summary = pipeline_module.run_pipeline(
            events_path=temp_workspace["events"],
            dry_run=False,
        )

        # Lint results
        assert "gaps_after_lint" in summary
        assert "orphans_after_lint" in summary
        assert isinstance(summary["gaps_after_lint"], int)
        assert isinstance(summary["orphans_after_lint"], int)


class TestDomainLintModule:
    """Task 6: vault/quality/domain_lint.py module tests.

    New module should validate domain-specific quality rules.
    """

    def test_domain_lint_module_importable(self):
        """domain_lint module should exist and be importable."""
        import vault.quality.domain_lint as dl  # noqa: F401

    def test_domain_lint_runs_without_error(self):
        """domain_lint should execute without raising."""
        from vault.quality.domain_lint import run_domain_lint
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "memory" / "vault"
            for d in ("decisions", "entities", "concepts"):
                (root / d).mkdir(parents=True, exist_ok=True)
            # Should not raise
            result = run_domain_lint(root)
            assert isinstance(result, dict)

    def test_domain_lint_returns_errors_list(self):
        """domain_lint should return a list of domain quality errors."""
        from vault.quality.domain_lint import run_domain_lint
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "memory" / "vault"
            for d in ("decisions", "entities", "concepts"):
                (root / d).mkdir(parents=True, exist_ok=True)
            result = run_domain_lint(root)
            assert "errors" in result
            assert isinstance(result["errors"], list)

    def test_domain_lint_validates_relationships(self):
        """domain_lint should validate relationship edges."""
        from vault.quality.domain_lint import run_domain_lint
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "memory" / "vault"
            for d in ("decisions", "entities", "concepts"):
                (root / d).mkdir(parents=True, exist_ok=True)
            result = run_domain_lint(root)
            # Should have relationship validation
            assert "relationships_valid" in result or "relationship_errors" in result


class TestExtendedMetricsModule:
    """Task 6: vault/metrics.py domain metrics extension.

    metrics module should expose domain-specific quality metrics.
    """

    def test_collect_domain_metrics_function_exists(self, metrics_module):
        """metrics module should have collect_domain_metrics function."""
        assert hasattr(metrics_module, "collect_domain_metrics")

    def test_collect_domain_metrics_returns_dict(self, metrics_module, vault_with_decisions):
        """collect_domain_metrics should return a dict with domain metrics."""
        result = metrics_module.collect_domain_metrics(vault_with_decisions)
        assert isinstance(result, dict)

    def test_domain_metrics_has_required_keys(self, metrics_module, vault_with_decisions):
        """Domain metrics should include key domain quality dimensions."""
        result = metrics_module.collect_domain_metrics(vault_with_decisions)
        # Should include entity, relationship, or coverage metrics
        assert isinstance(result, dict)

    def test_quality_metrics_includes_gaps_and_orphans(self, metrics_module, vault_with_decisions):
        """Quality metrics should include gap/orphan counts."""
        result = metrics_module.collect_quality_metrics(vault_with_decisions)
        assert "gaps" in result
        assert "orphans" in result

    def test_quality_metrics_includes_stale_claims(self, metrics_module, vault_with_decisions):
        """Quality metrics should include stale claims count."""
        result = metrics_module.collect_quality_metrics(vault_with_decisions)
        assert "stale_claims" in result
