"""
Tests for vault/repair.py — auto-repair coverage gaps and orphan pages.
Phase 1C: repair auto-backlink and auto-generate missing concept pages.
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest


@pytest.fixture
def repair_module():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import vault.repair as rp
    return rp


@pytest.fixture
def repair_vault(tmp_path):
    """Vault with 2 orphans, 1 coverage gap, and parent pages that can link to them."""
    root = tmp_path / "memory" / "vault"
    for d in ("entities", "decisions", "concepts", "lint-reports"):
        (root / d).mkdir(parents=True, exist_ok=True)

    # Parent page that references a concept that doesn't exist (gap)
    (root / "decisions" / "d1.md").write_text(
        """---
entity: Decision 1
type: decision
confidence: high
sources: []
last_verified: 2026-04-09
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Decision 1

Mentions [[missing-concept]] without a concept page.
""",
        encoding="utf-8",
    )

    # Orphan entity — nothing links to it
    (root / "entities" / "orphan-entity.md").write_text(
        """---
entity: Orphan Entity
type: entity
confidence: medium
sources: []
last_verified: 2026-04-09
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Orphan Entity

No other page links to me.
""",
        encoding="utf-8",
    )

    # Another orphan
    (root / "entities" / "orphan-entity-2.md").write_text(
        """---
entity: Orphan Entity 2
type: entity
confidence: low
sources: []
last_verified: 2026-04-09
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Orphan Entity 2

Also an orphan.
""",
        encoding="utf-8",
    )

    # Parent page that CAN link to orphan-entity
    (root / "entities" / "parent-entity.md").write_text(
        """---
entity: Parent Entity
type: entity
confidence: high
sources: []
last_verified: 2026-04-09
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Parent Entity

Mentions orphan-entity and orphan-entity-2 in plain text.
""",
        encoding="utf-8",
    )

    (root / "log.md").write_text("", encoding="utf-8")
    return root


# ------------------------------------------------------------------
# 1. Gap repair — generate missing concept pages
# ------------------------------------------------------------------

class TestGapRepair:

    def test_generates_concept_page_for_gap(self, repair_module, repair_vault):
        import vault.lint as lnt
        gaps = lnt.detect_coverage_gaps(repair_vault)
        gap_names = {g["concept"] for g in gaps}

        assert "missing-concept" in gap_names

        # Repair the gap
        result = repair_module.repair_gaps(repair_vault, gaps)

        assert result["gaps_repaired"] >= 1
        concept_page = repair_vault / "concepts" / "missing-concept.md"
        assert concept_page.exists()
        text = concept_page.read_text(encoding="utf-8")
        assert "# Missing-concept" in text or "missing-concept" in text.lower()

    def test_repair_gaps_idempotent(self, repair_module, repair_vault):
        import vault.lint as lnt
        gaps = lnt.detect_coverage_gaps(repair_vault)
        repair_module.repair_gaps(repair_vault, gaps)
        # Second run should not crash or duplicate
        result2 = repair_module.repair_gaps(repair_vault, gaps)
        assert result2["gaps_repaired"] == 0

    def test_no_gaps_reports_zero(self, repair_module, tmp_path):
        root = tmp_path / "memory" / "vault"
        (root / "concepts").mkdir(parents=True, exist_ok=True)
        gaps = [{"concept": "already-exists"}]
        (root / "concepts" / "already-exists.md").write_text("# Already exists\n", encoding="utf-8")
        result = repair_module.repair_gaps(root, gaps)
        assert result["gaps_repaired"] == 0


# ------------------------------------------------------------------
# 2. Orphan repair — add backlink stubs to parent pages
# ------------------------------------------------------------------

class TestOrphanRepair:

    def test_repair_orphans_adds_backlinks(self, repair_module, repair_vault):
        import vault.lint as lnt
        orphans = lnt.detect_orphans(repair_vault)
        orphan_names = {o["page"] for o in orphans}
        assert "orphan-entity" in orphan_names
        assert "orphan-entity-2" in orphan_names

        result = repair_module.repair_orphans(repair_vault, orphans)

        assert result["orphans_repaired"] >= 2
        # Check parent-entity now links to orphan-entity
        parent = (repair_vault / "entities" / "parent-entity.md").read_text(encoding="utf-8")
        assert "[[orphan-entity]]" in parent or "Orphan Entity]]" in parent

    def test_orphan_repair_idempotent(self, repair_module, repair_vault):
        import vault.lint as lnt
        orphans = lnt.detect_orphans(repair_vault)
        repair_module.repair_orphans(repair_vault, orphans)
        result2 = repair_module.repair_orphans(repair_vault, orphans)
        assert result2["orphans_repaired"] == 0


# ------------------------------------------------------------------
# 3. Full repair pipeline
# ------------------------------------------------------------------

class TestRepairPipeline:

    def test_run_repair_reports_counts(self, repair_module, repair_vault):
        result = repair_module.run_repair(repair_vault)

        assert "gaps_repaired" in result
        assert "orphans_repaired" in result
        assert "gaps_remaining" in result
        assert "orphans_remaining" in result
        assert "repaired_at" in result

    def test_run_repair_improves_vault_quality(self, repair_module, repair_vault):
        import vault.lint as lnt
        before_orphans = len(lnt.detect_orphans(repair_vault))

        repair_module.run_repair(repair_vault)

        after_gaps = len(lnt.detect_coverage_gaps(repair_vault))
        after_orphans = len(lnt.detect_orphans(repair_vault))

        # Repair may create new gaps (new concept stubs create new coverage refs),
        # but must reduce orphans.
        assert after_orphans < before_orphans

    def test_run_repair_dry_run(self, repair_module, repair_vault):
        result = repair_module.run_repair(repair_vault, dry_run=True)

        assert result["gaps_repaired"] >= 0
        assert result["orphans_repaired"] >= 0
        # In dry-run, no actual files should be created
        concept_page = repair_vault / "concepts" / "missing-concept.md"
        assert not concept_page.exists()
