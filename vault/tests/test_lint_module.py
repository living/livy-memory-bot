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
# 6. Wave C: meeting/card id_source requirements + orphan edges + role validation
# ------------------------------------------------------------------

class TestWaveCLint_wave_c_lint:
    """C3.3: lint extension for Wave C entity model."""

    # --- meeting_id_source requirement ---

    def test_detect_meeting_id_source_missing(self, lint_module, tmp_path):
        """Meeting entity without meeting_id_source must be flagged."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions", "relationships"):
            (root / d).mkdir(parents=True, exist_ok=True)
        (root / "entities" / "meeting-no-source.md").write_text(
            """---
entity: Meeting Entity
type: meeting
id_canonical: meeting:daily-2026-04-10
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Daily Sync

No meeting_id_source field present.
""",
            encoding="utf-8",
        )
        result = lint_module.detect_meeting_id_source_requirements(root)
        assert len(result) >= 1
        assert any("meeting-no-source" in r["page"] for r in result)

    def test_detect_meeting_id_source_present(self, lint_module, tmp_path):
        """Meeting entity with meeting_id_source must NOT be flagged."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions", "relationships"):
            (root / d).mkdir(parents=True, exist_ok=True)
        (root / "entities" / "meeting-with-source.md").write_text(
            """---
entity: Meeting Entity
type: meeting
id_canonical: meeting:daily-2026-04-10
meeting_id_source: tldv:67890
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Daily Sync
""",
            encoding="utf-8",
        )
        result = lint_module.detect_meeting_id_source_requirements(root)
        page_names = {r["page"] for r in result}
        assert "meeting-with-source" not in page_names

    def test_detect_meeting_id_source_only_checks_meeting_type(self, lint_module, tmp_path):
        """Person entities should not be checked for meeting_id_source."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions", "relationships"):
            (root / d).mkdir(parents=True, exist_ok=True)
        (root / "entities" / "person-no-meeting.md").write_text(
            """---
entity: Person Example
type: person
id_canonical: person:john
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Person Example
""",
            encoding="utf-8",
        )
        result = lint_module.detect_meeting_id_source_requirements(root)
        page_names = {r["page"] for r in result}
        assert "person-no-meeting" not in page_names

    # --- card_id_source requirement ---

    def test_detect_card_id_source_missing(self, lint_module, tmp_path):
        """Card entity without card_id_source must be flagged."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions", "relationships"):
            (root / d).mkdir(parents=True, exist_ok=True)
        (root / "entities" / "card-no-source.md").write_text(
            """---
entity: Card Entity
type: card
id_canonical: card:abc123
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Card Title
""",
            encoding="utf-8",
        )
        result = lint_module.detect_card_id_source_requirements(root)
        assert len(result) >= 1
        assert any("card-no-source" in r["page"] for r in result)

    def test_detect_card_id_source_present(self, lint_module, tmp_path):
        """Card entity with card_id_source must NOT be flagged."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions", "relationships"):
            (root / d).mkdir(parents=True, exist_ok=True)
        (root / "entities" / "card-with-source.md").write_text(
            """---
entity: Card Entity
type: card
id_canonical: card:abc123
card_id_source: trello:abc123
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Card Title
""",
            encoding="utf-8",
        )
        result = lint_module.detect_card_id_source_requirements(root)
        page_names = {r["page"] for r in result}
        assert "card-with-source" not in page_names

    def test_detect_card_id_source_only_checks_card_type(self, lint_module, tmp_path):
        """Repo entities should not be checked for card_id_source."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions", "relationships"):
            (root / d).mkdir(parents=True, exist_ok=True)
        (root / "entities" / "repo-no-card.md").write_text(
            """---
entity: Repo Example
type: repo
id_canonical: repo:living/livy-memory-bot
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Repo Example
""",
            encoding="utf-8",
        )
        result = lint_module.detect_card_id_source_requirements(root)
        page_names = {r["page"] for r in result}
        assert "repo-no-card" not in page_names

    # --- orphan edge detection ---

    def test_detect_orphan_edges_flags_from_id_not_in_vault(self, lint_module, tmp_path):
        """Edge whose from_id references a non-existent entity must be flagged."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions", "relationships"):
            (root / d).mkdir(parents=True, exist_ok=True)
        # Entity B exists but A does not
        (root / "entities" / "entity-b.md").write_text(
            """---
