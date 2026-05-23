"""Tests for vault/insights/honcho_query.py"""
import pytest
from unittest.mock import patch, Mock


class TestHonchoQuery:
    def test_honcho_fast_path_returns_lessons(self):
        """When Honcho returns results, they are returned."""
        mock_response = {
            "conclusions": [
                {"text": "PR #24 — Enriched Claims Rollout", "id": "c1", "score": 0.95},
                {"text": "PR #23 — Self-Healing Apply V2", "id": "c2", "score": 0.88},
            ]
        }
        with patch("vault.insights.honcho_query.honcho_health_check", return_value=True):
            with patch("httpx.post", return_value=Mock(json=lambda: mock_response, status_code=200)):
                from vault.insights.honcho_query import honcho_query
                results = honcho_query("enriched claims quality guardrail", topK=2)
                assert len(results) == 2
                assert results[0]["text"] == "PR #24 — Enriched Claims Rollout"

    def test_disk_fallback_returns_results(self, monkeypatch, tmp_path):
        """When Honcho is unreachable, falls back to disk search."""
        # Create a fake lessons dir with one lesson file
        lesson_content = "# PR #24 — Enriched Claims Rollout\n\nSome content about quality guardrail."
        lesson_file = tmp_path / "2026-04-21-pr-24-enriched-claims-rollout-26ca99.md"
        lesson_file.write_text(lesson_content)

        with patch("vault.insights.honcho_query.honcho_health_check", return_value=False):
            with patch("vault.insights.honcho_query.LESSONS_DIR", tmp_path):
                from vault.insights.honcho_query import disk_search
                results = disk_search("quality guardrail", topK=5)
                assert len(results) >= 1
                assert "quality guardrail" in results[0]["text"].lower() or \
                       "quality guardrail" in results[0].get("source", "").lower()

    def test_disk_search_skips_template(self, monkeypatch, tmp_path):
        """TEMPLATE.md is never included in results."""
        (tmp_path / "TEMPLATE.md").write_text("# Template content")
        (tmp_path / "2026-04-21-real-lesson-abc123.md").write_text("# Real Lesson\nContent.")

        with patch("vault.insights.honcho_query.LESSONS_DIR", tmp_path):
            from vault.insights.honcho_query import disk_search
            results = disk_search("content", topK=5)
            filenames = [r["source"] for r in results]
            assert not any("TEMPLATE" in f for f in filenames)
