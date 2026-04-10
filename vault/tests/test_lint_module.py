"""
Tests for vault/lint.py — contradictions, orphan pages, stale claims, coverage gaps.
Phase 1B TDD.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture
def lint_module():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import vault.lint as lnt
    return lnt


@pytest.fixture
def sample_vault(tmp_path):
    """Create a synthetic vault with entities/decisions/concepts."""
    root = tmp_path / "memory" / "vault"
    for d in ("entities", "decisions", "concepts", "lint-reports"):
        (root / d).mkdir(parents=True, exist_ok=True)

    # Entity A references B
    (root / "entities" / "entity-a.md").write_text(
        """---
entity: Entity A
type: entity
confidence: high
sources: []
last_verified: 2026-04-01
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Entity A

Links: [[entity-b]]
Claim: API status is active.
""",
        encoding="utf-8",
    )

    # Entity B unlinked orphan
    (root / "entities" / "entity-b.md").write_text(
        """---
entity: Entity B
type: entity
confidence: medium
sources: []
last_verified: 2026-04-01
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Entity B

Standalone page.
""",
        encoding="utf-8",
    )

    # Contradiction example
    (root / "decisions" / "2026-04-01-enable-feature.md").write_text(
        """---
entity: Feature Flag
type: decision
confidence: high
sources: []
last_verified: 2026-04-01
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Enable Feature

Decision: Feature X is enabled.
""",
        encoding="utf-8",
    )

    (root / "decisions" / "2026-04-02-disable-feature.md").write_text(
        """---
entity: Feature Flag
type: decision
confidence: high
sources: []
last_verified: 2026-04-02
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Disable Feature

Decision: Feature X is disabled.
""",
        encoding="utf-8",
    )

    # Concept referenced but missing page
    (root / "entities" / "entity-c.md").write_text(
        """---
entity: Entity C
type: entity
confidence: medium
sources: []
last_verified: 2026-04-01
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Entity C

Mentions concept [[streaming-architecture]].
""",
        encoding="utf-8",
    )

    # Log file (optional)
    (root / "log.md").write_text("", encoding="utf-8")

    return root


# ------------------------------------------------------------------
# 1. Contradictions
# ------------------------------------------------------------------

class TestContradictions:

    def test_detects_enabled_vs_disabled_contradiction(self, lint_module, sample_vault):
        report = lint_module.detect_contradictions(sample_vault)
        assert isinstance(report, list)
        assert any("enabled" in r["a"].lower() and "disabled" in r["b"].lower() for r in report)

    def test_no_false_positive_when_same_semantic(self, lint_module, tmp_path):
        root = tmp_path / "memory" / "vault"
        (root / "decisions").mkdir(parents=True, exist_ok=True)
        (root / "decisions" / "d1.md").write_text("Decision: Feature X is enabled.", encoding="utf-8")
        (root / "decisions" / "d2.md").write_text("Decision: Feature X stays enabled.", encoding="utf-8")

        report = lint_module.detect_contradictions(root)
        assert report == []


# ------------------------------------------------------------------
# 2. Orphans
# ------------------------------------------------------------------

class TestOrphans:

    def test_detects_orphan_pages(self, lint_module, sample_vault):
        orphans = lint_module.detect_orphans(sample_vault)
        # entity-b has no inbound links
        names = {o["page"] for o in orphans}
        assert "entity-b" in names

    def test_linked_page_not_orphan(self, lint_module, sample_vault):
        orphans = lint_module.detect_orphans(sample_vault)
        names = {o["page"] for o in orphans}
        assert "entity-a" not in names


# ------------------------------------------------------------------
# 3. Stale claims (>7 days)
# ------------------------------------------------------------------

class TestStaleClaims:

    def test_stale_when_last_verified_older_than_7_days(self, lint_module):
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        stale_date = "2026-04-01"
        assert lint_module.is_stale(stale_date, now=now)

    def test_not_stale_within_7_days(self, lint_module):
        now = datetime(2026, 4, 10, tzinfo=timezone.utc)
        fresh_date = "2026-04-08"
        assert not lint_module.is_stale(fresh_date, now=now)

    def test_detects_stale_pages_from_frontmatter(self, lint_module, sample_vault):
        stale = lint_module.detect_stale_claims(sample_vault, now=datetime(2026, 4, 10, tzinfo=timezone.utc))
        assert len(stale) >= 1
        assert all("page" in s and "last_verified" in s for s in stale)


# ------------------------------------------------------------------
# 4. Coverage gaps
# ------------------------------------------------------------------

class TestCoverageGaps:

    def test_detects_concept_link_without_page(self, lint_module, sample_vault):
        gaps = lint_module.detect_coverage_gaps(sample_vault)
        missing = {g["concept"] for g in gaps}
        assert "streaming-architecture" in missing

    def test_no_gap_when_concept_exists(self, lint_module, sample_vault):
        (sample_vault / "concepts" / "streaming-architecture.md").write_text(
            "# Streaming Architecture", encoding="utf-8"
        )
        gaps = lint_module.detect_coverage_gaps(sample_vault)
        assert "streaming-architecture" not in {g["concept"] for g in gaps}


# ------------------------------------------------------------------
# 5. Lint report output
# ------------------------------------------------------------------

class TestLintReportOutput:

    def test_generates_daily_lint_report_file(self, lint_module, sample_vault):
        report_path = lint_module.run_lint(sample_vault, now=datetime(2026, 4, 10, tzinfo=timezone.utc))
        assert report_path.exists()
        assert report_path.name == "2026-04-10-lint.md"

    def test_lint_report_contains_sections(self, lint_module, sample_vault):
        report_path = lint_module.run_lint(sample_vault, now=datetime(2026, 4, 10, tzinfo=timezone.utc))
        text = report_path.read_text(encoding="utf-8").lower()
        assert "contrad" in text
        assert "orphan" in text
        assert "stale" in text
        assert "coverage" in text

    def test_run_lint_appends_log_entry(self, lint_module, sample_vault):
        lint_module.run_lint(sample_vault, now=datetime(2026, 4, 10, tzinfo=timezone.utc))
        log = (sample_vault / "log.md").read_text(encoding="utf-8").lower()
        assert "lint" in log
        assert "contradictions" in log
