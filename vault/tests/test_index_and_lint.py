"""Tests for Task 12 (index PRs/cards) and Task 13 (lint crosslink relationships)."""
import json
import pytest
from pathlib import Path

from vault.ingest.index_manager import rebuild_index
from vault.ingest.vault_lint_scanner import _count_relationships, run_lint_scans


class TestRebuildIndexIncludesPRsAndCards:

    def _make_pr_file(self, vault_root: Path, name: str, repo: str = "living/test", project: str = "BAT", author: str = "Lincoln") -> Path:
        prs_dir = vault_root / "entities" / "prs"
        prs_dir.mkdir(parents=True, exist_ok=True)
        p = prs_dir / f"{name}.md"
        p.write_text(f"---\nrepo: {repo}\nproject: {project}\nauthor: {author}\n---\n# {name}\n", encoding="utf-8")
        return p

    def _make_card_file(self, vault_root: Path, name: str, project: str = "BAT") -> Path:
        cards_dir = vault_root / "entities" / "cards"
        cards_dir.mkdir(parents=True, exist_ok=True)
        p = cards_dir / f"{name}.md"
        p.write_text(f"---\nproject: {project}\n---\n# {name}\n", encoding="utf-8")
        return p

    def test_prs_section_appears_in_index(self, tmp_path):
        self._make_pr_file(tmp_path, "pr-123")
        self._make_pr_file(tmp_path, "pr-456")
        rebuild_index(tmp_path)
        text = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert "## 🔀 PRs (2)" in text
        assert "[[pr-123]]" in text
        assert "[[pr-456]]" in text

    def test_prs_table_includes_repo_project_author(self, tmp_path):
        self._make_pr_file(tmp_path, "pr-999", repo="living/bat", project="ConectaBot", author="Victor")
        rebuild_index(tmp_path)
        text = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert "living/bat" in text
        assert "ConectaBot" in text
        assert "Victor" in text

    def test_cards_section_appears_in_index(self, tmp_path):
        self._make_card_file(tmp_path, "card-1")
        rebuild_index(tmp_path)
        text = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert "## 📋 Cards (1)" in text
        assert "[[card-1]]" in text

    def test_no_prs_no_cards_sections_absent(self, tmp_path):
        (tmp_path / "entities" / "persons").mkdir(parents=True)
        rebuild_index(tmp_path)
        text = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert "## PRs" not in text
        assert "## Cards" not in text

    def test_prs_and_cards_counts_in_stats(self, tmp_path):
        self._make_pr_file(tmp_path, "pr-1")
        self._make_card_file(tmp_path, "card-1")
        self._make_card_file(tmp_path, "card-2")
        rebuild_index(tmp_path)
        text = (tmp_path / "index.md").read_text(encoding="utf-8")
        assert "| PRs | 1 |" in text
        assert "| Cards | 2 |" in text


class TestCountRelationshipsCrosslink:

    def _make_rel(self, vault_root: Path, name: str, edges: list) -> Path:
        rel_dir = vault_root / "relationships"
        rel_dir.mkdir(parents=True, exist_ok=True)
        p = rel_dir / name
        p.write_text(json.dumps({"edges": edges}), encoding="utf-8")
        return p

    def test_counts_person_meeting(self, tmp_path):
        self._make_rel(tmp_path, "person-meeting.json", [{"a": 1}, {"b": 2}])
        total, breakdown = _count_relationships(tmp_path)
        assert total == 2
        assert breakdown == {}

    def test_counts_crosslink_relationships(self, tmp_path):
        self._make_rel(tmp_path, "card-person.json", [{"x": 1}])
        self._make_rel(tmp_path, "card-project.json", [{"y": 1}, {"y": 2}])
        self._make_rel(tmp_path, "pr-person.json", [{"z": 1}])
        self._make_rel(tmp_path, "pr-project.json", [{"w": 1}])
        total, breakdown = _count_relationships(tmp_path)
        assert total == 5
        assert breakdown == {"card-person": 1, "card-project": 2, "pr-person": 1, "pr-project": 1}

    def test_mixed_relationships(self, tmp_path):
        self._make_rel(tmp_path, "person-meeting.json", [{"a": 1}])
        self._make_rel(tmp_path, "card-person.json", [{"b": 1}, {"b": 2}])
        total, breakdown = _count_relationships(tmp_path)
        assert total == 3
        assert breakdown == {"card-person": 2}

    def test_lint_report_includes_crosslink_breakdown(self, tmp_path):
        self._make_rel(tmp_path, "card-person.json", [{"x": 1}])
        self._make_rel(tmp_path, "pr-project.json", [{"y": 1}, {"y": 2}])
        report = run_lint_scans(tmp_path)
        metrics = report["metrics"]
        assert metrics["total_relationships"] == 3
        assert metrics.get("crosslink_edges", {}).get("card-person") == 1
        assert metrics.get("crosslink_edges", {}).get("pr-project") == 2