entity: Entity B
type: person
id_canonical: person:bob
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Entity B
""",
            encoding="utf-8",
        )
        import json
        (root / "relationships" / "r.json").write_text(
            json.dumps([
                {
                    "from_id": "person:alice",  # Does not exist in vault
                    "to_id": "person:bob",
                    "role": "author",
                    "confidence": "high",
                    "sources": [],
                }
            ]),
            encoding="utf-8",
        )
        result = lint_module.detect_orphan_edges(root)
        assert len(result) >= 1
        assert any("person:alice" in r.get("orphan_id", "") for r in result)

    def test_detect_orphan_edges_flags_to_id_not_in_vault(self, lint_module, tmp_path):
        """Edge whose to_id references a non-existent entity must be flagged."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions", "relationships"):
            (root / d).mkdir(parents=True, exist_ok=True)
        # Entity A exists but C does not
        (root / "entities" / "entity-a.md").write_text(
            """---
entity: Entity A
type: person
id_canonical: person:alice
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Entity A
""",
            encoding="utf-8",
        )
        import json
        (root / "relationships" / "r.json").write_text(
            json.dumps([
                {
                    "from_id": "person:alice",
                    "to_id": "person:charlie",  # Does not exist in vault
                    "role": "participant",
                    "confidence": "high",
                    "sources": [],
                }
            ]),
            encoding="utf-8",
        )
        result = lint_module.detect_orphan_edges(root)
        assert len(result) >= 1
        assert any("person:charlie" in r.get("orphan_id", "") for r in result)

    def test_detect_orphan_edges_all_ids_exist(self, lint_module, tmp_path):
        """Edge where both from_id and to_id exist in vault must NOT be flagged."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions", "relationships"):
            (root / d).mkdir(parents=True, exist_ok=True)
        (root / "entities" / "entity-a.md").write_text(
            """---
entity: Entity A
type: person
id_canonical: person:alice
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Entity A
""",
            encoding="utf-8",
        )
        (root / "entities" / "entity-b.md").write_text(
            """---
entity: Entity B
type: person
id_canonical: person:bob
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Entity B
""",
            encoding="utf-8",
        )
        import json
        (root / "relationships" / "r.json").write_text(
            json.dumps([
                {
                    "from_id": "person:alice",
                    "to_id": "person:bob",
                    "role": "author",
                    "confidence": "high",
                    "sources": [],
                }
            ]),
            encoding="utf-8",
        )
        result = lint_module.detect_orphan_edges(root)
        assert result == [], f"Expected no orphan edges, got: {result}"

    def test_detect_orphan_edges_no_relationships_dir(self, lint_module, tmp_path):
        """Vault without relationships directory must return empty list (valid state)."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions"):
            (root / d).mkdir(parents=True, exist_ok=True)
        result = lint_module.detect_orphan_edges(root)
        assert result == []

    # --- role validation per allowed set ---

    def test_detect_invalid_relationship_roles_flags_unknown_role(
        self, lint_module, tmp_path
    ):
        """Edge with a role not in RELATIONSHIP_ROLES must be flagged."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions", "relationships"):
            (root / d).mkdir(parents=True, exist_ok=True)
        (root / "entities" / "entity-a.md").write_text(
            """---
entity: Entity A
type: person
id_canonical: person:alice
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Entity A
""",
            encoding="utf-8",
        )
        (root / "entities" / "entity-b.md").write_text(
            """---
entity: Entity B
type: person
id_canonical: person:bob
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Entity B
""",
            encoding="utf-8",
        )
        import json
        (root / "relationships" / "r.json").write_text(
            json.dumps([
                {
                    "from_id": "person:alice",
                    "to_id": "person:bob",
                    "role": "hacker",  # Not in RELATIONSHIP_ROLES
                    "confidence": "high",
                    "sources": [],
                }
            ]),
            encoding="utf-8",
        )
        result = lint_module.detect_invalid_relationship_roles(root)
        assert len(result) >= 1
        assert any("hacker" in r.get("role", "") for r in result)

    def test_detect_invalid_relationship_roles_passes_valid_roles(
        self, lint_module, tmp_path
    ):
        """Edge with a role in RELATIONSHIP_ROLES must NOT be flagged."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions", "relationships"):
            (root / d).mkdir(parents=True, exist_ok=True)
        (root / "entities" / "entity-a.md").write_text(
            """---
entity: Entity A
type: person
id_canonical: person:alice
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Entity A
""",
            encoding="utf-8",
        )
        (root / "entities" / "entity-b.md").write_text(
            """---
entity: Entity B
type: person
id_canonical: person:bob
confidence: high
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Entity B
""",
            encoding="utf-8",
        )
        import json
        (root / "relationships" / "r.json").write_text(
            json.dumps([
                {
                    "from_id": "person:alice",
                    "to_id": "person:bob",
                    "role": "author",  # Valid role
                    "confidence": "high",
                    "sources": [],
                }
            ]),
            encoding="utf-8",
        )
        result = lint_module.detect_invalid_relationship_roles(root)
        assert result == [], f"Expected no invalid roles, got: {result}"

    def test_detect_invalid_relationship_roles_no_relationships_dir(
        self, lint_module, tmp_path
    ):
        """Vault without relationships directory must return empty list (valid state)."""
        root = tmp_path / "memory" / "vault"
        for d in ("entities", "decisions"):
            (root / d).mkdir(parents=True, exist_ok=True)
        result = lint_module.detect_invalid_relationship_roles(root)
        assert result == []


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
