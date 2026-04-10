"""Tests for domain frontmatter contract — validates existing vault pages meet
the canonical domain model requirements.

TDD RED phase: these tests define what domain-compliant frontmatter looks like
for entity and decision pages. They MUST fail against the current legacy files
(missing id_canonical, source_keys, first_seen_at, last_seen_at, lineage).
Only after Task 1–4 implementation + PoC/bulk migration will these go green.

Ref: docs/superpowers/specs/2026-04-10-llm-wiki-auto-evolutiva-design.md
     Wave A plan (2026-04-10) — Task 1
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure vault package is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def vault_root() -> Path:
    return Path(__file__).resolve().parents[2] / "memory" / "vault"


def parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter block from markdown text.

    Returns {} if no frontmatter found.
    Returns {} if YAML is malformed (treats as no frontmatter rather than crashing).
    """
    import yaml

    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return {}
    try:
        end = stripped.index("\n---", 3)
    except ValueError:
        # no closing ---
        return {}
    fm_text = stripped[3:end]
    try:
        return yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        # Malformed YAML in some vault files — treat as no frontmatter,
        # so the contract tests correctly flag missing fields.
        return {}


def _entity_files(vault_root: Path) -> list[Path]:
    """Return all entity .md files under vault_root/entities/."""
    entities_dir = vault_root / "entities"
    if not entities_dir.is_dir():
        return []
    return sorted(entities_dir.glob("*.md"))


