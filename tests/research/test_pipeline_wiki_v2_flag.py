"""Tests for WIKI_V2_ENABLED feature flag gating in ResearchPipeline.

RED phase: write failing tests first.
GREEN phase: minimal code to pass.

Coverage:
- WIKI_V2_ENABLED=true → pipeline.wiki_v2_active = True
- WIKI_V2_ENABLED=false/unset → pipeline.wiki_v2_active = False
- Audit log records wiki_v2_active flag state at run start
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tmp_pipeline_dir(tmp_path):
    d = tmp_path / ".research" / "tldv"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def tmp_state_file(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(
        json.dumps(
            {
                "processed_event_keys": {"github": [], "tldv": [], "trello": []},
                "last_seen_at": {"github": None, "tldv": None, "trello": None},
                "version": 1,
            }
        )
    )
    return p


class TestWikiV2FlagGating:
    """Verify WIKI_V2_ENABLED gates pipeline behavior."""

    def test_wiki_v2_active_true_when_flag_set(self, tmp_state_file, tmp_pipeline_dir, monkeypatch):
        monkeypatch.setenv("WIKI_V2_ENABLED", "true")

        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="tldv",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )

        with patch("vault.research.pipeline.TLDVClient") as mock_tldv:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = []
            mock_tldv.return_value = mock_client
            pipeline.run()

        assert pipeline.wiki_v2_active is True

    def test_wiki_v2_active_false_when_flag_unset(self, tmp_state_file, tmp_pipeline_dir, monkeypatch):
        monkeypatch.delenv("WIKI_V2_ENABLED", raising=False)

        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="tldv",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )

        with patch("vault.research.pipeline.TLDVClient") as mock_tldv:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = []
            mock_tldv.return_value = mock_client
            pipeline.run()

        assert pipeline.wiki_v2_active is False

    def test_wiki_v2_active_false_when_flag_false(self, tmp_state_file, tmp_pipeline_dir, monkeypatch):
        monkeypatch.setenv("WIKI_V2_ENABLED", "false")

        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="tldv",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )

        with patch("vault.research.pipeline.TLDVClient") as mock_tldv:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = []
            mock_tldv.return_value = mock_client
            pipeline.run()

        assert pipeline.wiki_v2_active is False

    def test_audit_log_contains_wiki_v2_active_flag(self, tmp_state_file, tmp_pipeline_dir, monkeypatch):
        monkeypatch.setenv("WIKI_V2_ENABLED", "true")

        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="tldv",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )

        with patch("vault.research.pipeline.TLDVClient") as mock_tldv:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = []
            mock_tldv.return_value = mock_client
            pipeline.run()

        audit_log = tmp_pipeline_dir / "audit.log"
        assert audit_log.exists(), "audit.log should be created"
        entries = json.loads(audit_log.read_text())
        run_started = next((e for e in entries if e.get("action") == "run_started"), None)
        assert run_started is not None, "run_started audit entry not found"
        assert "wiki_v2_active" in run_started.get("data", {})
        assert run_started["data"]["wiki_v2_active"] is True
