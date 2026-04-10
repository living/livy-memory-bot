"""
Tests for vault/status.py — operational metrics for dashboard.
Phase 1B TDD.
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def status_module():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import vault.status as st
    return st


@pytest.fixture
def populated_vault(tmp_path):
    root = tmp_path / "memory" / "vault"
    for d in ("entities", "decisions", "concepts", "evidence", "lint-reports", ".cache", ".cache/fact-check"):
        (root / d).mkdir(parents=True, exist_ok=True)

    # entities
    (root / "entities" / "a.md").write_text("# A", encoding="utf-8")
    (root / "entities" / "b.md").write_text("# B", encoding="utf-8")

    # decisions
    (root / "decisions" / "2026-04-09-d1.md").write_text("# D1", encoding="utf-8")

    # concepts
    (root / "concepts" / "c1.md").write_text("# C1", encoding="utf-8")

    # evidence
    (root / "evidence" / "e1.md").write_text("# E1", encoding="utf-8")

    # lint report
    (root / "lint-reports" / "2026-04-10-lint.md").write_text("# Lint", encoding="utf-8")

    # cache entries
    (root / ".cache" / "fact-check" / "x.json").write_text('{"confidence":"medium"}', encoding="utf-8")
    (root / ".cache" / "fact-check" / "y.json").write_text('{"confidence":"high"}', encoding="utf-8")

    # log with ingest/lint entries
    (root / "log.md").write_text(
        """## [2026-04-10] ingest | signal events\n  total: 3\n
## [2026-04-10] lint | daily cycle\n  contradictions: 1\n""",
        encoding="utf-8",
    )

    return root


# ------------------------------------------------------------------
# 1. Basic counters
# ------------------------------------------------------------------

class TestBasicCounters:

    def test_counts_entities(self, status_module, populated_vault):
        metrics = status_module.collect_metrics(populated_vault)
        assert metrics["entities_count"] == 2

    def test_counts_decisions(self, status_module, populated_vault):
        metrics = status_module.collect_metrics(populated_vault)
        assert metrics["decisions_count"] == 1

    def test_counts_concepts(self, status_module, populated_vault):
        metrics = status_module.collect_metrics(populated_vault)
        assert metrics["concepts_count"] == 1

    def test_counts_evidence(self, status_module, populated_vault):
        metrics = status_module.collect_metrics(populated_vault)
        assert metrics["evidence_count"] == 1

    def test_counts_lint_reports(self, status_module, populated_vault):
        metrics = status_module.collect_metrics(populated_vault)
        assert metrics["lint_reports_count"] == 1


# ------------------------------------------------------------------
# 2. Cache/health metrics
# ------------------------------------------------------------------

class TestCacheHealth:

    def test_counts_fact_check_cache_entries(self, status_module, populated_vault):
        metrics = status_module.collect_metrics(populated_vault)
        assert metrics["fact_check_cache_entries"] == 2

    def test_has_last_lint_report_date(self, status_module, populated_vault):
        metrics = status_module.collect_metrics(populated_vault)
        assert metrics["last_lint_report"] == "2026-04-10"


# ------------------------------------------------------------------
# 3. Log-derived activity metrics
# ------------------------------------------------------------------

class TestActivityMetrics:

    def test_counts_ingest_runs_from_log(self, status_module, populated_vault):
        metrics = status_module.collect_metrics(populated_vault)
        assert metrics["ingest_runs"] == 1

    def test_counts_lint_runs_from_log(self, status_module, populated_vault):
        metrics = status_module.collect_metrics(populated_vault)
        assert metrics["lint_runs"] == 1

    def test_last_activity_timestamp_present(self, status_module, populated_vault):
        metrics = status_module.collect_metrics(populated_vault)
        assert "last_activity" in metrics
        assert metrics["last_activity"] == "2026-04-10"


# ------------------------------------------------------------------
# 4. Dashboard output shape
# ------------------------------------------------------------------

class TestDashboardPayload:

    def test_status_payload_contains_required_keys(self, status_module, populated_vault):
        payload = status_module.build_status_payload(populated_vault)
        required = {
            "generated_at",
            "vault_health",
            "metrics",
        }
        assert required.issubset(payload.keys())

    def test_vault_health_ok_when_structure_present(self, status_module, populated_vault):
        payload = status_module.build_status_payload(populated_vault)
        assert payload["vault_health"] == "ok"

    def test_vault_health_degraded_when_structure_missing(self, status_module, tmp_path):
        root = tmp_path / "memory" / "vault"
        root.mkdir(parents=True, exist_ok=True)
        payload = status_module.build_status_payload(root)
        assert payload["vault_health"] == "degraded"


# ------------------------------------------------------------------
# 5. Markdown dashboard output
# ------------------------------------------------------------------

class TestMarkdownOutput:

    def test_render_markdown_contains_title(self, status_module, populated_vault):
        payload = status_module.build_status_payload(populated_vault)
        md = status_module.render_markdown(payload)
        assert "# Memory Vault Status" in md

    def test_render_markdown_lists_key_metrics(self, status_module, populated_vault):
        payload = status_module.build_status_payload(populated_vault)
        md = status_module.render_markdown(payload)
        assert "entities_count" in md
        assert "decisions_count" in md
        assert "fact_check_cache_entries" in md
