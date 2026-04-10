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

    # Contradiction example — wikilink provides feature anchor for grouping
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

Decision: Feature X is enabled. [[feature-x]]
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

Decision: Feature X is disabled. [[feature-x]]
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


@pytest.fixture
def domain_lint_module():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import vault.quality.domain_lint as dl
    return dl


# ------------------------------------------------------------------
# 1. Contradictions
# ------------------------------------------------------------------

class TestContradictions:

    def test_detects_enabled_vs_disabled_contradiction(self, lint_module, sample_vault):
        report = lint_module.detect_contradictions(sample_vault)
        assert isinstance(report, list)

        def has_enabled_disabled_pair(row: dict) -> bool:
            a_text = row.get("a", "").lower()
            b_text = row.get("b", "").lower()
            return (
                ("enabled" in a_text and "disabled" in b_text)
                or ("disabled" in a_text and "enabled" in b_text)
            )

        assert any(has_enabled_disabled_pair(r) for r in report)

    def test_no_false_positive_when_same_semantic(self, lint_module, tmp_path):
        root = tmp_path / "memory" / "vault"
        (root / "decisions").mkdir(parents=True, exist_ok=True)
        (root / "decisions" / "d1.md").write_text("Decision: Feature X is enabled.", encoding="utf-8")
        (root / "decisions" / "d2.md").write_text("Decision: Feature X stays enabled.", encoding="utf-8")

        report = lint_module.detect_contradictions(root)
        assert report == []

    def test_no_false_positive_cross_feature(self, lint_module, tmp_path):
        """enabled in Feature A and disabled in Feature B are NOT contradictory."""
        root = tmp_path / "memory" / "vault"
        (root / "decisions").mkdir(parents=True, exist_ok=True)
        (root / "decisions" / "d1.md").write_text(
            "Decision: Feature A is enabled. Migration complete.", encoding="utf-8"
        )
        (root / "decisions" / "d2.md").write_text(
            "Decision: Feature B is disabled. Not ready for production.", encoding="utf-8"
        )
        report = lint_module.detect_contradictions(root)
        assert report == [], "Cross-feature enabled/disabled should not be flagged as contradiction"

    def test_no_cross_feature_false_positive(self, lint_module, tmp_path):
        """Enabled/disabled only contradict for the same feature/subject."""
        root = tmp_path / "memory" / "vault"
        (root / "decisions").mkdir(parents=True, exist_ok=True)
        (root / "decisions" / "d1.md").write_text(
            "Decision: Feature A is enabled.", encoding="utf-8"
        )
        (root / "decisions" / "d2.md").write_text(
            "Decision: Feature B is disabled.", encoding="utf-8"
        )

        report = lint_module.detect_contradictions(root)
        assert report == [], "different features should not be flagged as contradiction"


# ------------------------------------------------------------------
# 2. Orphans
# ------------------------------------------------------------------

class TestOrphans:

    def test_detects_orphan_pages(self, lint_module, sample_vault):
        orphans = lint_module.detect_orphans(sample_vault)
        # entity-a: no inbound links from any page (entity-b has no wikilink to entity-a)
        names = {o["page"] for o in orphans}
        assert "entity-a" in names, "entity-a has no inbound links, must be orphan"

    def test_linked_page_not_orphan(self, lint_module, sample_vault):
        orphans = lint_module.detect_orphans(sample_vault)
        names = {o["page"] for o in orphans}
        # entity-b has inbound link from entity-a
        assert "entity-b" not in names, "entity-b has inbound link from entity-a, must not be orphan"

    def test_orphan_means_zero_inbound_links(self, lint_module, tmp_path):
        """Orphan = page that no other page links TO."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions", "concepts"):
            (root / d).mkdir(parents=True, exist_ok=True)

        # page-x has outgoing link to page-y, but no one links TO page-x
        (root / "entities" / "page-x.md").write_text(
            "# Page X\n\nLinks: [[page-y]]\n", encoding="utf-8"
        )
        # page-y has an incoming link from page-x
        (root / "entities" / "page-y.md").write_text(
            "# Page Y\n\nNo links here.\n", encoding="utf-8"
        )

        orphans = lint_module.detect_orphans(root)
        names = {o["page"] for o in orphans}
        assert "page-x" in names, "page-x has no inbound links, must be orphan"
        assert "page-y" not in names, "page-y has inbound link from page-x, must not be orphan"


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


# ------------------------------------------------------------------
# 6. Domain completeness (quality/domain_lint.py)
# ------------------------------------------------------------------

class TestDomainLintCompleteness:

    def test_validate_vault_file_flags_missing_id_canonical(self, domain_lint_module, tmp_path):
        root = tmp_path / "memory" / "vault"
        (root / "decisions").mkdir(parents=True, exist_ok=True)
        page = root / "decisions" / "missing-id.md"
        page.write_text(
            """---
entity: decision:missing-id
type: decision
confidence: high
sources:
  - source_type: github_api
    source_ref: https://github.com/living/livy-memory-bot/issues/1
    retrieved_at: 2026-04-10T12:00:00Z
    mapper_version: test-v1
---
# Missing ID
""",
            encoding="utf-8",
        )

        errors = domain_lint_module.validate_vault_file(page)
        assert "missing_id_canonical" in errors

    def test_validate_vault_file_flags_invalid_id_canonical_prefix(self, domain_lint_module, tmp_path):
        root = tmp_path / "memory" / "vault"
        (root / "entities").mkdir(parents=True, exist_ok=True)
        page = root / "entities" / "bad-id.md"
        page.write_text(
            """---
entity: Person Example
type: person
id_canonical: invalidprefix-john
confidence: high
sources:
  - source_type: github_api
    source_ref: https://github.com/john
    retrieved_at: 2026-04-10T12:00:00Z
    mapper_version: test-v1
---
# Person
""",
            encoding="utf-8",
        )

        errors = domain_lint_module.validate_vault_file(page)
        assert any(err.startswith("invalid_id_prefix:") for err in errors)
