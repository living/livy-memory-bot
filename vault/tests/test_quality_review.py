"""
Tests for vault/quality/quality_review.py — weekly quality review report.

TDD: RED phase (failing tests), then GREEN (minimal impl), then REFACTOR.
"""
import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def quality_module():
    import sys
    from pathlib import Path as PP
    sys.path.insert(0, str(PP(__file__).resolve().parents[2]))
    from vault.quality import quality_review as qr
    return qr


@pytest.fixture
def tmp_vault(tmp_path):
    """Minimal vault with decisions, entities, concepts, relationships."""
    root = tmp_path / "memory" / "vault"
    for d in ("decisions", "entities", "concepts", "relationships"):
        (root / d).mkdir(parents=True, exist_ok=True)
    return root


def _write_decision(path: Path, entity_id: str, confidence: str, sources: list = None, body: str = "# Decision"):
    text = "---\n"
    text += f"entity: {entity_id}\n"
    text += f"type: decision\n"
    text += f"confidence: {confidence}\n"
    if sources:
        text += "sources:\n"
        for s in sources:
            text += f"  - type: {s['type']}\n    ref: {s['ref']}\n    retrieved: 2026-04-01T00:00:00Z\n    mapper_version: test-v1\n"
    text += f"---\n{body}\n"
    path.write_text(text, encoding="utf-8")


def _write_entity(path: Path, entity_id: str, entity_type: str, source_keys: list = None):
    text = "---\n"
    text += f"entity: {entity_id}\n"
    text += f"type: {entity_type}\n"
    if source_keys:
        text += "sources:\n"
        for s in source_keys:
            text += f"  - type: {s['type']}\n    ref: {s['ref']}\n    retrieved: 2026-04-01T00:00:00Z\n    mapper_version: test-v1\n"
    text += "---\n# Entity\n"
    path.write_text(text, encoding="utf-8")