def _decision_files(vault_root: Path) -> list[Path]:
    """Return all decision .md files under vault_root/decisions/."""
    decisions_dir = vault_root / "decisions"
    if not decisions_dir.is_dir():
        return []
    return sorted(decisions_dir.glob("*.md"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def frontmatter_of(path: Path) -> dict:
    return parse_frontmatter(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Required domain fields per entity type (per spec)
# ---------------------------------------------------------------------------

# Generic entity fields — required for ALL entity types
ENTITY_REQUIRED_DOMAIN_FIELDS = [
    "id_canonical",
    "source_keys",
    "first_seen_at",
    "last_seen_at",
]

# Decision-specific lineage minimum (per spec §3.4)
DECISION_REQUIRED_LINEAGE_FIELDS = [
    "run_id",
    "source_keys",
    "transformed_at",
    "mapper_version",
    "actor",
]

# ---------------------------------------------------------------------------
# Task 1 Step 1 — Entity pages require domain fields
# ---------------------------------------------------------------------------

class TestEntityDomainContract:
    """Every entity page must carry the canonical domain fields.

    Required (per Wave A spec):
      - id_canonical     — globally unique identifier with type prefix
      - source_keys      — list of all provenance keys for this entity
      - first_seen_at   — ISO datetime of earliest observation
      - last_seen_at    — ISO datetime of most recent observation

    These fields are the minimum bar for domain model compliance.
    """

    @pytest.mark.parametrize("field", ENTITY_REQUIRED_DOMAIN_FIELDS)
    def test_entity_pages_have_required_domain_fields(self, vault_root, field):
        """Every entity .md must declare each required domain field."""
        missing = []
        for path in _entity_files(vault_root):
            fm = frontmatter_of(path)
            if field not in fm:
                missing.append(path.name)
        assert missing == [], (
            f"Entity pages missing {field}: {missing}. "
            f"Every entity must carry '{field}' in frontmatter."
        )

    def test_entity_id_canonical_uses_valid_prefix(self, vault_root):
        """Every id_canonical must use a known type prefix (person:, repo:, etc.)."""
        from vault.domain.canonical_types import is_valid_id_prefix

        invalid = []
        for path in _entity_files(vault_root):
            fm = frontmatter_of(path)
            cid = fm.get("id_canonical")
            if cid and not is_valid_id_prefix(cid):
                invalid.append(f"{path.name}: {cid}")
        assert invalid == [], (
            f"Entity pages with invalid id_canonical prefix: {invalid}. "
            "Use: person:, project:, repo:, meeting:, card:"
        )

    def test_entity_source_keys_is_non_empty_list(self, vault_root):
        """Every entity's source_keys must be a non-empty list."""
        empty_or_invalid = []
        for path in _entity_files(vault_root):
            fm = frontmatter_of(path)
            sk = fm.get("source_keys")
            if not isinstance(sk, list) or len(sk) == 0:
                empty_or_invalid.append(path.name)
        assert empty_or_invalid == [], (
            f"Entity pages with empty/missing source_keys: {empty_or_invalid}. "
            "source_keys must be a non-empty list of provenance key strings."
        )


# ---------------------------------------------------------------------------
# Task 1 Step 2 — Decision pages require lineage minimum
# ---------------------------------------------------------------------------

class TestDecisionLineageContract:
    """Every decision page must carry the lineage minimum defined by the spec.

    Required lineage block (spec §3.4):
      - lineage.run_id
      - lineage.source_keys
      - lineage.transformed_at
      - lineage.mapper_version
      - lineage.actor

    These fields provide the minimum traceability chain for every decision.
    """

    def test_decision_pages_have_id_canonical(self, vault_root):
        """Every decision .md must declare an id_canonical."""
        missing = []
        for path in _decision_files(vault_root):
            fm = frontmatter_of(path)
            if "id_canonical" not in fm:
                missing.append(path.name)
        assert missing == [], (
            f"Decision pages missing id_canonical: {missing}. "
            "Every decision must carry 'id_canonical: decision:<slug>'."
        )

    def test_decision_pages_have_lineage_block(self, vault_root):
        """Every decision .md must declare a lineage mapping."""
        missing_or_invalid = []
        for path in _decision_files(vault_root):
            fm = frontmatter_of(path)
            lineage = fm.get("lineage")
            if not isinstance(lineage, dict):
                missing_or_invalid.append(path.name)
        assert missing_or_invalid == [], (
            f"Decision pages missing/invalid lineage block: {missing_or_invalid}. "
            "Every decision must carry 'lineage: {...}'."
        )

    @pytest.mark.parametrize("lineage_key", DECISION_REQUIRED_LINEAGE_FIELDS)
    def test_decision_lineage_has_required_keys(self, vault_root, lineage_key):
        """Every decision lineage block must contain all mandatory keys from spec §3.4."""
        missing = []
        for path in _decision_files(vault_root):
            fm = frontmatter_of(path)
            lineage = fm.get("lineage")
            if not isinstance(lineage, dict) or lineage_key not in lineage:
                missing.append(path.name)
        assert missing == [], (
            f"Decision pages with missing lineage.{lineage_key}: {missing}. "
            f"Every decision must carry lineage.{lineage_key}."
        )

    def test_decision_lineage_source_keys_is_non_empty_list(self, vault_root):
        """Every decision lineage.source_keys must be a non-empty list."""
        empty_or_invalid = []
        for path in _decision_files(vault_root):
            fm = frontmatter_of(path)
            lineage = fm.get("lineage")
            source_keys = lineage.get("source_keys") if isinstance(lineage, dict) else None
            if not isinstance(source_keys, list) or len(source_keys) == 0:
                empty_or_invalid.append(path.name)
        assert empty_or_invalid == [], (
            "Decision pages with empty/missing lineage.source_keys: "
            f"{empty_or_invalid}. lineage.source_keys must be a non-empty list."
        )

    def test_decision_pages_have_sources(self, vault_root):
        """Every decision .md must declare a non-empty sources list."""
        missing_or_empty = []
        for path in _decision_files(vault_root):
            fm = frontmatter_of(path)
            sources = fm.get("sources")
            if not isinstance(sources, list) or len(sources) == 0:
                missing_or_empty.append(path.name)
        assert missing_or_empty == [], (
            f"Decision pages with missing/empty/invalid sources: {missing_or_empty}. "
            "Every decision must carry 'sources: [...]' with at least one record."
        )

    def test_decision_sources_are_dicts_with_source_type(self, vault_root):
        """Every source record in a decision must be a dict with source_type."""
        broken = []
        for path in _decision_files(vault_root):
            fm = frontmatter_of(path)
            sources = fm.get("sources")
            if not isinstance(sources, list):
                continue
            for i, src in enumerate(sources):
                if not isinstance(src, dict):
                    broken.append(f"{path.name}[{i}]: not a dict")
                elif "source_type" not in src:
                    broken.append(f"{path.name}[{i}]: missing source_type")
        assert broken == [], (
            f"Decision source records missing source_type: {broken}. "
            "Each source must be a dict with at least source_type set."
        )

    def test_decision_sources_have_source_ref(self, vault_root):
        """Every source record must carry a source_ref URI."""
        missing = []
        for path in _decision_files(vault_root):
            fm = frontmatter_of(path)
            sources = fm.get("sources")
            if not isinstance(sources, list):
                continue
            for i, src in enumerate(sources):
                if isinstance(src, dict) and "source_ref" not in src:
                    missing.append(f"{path.name}[{i}]")
        assert missing == [], (
            f"Decision source records missing source_ref: {missing}. "
            "Each source must carry 'source_ref: <URI>'."
        )

    def test_decision_sources_have_retrieved_at(self, vault_root):
        """Every source record must carry a retrieved_at ISO datetime."""
        missing = []
        for path in _decision_files(vault_root):
            fm = frontmatter_of(path)
            sources = fm.get("sources")
            if not isinstance(sources, list):
                continue
            for i, src in enumerate(sources):
                if isinstance(src, dict) and "retrieved_at" not in src:
                    missing.append(f"{path.name}[{i}]")
        assert missing == [], (
            f"Decision source records missing retrieved_at: {missing}. "
            "Each source must carry 'retrieved_at: <ISO datetime>'."
        )

    def test_decision_sources_have_mapper_version(self, vault_root):
        """Every source record must carry a mapper_version string."""
        missing = []
        for path in _decision_files(vault_root):
            fm = frontmatter_of(path)
            sources = fm.get("sources")
            if not isinstance(sources, list):
                continue
            for i, src in enumerate(sources):
                if isinstance(src, dict) and "mapper_version" not in src:
                    missing.append(f"{path.name}[{i}]")
        assert missing == [], (
            f"Decision source records missing mapper_version: {missing}. "
            "Each source must carry 'mapper_version: <version string>'."
        )

    def test_decision_pages_have_last_verified(self, vault_root):
        """Every decision .md must declare a last_verified ISO date."""
        missing = []
        for path in _decision_files(vault_root):
            fm = frontmatter_of(path)
            if "last_verified" not in fm:
                missing.append(path.name)
        assert missing == [], (
            f"Decision pages missing last_verified: {missing}. "
            "Every decision must carry 'last_verified: <ISO date>'."
        )

    def test_decision_id_canonical_uses_decision_prefix(self, vault_root):
        """Every decision id_canonical must start with 'decision:'."""
        invalid = []
        for path in _decision_files(vault_root):
            fm = frontmatter_of(path)
            cid = fm.get("id_canonical", "")
            if cid and not cid.startswith("decision:"):
                invalid.append(f"{path.name}: {cid}")
        assert invalid == [], (
            f"Decision pages with non-decision id_canonical prefix: {invalid}. "
            "All decision id_canonical must start with 'decision:'."
        )

    def test_decision_source_types_are_in_allowed_set(self, vault_root):
        """Every source_type value must belong to the official allowed set."""
        from vault.domain.canonical_types import SOURCE_TYPES

        invalid = []
        for path in _decision_files(vault_root):
            fm = frontmatter_of(path)
            sources = fm.get("sources")
            if not isinstance(sources, list):
                continue
            for i, src in enumerate(sources):
                if isinstance(src, dict):
                    st = src.get("source_type", "")
                    if st and st not in SOURCE_TYPES:
                        invalid.append(f"{path.name}[{i}]: {st}")
        assert invalid == [], (
            f"Decision source records with unknown source_type: {invalid}. "
            f"Allowed values: {sorted(SOURCE_TYPES)}."
        )
