"""Tests for vault lint scanner."""
import json
import pytest
from pathlib import Path
from vault.ingest.vault_lint_scanner import run_lint_scans, LintReport


def _write_entity(vault: Path, path: str, frontmatter: dict, body: str = ""):
    """Helper to create a vault entity file with YAML frontmatter."""
    f = vault / path
    f.parent.mkdir(parents=True, exist_ok=True)
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            fm_lines.append(f"{k}:")
            for item in v:
                fm_lines.append(f"  - {item}")
        elif isinstance(v, dict):
            fm_lines.append(f"{k}:")
            for sk, sv in v.items():
                fm_lines.append(f"  {sk}: {sv}")
        else:
            fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    fm_lines.append(body)
    f.write_text("\n".join(fm_lines))


class TestLintScanner:
    def test_find_orphans(self, tmp_path):
        vault = tmp_path / "vault"
        entities = vault / "entities"
        # Create entity NOT in index
        _write_entity(vault, "entities/meeting-orphan.md", {"id_canonical": "meeting-orphan"})
        result = run_lint_scans(vault)
        assert len(result["orphans"]) > 0

    def test_find_stale(self, tmp_path):
        vault = tmp_path / "vault"
        # Entity with old last_seen_at
        _write_entity(vault, "entities/meeting-stale.md", {
            "id_canonical": "meeting-stale",
            "last_seen_at": "2025-01-01T00:00:00Z",
        })
        result = run_lint_scans(vault)
        assert len(result["stale"]) > 0

    def test_find_gaps(self, tmp_path):
        vault = tmp_path / "vault"
        # Entity mentioning a concept that doesn't have its own page
        _write_entity(vault, "entities/meeting-1.md", {
            "id_canonical": "meeting-1",
            "concepts": ["missing-concept"],
        })
        result = run_lint_scans(vault)
        assert len(result["gaps"]) > 0

    def test_find_contradictions(self, tmp_path):
        vault = tmp_path / "vault"
        # Two entities with same id_canonical but different data
        _write_entity(vault, "entities/person-a-v1.md", {
            "id_canonical": "person-abc",
            "confidence": "high",
        })
        _write_entity(vault, "entities/person-a-v2.md", {
            "id_canonical": "person-abc",
            "confidence": "low",
        })
        result = run_lint_scans(vault)
        assert len(result["contradictions"]) > 0

    def test_empty_vault_no_crash(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir(parents=True)
        result = run_lint_scans(vault)
        assert result["orphans"] == []
        assert result["stale"] == []
        assert result["gaps"] == []
        assert result["contradictions"] == []
        assert result["metrics"]["total_entities"] == 0

    def test_metrics_populated(self, tmp_path):
        vault = tmp_path / "vault"
        _write_entity(vault, "entities/meeting-1.md", {"id_canonical": "meeting-1"})
        _write_entity(vault, "concepts/bat.md", {"id_canonical": "bat"})
        result = run_lint_scans(vault)
        assert result["metrics"]["total_entities"] >= 1
        assert "total_concepts" in result["metrics"]