def _write_relationships(path: Path, edges: list):
    path.write_text(json.dumps({"edges": edges}, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Section: source_coverage
# ---------------------------------------------------------------------------

class TestSourceCoverage:

    def test_total_source_types_found(self, quality_module, tmp_vault):
        """All SOURCE_TYPES are discovered from vault decision/entity files."""
        _write_decision(tmp_vault / "decisions" / "d1.md",
                        entity_id="D1",
                        confidence="high",
                        sources=[{"type": "github_api", "ref": "http://gh/1"}])
        _write_decision(tmp_vault / "decisions" / "d2.md",
                        entity_id="D2",
                        confidence="high",
                        sources=[{"type": "tldv_api", "ref": "http://tldv/1"}])
        _write_entity(tmp_vault / "entities" / "e1.md",
                       entity_id="person:u1",
                       entity_type="person",
                       source_keys=[{"type": "observation", "ref": "http://obs/1"}])

        coverage = quality_module.collect_source_coverage(tmp_vault)

        assert "github_api" in coverage["source_types_found"]
        assert "tldv_api" in coverage["source_types_found"]
        assert "observation" in coverage["source_types_found"]

    def test_unofficial_source_count(self, quality_module, tmp_vault):
        """signal_event and curated_topic are counted as unofficial."""
        _write_decision(tmp_vault / "decisions" / "d1.md",
                        entity_id="D1", confidence="high",
                        sources=[{"type": "signal_event", "ref": "http://sig/1"}])
        _write_decision(tmp_vault / "decisions" / "d2.md",
                        entity_id="D2", confidence="high",
                        sources=[{"type": "curated_topic", "ref": "http://cur/1"}])

        coverage = quality_module.collect_source_coverage(tmp_vault)

        assert coverage["unofficial_count"] == 2

    def test_official_source_count(self, quality_module, tmp_vault):
        """github_api, tldv_api, trello_api, supabase_rest count as official."""
        _write_decision(tmp_vault / "decisions" / "d1.md",
                        entity_id="D1", confidence="high",
                        sources=[{"type": "github_api", "ref": "http://gh/1"}])
        _write_decision(tmp_vault / "decisions" / "d2.md",
                        entity_id="D2", confidence="high",
                        sources=[{"type": "tldv_api", "ref": "http://tldv/1"}])

        coverage = quality_module.collect_source_coverage(tmp_vault)

        assert coverage["official_count"] == 2

    def test_missing_source_entities(self, quality_module, tmp_vault):
        """Entities without sources are flagged in missing_sources list."""
        _write_entity(tmp_vault / "entities" / "e1.md",
                       entity_id="person:u1", entity_type="person",
                       source_keys=None)  # no sources

        coverage = quality_module.collect_source_coverage(tmp_vault)

        assert any("person:u1" in str(m) for m in coverage["missing_sources"])

    def test_pct_official(self, quality_module, tmp_vault):
        """Percentage of official sources is computed."""
        _write_decision(tmp_vault / "decisions" / "d1.md",
                        entity_id="D1", confidence="high",
                        sources=[{"type": "github_api", "ref": "http://gh/1"}])
        _write_decision(tmp_vault / "decisions" / "d2.md",
                        entity_id="D2", confidence="high",
                        sources=[{"type": "signal_event", "ref": "http://sig/1"}])

        coverage = quality_module.collect_source_coverage(tmp_vault)

        assert coverage["pct_official"] == 50.0

    def test_source_coverage_structure(self, quality_module, tmp_vault):
        """Result has expected top-level keys."""
        coverage = quality_module.collect_source_coverage(tmp_vault)

        assert "source_types_found" in coverage
        assert "official_count" in coverage
        assert "unofficial_count" in coverage
        assert "missing_sources" in coverage
        assert "pct_official" in coverage


# ---------------------------------------------------------------------------
# Section: relation_completeness
# ---------------------------------------------------------------------------

class TestRelationCompleteness:

    def test_valid_edges_pass(self, quality_module, tmp_vault):
        """Edges with valid from_id, to_id, role, confidence are valid."""
        _write_relationships(tmp_vault / "relationships" / "r.json", [
            {"from_id": "person:a", "to_id": "repo:b", "role": "author",
             "confidence": "high"},
        ])
        result = quality_module.check_relation_completeness(tmp_vault)

        assert result["valid_edges"] == 1
        assert result["invalid_edges"] == 0

    def test_invalid_from_id_prefix(self, quality_module, tmp_vault):
        """Edge with unknown from_id prefix is flagged."""
        _write_relationships(tmp_vault / "relationships" / "r.json", [
            {"from_id": "unknown:p1", "to_id": "repo:b", "role": "author",
             "confidence": "high"},
        ])
        result = quality_module.check_relation_completeness(tmp_vault)

        assert result["invalid_edges"] == 1
        assert any("from_id" in str(e) for e in result["errors"])

    def test_invalid_to_id_prefix(self, quality_module, tmp_vault):
        """Edge with unknown to_id prefix is flagged."""
        _write_relationships(tmp_vault / "relationships" / "r.json", [
            {"from_id": "person:a", "to_id": "bad:p1", "role": "author",
             "confidence": "high"},
        ])
        result = quality_module.check_relation_completeness(tmp_vault)

        assert result["invalid_edges"] == 1
        assert any("to_id" in str(e) for e in result["errors"])

    def test_invalid_role(self, quality_module, tmp_vault):
        """Edge with unknown role is flagged."""
        _write_relationships(tmp_vault / "relationships" / "r.json", [
            {"from_id": "person:a", "to_id": "repo:b", "role": "bad_role",
             "confidence": "high"},
        ])
        result = quality_module.check_relation_completeness(tmp_vault)

        assert result["invalid_edges"] == 1
        assert any("role" in str(e) for e in result["errors"])

    def test_invalid_confidence(self, quality_module, tmp_vault):
        """Edge with non-enum confidence is flagged."""
        _write_relationships(tmp_vault / "relationships" / "r.json", [
            {"from_id": "person:a", "to_id": "repo:b", "role": "author",
             "confidence": "invalid_conf"},
        ])
        result = quality_module.check_relation_completeness(tmp_vault)

        assert result["invalid_edges"] == 1
        assert any("confidence" in str(e) for e in result["errors"])

    def test_missing_role(self, quality_module, tmp_vault):
        """Edge missing role field is flagged."""
        _write_relationships(tmp_vault / "relationships" / "r.json", [
            {"from_id": "person:a", "to_id": "repo:b", "confidence": "high"},
        ])
        result = quality_module.check_relation_completeness(tmp_vault)

        assert result["invalid_edges"] == 1

    def test_missing_confidence_ok(self, quality_module, tmp_vault):
        """Edge without confidence is valid (confidence is optional)."""
        _write_relationships(tmp_vault / "relationships" / "r.json", [
            {"from_id": "person:a", "to_id": "repo:b", "role": "author"},
        ])
        result = quality_module.check_relation_completeness(tmp_vault)

        assert result["invalid_edges"] == 0
        assert result["valid_edges"] == 1

    def test_relation_completeness_structure(self, quality_module, tmp_vault):
        """Result has expected top-level keys."""
        result = quality_module.check_relation_completeness(tmp_vault)

        assert "valid_edges" in result
        assert "invalid_edges" in result
        assert "errors" in result
        assert "edges_checked" in result


# ---------------------------------------------------------------------------
# Section: identity_ambiguity_queue
# ---------------------------------------------------------------------------

class TestIdentityAmbiguityQueue:

    def test_duplicate_github_login(self, quality_module, tmp_vault):
        """Same github_login across multiple person entities is ambiguous."""
        _write_entity(tmp_vault / "entities" / "p1.md",
                      entity_id="person:login1", entity_type="person",
                      source_keys=[{"type": "github_api", "ref": "http://gh/1"}])
        _write_entity(tmp_vault / "entities" / "p2.md",
                      entity_id="person:login2", entity_type="person",
                      source_keys=[{"type": "github_api", "ref": "http://gh/2"}])

        # Manually create ambiguity: p1 and p2 share the same github_login in body
        # Simulate by writing entity files that look similar
        (tmp_vault / "entities" / "p1.md").write_text(
            "---\nentity: person:login1\ntype: person\nsources:\n  - type: github_api\n    ref: https://github.com/sameuser\n    retrieved: 2026-04-01T00:00:00Z\n    mapper_version: test-v1\n---\n# Person\n",
            encoding="utf-8",
        )
        (tmp_vault / "entities" / "p2.md").write_text(
            "---\nentity: person:login2\ntype: person\nsources:\n  - type: github_api\n    ref: https://github.com/sameuser\n    retrieved: 2026-04-01T00:00:00Z\n    mapper_version: test-v1\n---\n# Person\n",
            encoding="utf-8",
        )

        result = quality_module.detect_identity_ambiguity(tmp_vault)

        assert result["ambiguity_count"] == 1
        assert any("sameuser" in str(a) for a in result["ambiguities"])

    def test_no_ambiguity_clean(self, quality_module, tmp_vault):
        """Unique github_logins produce no ambiguities."""
        (tmp_vault / "entities" / "p1.md").write_text(
            "---\nentity: person:user_a\ntype: person\nsources:\n  - type: github_api\n    ref: https://github.com/usera\n    retrieved: 2026-04-01T00:00:00Z\n    mapper_version: test-v1\n---\n# Person\n",
            encoding="utf-8",
        )
        (tmp_vault / "entities" / "p2.md").write_text(
            "---\nentity: person:user_b\ntype: person\nsources:\n  - type: github_api\n    ref: https://github.com/userb\n    retrieved: 2026-04-01T00:00:00Z\n    mapper_version: test-v1\n---\n# Person\n",
            encoding="utf-8",
        )

        result = quality_module.detect_identity_ambiguity(tmp_vault)

        assert result["ambiguity_count"] == 0

    def test_identity_ambiguity_structure(self, quality_module, tmp_vault):
        """Result has expected top-level keys."""
        result = quality_module.detect_identity_ambiguity(tmp_vault)

        assert "ambiguity_count" in result
        assert "ambiguities" in result


# ---------------------------------------------------------------------------
# Section: mismatches
# ---------------------------------------------------------------------------

class TestMismatches:

    def test_missing_confidence_mismatch(self, quality_module, tmp_vault):
        """Decision without confidence is flagged as mismatch."""
        (tmp_vault / "decisions" / "d1.md").write_text(
            "---\nentity: D1\ntype: decision\n---\n# D1\n",
            encoding="utf-8",
        )
        result = quality_module.detect_mismatches(tmp_vault)

        assert result["mismatch_count"] == 1
        assert any("confidence" in str(m) for m in result["mismatches"])

    def test_invalid_confidence_mismatch(self, quality_module, tmp_vault):
        """Decision with non-enum confidence is flagged."""
        _write_decision(tmp_vault / "decisions" / "d1.md",
                        entity_id="D1", confidence="super_high",
                        sources=[])
        result = quality_module.detect_mismatches(tmp_vault)

        assert result["mismatch_count"] >= 1
        assert any("confidence" in str(m) for m in result["mismatches"])

    def test_missing_type_field(self, quality_module, tmp_vault):
        """File without type field is flagged."""
        (tmp_vault / "decisions" / "d1.md").write_text(
            "---\nentity: D1\nconfidence: high\n---\n# D1\n",
            encoding="utf-8",
        )
        result = quality_module.detect_mismatches(tmp_vault)

        assert result["mismatch_count"] >= 1
        assert any("type" in str(m) for m in result["mismatches"])

    def test_missing_source_ref(self, quality_module, tmp_vault):
        """Source record without ref is flagged."""
        _write_decision(tmp_vault / "decisions" / "d1.md",
                        entity_id="D1", confidence="high",
                        sources=[{"type": "github_api", "ref": ""}])
        result = quality_module.detect_mismatches(tmp_vault)

        assert result["mismatch_count"] >= 1

    def test_no_mismatches_clean(self, quality_module, tmp_vault):
        """Valid vault has zero mismatches."""
        _write_decision(tmp_vault / "decisions" / "d1.md",
                        entity_id="D1", confidence="high",
                        sources=[{"type": "github_api", "ref": "http://gh/1"}])
        result = quality_module.detect_mismatches(tmp_vault)

        assert result["mismatch_count"] == 0

    def test_mismatches_structure(self, quality_module, tmp_vault):
        """Result has expected top-level keys."""
        result = quality_module.detect_mismatches(tmp_vault)

        assert "mismatch_count" in result
        assert "mismatches" in result


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

class TestReportGeneration:

    def test_generate_report_returns_dict(self, quality_module, tmp_vault):
        """generate_quality_report returns a dict."""
        result = quality_module.generate_quality_report(tmp_vault)

        assert isinstance(result, dict)

    def test_report_has_all_sections(self, quality_module, tmp_vault):
        """Report contains source_coverage, relation_completeness,
        identity_ambiguity_queue, mismatches."""
        result = quality_module.generate_quality_report(tmp_vault)

        assert "source_coverage" in result
        assert "relation_completeness" in result
        assert "identity_ambiguity_queue" in result
        assert "mismatches" in result

    def test_report_has_metadata(self, quality_module, tmp_vault):
        """Report contains generated_at and vault_path."""
        result = quality_module.generate_quality_report(tmp_vault)

        assert "generated_at" in result
        assert "vault_path" in result
        assert "2026-04" in result["generated_at"]

    def test_write_report_to_file(self, quality_module, tmp_vault, tmp_path):
        """write_report writes a dated .md file to memory/vault/quality-review/."""
        quality_module.generate_quality_report(tmp_vault)
        out_path = quality_module.write_report(tmp_vault, output_dir=tmp_path)

        assert out_path is not None
        assert out_path.suffix == ".md"
        assert "2026-04-10" in out_path.name

    def test_write_report_creates_dir(self, quality_module, tmp_vault, tmp_path):
        """write_report creates output directory if it doesn't exist."""
        out_path = quality_module.write_report(tmp_vault, output_dir=tmp_path)

        assert out_path.parent.exists()

    def test_report_content_has_sections(self, quality_module, tmp_vault, tmp_path):
        """Written report contains markdown section headers."""
        out_path = quality_module.write_report(tmp_vault, output_dir=tmp_path)
        content = out_path.read_text(encoding="utf-8")

        assert "## Source Coverage" in content
        assert "## Relation Completeness" in content
        assert "## Identity Ambiguity Queue" in content
        assert "## Mismatches" in content

    def test_report_content_has_summary(self, quality_module, tmp_vault, tmp_path):
        """Written report contains a summary section."""
        out_path = quality_module.write_report(tmp_vault, output_dir=tmp_path)
        content = out_path.read_text(encoding="utf-8")

        assert "## Summary" in content or "summary" in content.lower()
