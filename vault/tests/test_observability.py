"""Tests for vault/domain/observability.py — TDD RED phase.

Requirements:
- In-memory counters (Counter class)
- Histogram for distributions
- Atomic RunAuditor (write to tmp, then rename)
- build_run_id() function
- Path: memory/vault/wave-c-runs/
"""
from __future__ import annotations

import json
import time
from pathlib import Path



class TestBuildRunId:
    """build_run_id() generates unique run identifiers."""

    def test_returns_string(self):
        from vault.domain.observability import build_run_id
        run_id = build_run_id()
        assert isinstance(run_id, str)

    def test_run_id_contains_timestamp(self):
        from vault.domain.observability import build_run_id
        run_id = build_run_id()
        # Run ID should contain numeric timestamp component
        assert any(c.isdigit() for c in run_id)

    def test_run_ids_are_unique(self):
        from vault.domain.observability import build_run_id
        ids = [build_run_id() for _ in range(10)]
        assert len(set(ids)) == len(ids), "Run IDs must be unique"

    def test_run_id_format_is_deterministic(self):
        from vault.domain.observability import build_run_id
        run_id = build_run_id(prefix="test")
        assert "test" in run_id


class TestCounter:
    """In-memory counter for tracking increments and values."""

    def test_initial_value_is_zero(self):
        from vault.domain.observability import Counter
        c = Counter()
        assert c.value == 0

    def test_increment_increases_value(self):
        from vault.domain.observability import Counter
        c = Counter()
        c.increment()
        assert c.value == 1

    def test_increment_by_amount(self):
        from vault.domain.observability import Counter
        c = Counter()
        c.increment(5)
        assert c.value == 5

    def test_multiple_increments(self):
        from vault.domain.observability import Counter
        c = Counter()
        for _ in range(10):
            c.increment()
        assert c.value == 10

    def test_get_returns_current_value(self):
        from vault.domain.observability import Counter
        c = Counter()
        c.increment(3)
        assert c.get() == 3

    def test_reset_returns_to_zero(self):
        from vault.domain.observability import Counter
        c = Counter()
        c.increment(5)
        c.reset()
        assert c.value == 0

    def test_counter_with_label(self):
        from vault.domain.observability import Counter
        c = Counter(label="entities_processed")
        assert c.label == "entities_processed"


class TestHistogram:
    """Histogram for tracking value distributions."""

    def test_initial_bucket_count_is_zero(self):
        from vault.domain.observability import Histogram
        h = Histogram()
        assert h.count == 0
        assert h.sum == 0.0

    def test_record_adds_to_count_and_sum(self):
        from vault.domain.observability import Histogram
        h = Histogram()
        h.record(100.0)
        assert h.count == 1
        assert h.sum == 100.0

    def test_multiple_records(self):
        from vault.domain.observability import Histogram
        h = Histogram()
        h.record(10.0)
        h.record(20.0)
        h.record(30.0)
        assert h.count == 3
        assert h.sum == 60.0

    def test_mean_calculation(self):
        from vault.domain.observability import Histogram
        h = Histogram()
        h.record(10.0)
        h.record(20.0)
        h.record(30.0)
        assert h.mean() == 20.0

    def test_mean_returns_zero_when_empty(self):
        from vault.domain.observability import Histogram
        h = Histogram()
        assert h.mean() == 0.0

    def test_min_max_tracking(self):
        from vault.domain.observability import Histogram
        h = Histogram()
        h.record(15.0)
        h.record(5.0)
        h.record(25.0)
        assert h.min() == 5.0
        assert h.max() == 25.0

    def test_reset_clears_histogram(self):
        from vault.domain.observability import Histogram
        h = Histogram()
        h.record(100.0)
        h.reset()
        assert h.count == 0
        assert h.sum == 0.0


