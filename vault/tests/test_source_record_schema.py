"""
Tests for canonical source record schema in vault/ingest.py.
Phase 1D: validates that _decision_frontmatter and _concept_frontmatter
produce frontmatter conforming to vault/domain/canonical_types.py SOURCE_FIELDS.

Canonical source record schema:
  source_type  (not "type")
  source_ref   (not "ref")
  retrieved_at  (not "retrieved")
  mapper_version
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_yaml_block(text: str) -> dict:
    """Parse the YAML frontmatter block from markdown text."""
    assert text.startswith("---\n"), "text must start with ---"
    end = text.index("\n---", 4)
    block = text[4:end]
    result = {}
    in_sources = False
    sources: list[dict] = []
    current: dict[str, str] = {}

    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "sources:":
            in_sources = True
            continue
        if in_sources:
            if stripped.startswith("-"):
                if current:
                    sources.append(current)
                stripped = stripped[1:].strip()
                if ":" in stripped:
                    k, _, v = stripped.partition(":")
                    current = {k.strip(): v.strip()}
                continue
            if ":" in stripped:
                k, _, v = stripped.partition(":")
                k = k.strip()
                v = v.strip()
                if v == "":
                    in_sources = False
                    if current:
                        sources.append(current)
                        current = {}
                    continue
                if k in ("type", "source_type"):
                    current["source_type"] = v
                elif k in ("ref", "source_ref"):
                    current["source_ref"] = v
                elif k in ("retrieved", "retrieved_at"):
                    current["retrieved_at"] = v
                elif k == "mapper_version":
                    current["mapper_version"] = v
        else:
            if ":" in stripped:
                k, _, v = stripped.partition(":")
                result[k.strip()] = v.strip()
    if current:
        sources.append(current)
    if sources:
        result["sources"] = sources
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCanonicalSourceRecordSchema:
    """Decision and concept frontmatter must use canonical source record fields."""

    def test_decision_frontmatter_has_source_type_not_type(self, tmp_path):
        """Canonical: 'source_type' field, not 'type' inside sources[0]."""
        import vault.ingest as ing
        ing.VAULT_ROOT = tmp_path / "vault"
        (tmp_path / "vault").mkdir(parents=True, exist_ok=True)

        decision = {
            "description": "Usar entidade como base",
            "evidence": "https://tldv.io/meeting/123",
            "confidence": 0.8,
            "origin_id": "meeting-001",
            "origin_url": "https://tldv.io/meeting/123",
            "collected_at": "2026-04-07T13:00:00+00:00",
        }
        path = ing.upsert_decision(decision)
        fm_text = path.read_text(encoding="utf-8")
        parsed = _parse_yaml_block(fm_text)

        assert "sources" in parsed, "sources block required"
        src = parsed["sources"][0]
        assert "source_type" in src, f"canonical field 'source_type' required, got: {list(src.keys())}"
        assert "type" not in src, "legacy field 'type' must not appear in sources record"
        assert src["source_type"] == "signal_event"

    def test_decision_frontmatter_has_source_ref_not_ref(self, tmp_path):
        """Canonical: 'source_ref' field, not 'ref' inside sources[0]."""
        import vault.ingest as ing
        ing.VAULT_ROOT = tmp_path / "vault"
        (tmp_path / "vault").mkdir(parents=True, exist_ok=True)

        decision = {
            "description": "Teste",
            "evidence": "url",
            "confidence": 0.8,
            "origin_id": "m1",
            "origin_url": "https://tldv.io/meeting/abc",
            "collected_at": "2026-04-07T13:00:00+00:00",
        }
        path = ing.upsert_decision(decision)
        fm_text = path.read_text(encoding="utf-8")
        parsed = _parse_yaml_block(fm_text)

        src = parsed["sources"][0]
        assert "source_ref" in src, f"canonical field 'source_ref' required, got: {list(src.keys())}"
        assert "ref" not in src, "legacy field 'ref' must not appear in sources record"
        assert src["source_ref"] == "https://tldv.io/meeting/abc"

    def test_decision_frontmatter_has_retrieved_at_not_retrieved(self, tmp_path):
        """Canonical: 'retrieved_at' field (ISO timestamp), not 'retrieved' (date only)."""
        import vault.ingest as ing
        ing.VAULT_ROOT = tmp_path / "vault"
        (tmp_path / "vault").mkdir(parents=True, exist_ok=True)

        decision = {
            "description": "Teste",
            "evidence": "url",
            "confidence": 0.8,
            "origin_id": "m1",
            "origin_url": "url",
            "collected_at": "2026-04-07T13:00:00+00:00",
        }
        path = ing.upsert_decision(decision)
        fm_text = path.read_text(encoding="utf-8")
        parsed = _parse_yaml_block(fm_text)

        src = parsed["sources"][0]
        assert "retrieved_at" in src, f"canonical field 'retrieved_at' required, got: {list(src.keys())}"
        assert "retrieved" not in src, "legacy field 'retrieved' must not appear in sources record"
        # retrieved_at should be an ISO timestamp, not just YYYY-MM-DD
        assert "T" in src["retrieved_at"], f"retrieved_at must be ISO timestamp, got: {src['retrieved_at']}"

    def test_decision_frontmatter_has_mapper_version(self, tmp_path):
        """Canonical: sources[0] must include mapper_version field."""
        import vault.ingest as ing
        ing.VAULT_ROOT = tmp_path / "vault"
        (tmp_path / "vault").mkdir(parents=True, exist_ok=True)

        decision = {
            "description": "Teste",
            "evidence": "url",
            "confidence": 0.8,
            "origin_id": "m1",
            "origin_url": "url",
            "collected_at": "2026-04-07T13:00:00+00:00",
        }
        path = ing.upsert_decision(decision)
        fm_text = path.read_text(encoding="utf-8")
        parsed = _parse_yaml_block(fm_text)

        src = parsed["sources"][0]
        assert "mapper_version" in src, f"canonical field 'mapper_version' required, got: {list(src.keys())}"
        assert src["mapper_version"] != "", "mapper_version must not be empty"

    def test_concept_frontmatter_has_all_canonical_fields(self, tmp_path):
        """Concept frontmatter must use the same canonical source record schema."""
        import vault.ingest as ing
        ing.VAULT_ROOT = tmp_path / "vault"
        (tmp_path / "vault").mkdir(parents=True, exist_ok=True)

        topic = {
            "description": "Patrimônio Líquido",
            "evidence": "url",
            "confidence": 0.6,
            "origin_id": "topic-001",
            "origin_url": "https://tldv.io/meeting/xyz",
            "collected_at": "2026-04-07T13:00:00+00:00",
        }
        path = ing.upsert_concept(topic)
        fm_text = path.read_text(encoding="utf-8")
        parsed = _parse_yaml_block(fm_text)

        src = parsed["sources"][0]
        for field in ("source_type", "source_ref", "retrieved_at", "mapper_version"):
            assert field in src, f"canonical field '{field}' required in concept sources, got: {list(src.keys())}"
        assert src["source_type"] == "signal_event"
        assert src["source_ref"] == "https://tldv.io/meeting/xyz"

    def test_retrieved_at_is_iso_timestamp_not_date_only(self, tmp_path):
        """retrieved_at must be a full ISO timestamp, not just YYYY-MM-DD."""
        import vault.ingest as ing
        ing.VAULT_ROOT = tmp_path / "vault"
        (tmp_path / "vault").mkdir(parents=True, exist_ok=True)

        decision = {
            "description": "Teste",
            "evidence": "url",
            "confidence": 0.8,
            "origin_id": "m1",
            "origin_url": "url",
            "collected_at": "2026-04-07T13:00:00+00:00",
        }
        path = ing.upsert_decision(decision)
        fm_text = path.read_text(encoding="utf-8")
        parsed = _parse_yaml_block(fm_text)

        src = parsed["sources"][0]
        val = src["retrieved_at"]
        # Must be parseable as ISO datetime
        try:
            datetime.fromisoformat(val)
        except ValueError:
            pytest.fail(f"retrieved_at '{val}' is not a valid ISO datetime")

    def test_domain_lint_passes_for_fresh_ingest_output(self, tmp_path):
        """Domain lint should report zero source schema errors for new ingest output."""
        import vault.ingest as ing
        from vault.quality.domain_lint import run_domain_lint, validate_vault_file

        vault_root = tmp_path / "vault"
        ing.VAULT_ROOT = vault_root
        vault_root.mkdir(parents=True, exist_ok=True)
        (vault_root / "decisions").mkdir(parents=True, exist_ok=True)
        (vault_root / "concepts").mkdir(parents=True, exist_ok=True)

        decision = {
            "description": "Usar entidade como base",
            "evidence": "https://tldv.io/meeting/abc",
            "confidence": 0.8,
            "origin_id": "fresh-dec-001",
            "origin_url": "https://tldv.io/meeting/abc",
            "collected_at": "2026-04-10T12:00:00+00:00",
        }
        path = ing.upsert_decision(decision)

        errors = validate_vault_file(path)
        source_errors = [e for e in errors if "source" in e]
        assert source_errors == [], f"domain lint found source schema errors: {source_errors}"