class TestRunAuditorAtomicWrite:
    """RunAuditor writes atomically: tmp file then rename."""

    def test_auditor_initializes(self):
        from vault.domain.observability import RunAuditor
        auditor = RunAuditor()
        assert auditor is not None

    def test_auditor_uses_memory_vault_runs_path(self):
        from vault.domain.observability import RunAuditor
        auditor = RunAuditor()
        assert "wave-c-runs" in str(auditor.runs_dir)

    def test_record_run_creates_run_file(self):
        from vault.domain.observability import RunAuditor, build_run_id
        auditor = RunAuditor()
        run_id = build_run_id(prefix="test")
        auditor.record_run(
            run_id=run_id,
            phase="C3",
            counters={"entities_processed": 5, "edges_created": 10},
            histograms={"entity_duration_ms": {"count": 3, "sum": 150.0}},
        )
        run_file = auditor.runs_dir / f"{run_id}.json"
        assert run_file.exists(), f"Run file {run_file} should exist after record_run"

    def test_record_run_writes_valid_json(self):
        from vault.domain.observability import RunAuditor, build_run_id
        auditor = RunAuditor()
        run_id = build_run_id(prefix="test-json")
        auditor.record_run(
            run_id=run_id,
            phase="C3",
            counters={"test_counter": 42},
            histograms={},
        )
        run_file = auditor.runs_dir / f"{run_id}.json"
        with open(run_file) as f:
            data = json.load(f)
        assert data["run_id"] == run_id
        assert data["phase"] == "C3"
        assert data["counters"]["test_counter"] == 42

    def test_audit_read_returns_all_runs(self):
        from vault.domain.observability import RunAuditor, build_run_id
        auditor = RunAuditor()
        run_id = build_run_id(prefix="test-audit")
        auditor.record_run(
            run_id=run_id,
            phase="C3",
            counters={"audit_test": 1},
            histograms={},
        )
        runs = auditor.audit_read()
        run_ids = [r["run_id"] for r in runs]
        assert run_id in run_ids

    def test_audit_read_returns_empty_list_when_no_runs(self):
        from vault.domain.observability import RunAuditor
        # Use a fresh temp directory for this test
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            auditor = RunAuditor(runs_dir=Path(tmpdir))
            runs = auditor.audit_read()
            assert runs == []

    def test_audit_read_respects_limit(self):
        from vault.domain.observability import RunAuditor, build_run_id
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            auditor = RunAuditor(runs_dir=Path(tmpdir))
            # Create 5 run files
            for i in range(5):
                run_id = build_run_id(prefix=f"limit-test-{i}")
                auditor.record_run(
                    run_id=run_id,
                    phase="C3",
                    counters={"n": i},
                    histograms={},
                )
            runs = auditor.audit_read(limit=3)
            assert len(runs) == 3


class TestObservabilityIntegration:
    """Integration: all observability components work together."""

    def test_full_observability_pipeline(self):
        from vault.domain.observability import (
            Counter,
            Histogram,
            RunAuditor,
            build_run_id,
        )
        # Track processing metrics
        entities_counter = Counter(label="entities_processed")
        edges_counter = Counter(label="edges_created")
        duration_hist = Histogram(label="entity_duration_ms")

        # Simulate processing
        entities_counter.increment()
        entities_counter.increment()
        edges_counter.increment()
        edges_counter.increment()
        edges_counter.increment()
        duration_hist.record(45.0)
        duration_hist.record(55.0)

        # Record run
        run_id = build_run_id(prefix="integration-test")
        auditor = RunAuditor()
        auditor.record_run(
            run_id=run_id,
            phase="C3",
            counters={
                entities_counter.label: entities_counter.get(),
                edges_counter.label: edges_counter.get(),
            },
            histograms={
                duration_hist.label: {
                    "count": duration_hist.count,
                    "sum": duration_hist.sum,
                    "mean": duration_hist.mean(),
                }
            },
        )

        # Verify persisted
        run_file = auditor.runs_dir / f"{run_id}.json"
        assert run_file.exists()
        with open(run_file) as f:
            data = json.load(f)
        assert data["counters"]["entities_processed"] == 2
        assert data["counters"]["edges_created"] == 3
        assert data["histograms"]["entity_duration_ms"]["mean"] == 50.0
