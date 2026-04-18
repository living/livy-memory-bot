"""Tests for vault/research/pipeline.py — GitHub research pipeline.

RED phase: write failing tests first.
GREEN phase: implement minimal code to pass.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vault.research.state_store import load_state, save_state


@pytest.fixture
def tmp_pipeline_dir(tmp_path):
    d = tmp_path / ".research" / "github"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def tmp_state_file(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({
        "processed_event_keys": {"github": [], "tldv": []},
        "last_seen_at": {"github": None, "tldv": None},
        "version": 1,
    }))
    return p


def _make_github_event(event_id: str, pr_number: int, event_at: datetime, event_type: str = "pr_merged") -> dict:
    return {
        "id": event_id,
        "pr_number": pr_number,
        "type": event_type,
        "repo": "living/livy-memory-bot",
        "event_at": event_at.isoformat(),
    }


class TestGithubPipelineBasics:
    def test_event_key_for_github_event(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="github", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        ev = _make_github_event("gh-1", 42, datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc))
        assert pipeline._calculate_event_key(ev) == "github:pr_merged:gh-1"

    def test_duplicate_event_key_is_skipped(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        save_state({
            "processed_event_keys": {"github": [{"key": "github:pr_merged:gh-1", "event_at": "2026-04-18T11:00:00Z"}], "tldv": []},
            "last_seen_at": {"github": "2026-04-18T12:00:00Z", "tldv": None},
            "version": 1,
        }, tmp_state_file)

        pipeline = ResearchPipeline(source="github", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        ev = _make_github_event("gh-1", 42, datetime(2026, 4, 18, 11, 30, 0, tzinfo=timezone.utc))
        assert pipeline._is_duplicate(ev) is True

    def test_late_event_new_key_is_processed_even_if_older_than_last_seen(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        save_state({
            "processed_event_keys": {"github": [], "tldv": []},
            "last_seen_at": {"github": "2026-04-18T12:00:00Z", "tldv": None},
            "version": 1,
        }, tmp_state_file)

        pipeline = ResearchPipeline(source="github", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        ev = _make_github_event("gh-late-new", 43, datetime(2026, 4, 18, 11, 30, 0, tzinfo=timezone.utc))
        assert pipeline._is_duplicate(ev) is False


class TestGithubPipelineContextResolveApplyAudit:
    @patch("vault.research.pipeline.get_claude_mem_context")
    def test_build_context_uses_claude_mem_wiki_fs(self, mock_mem, tmp_state_file, tmp_pipeline_dir, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        mock_mem.return_value = {"recent": ["session1"]}
        wiki_root = tmp_path / "memory" / "vault"
        wiki_root.mkdir(parents=True)
        (wiki_root / "index.md").write_text("# Vault Index")

        pipeline = ResearchPipeline(source="github", state_path=tmp_state_file, research_dir=tmp_pipeline_dir, wiki_root=wiki_root)
        ctx = pipeline._build_context({"repo": "living/livy-memory-bot"})

        assert "claude_mem" in ctx
        assert "wiki" in ctx
        assert "fs" in ctx

    def test_entity_resolution_integration(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="github", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        out = pipeline._resolve_entities([
            {
                "source": "github",
                "identifier": "dev-alice",
                "email": "alice@example.com",
                "candidates": [
                    {
                        "source": "tldv",
                        "identifier": "alice-tldv",
                        "email": "alice@example.com",
                        "sources": ["tldv", "github"],
                        "event_at": "2026-04-18T10:00:00Z",
                    }
                ],
            }
        ])
        assert out[0]["confidence"] >= 0.60

    def test_validate_and_apply_flow(self, tmp_state_file, tmp_pipeline_dir, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        allowed = tmp_path / "memory" / "vault" / "entities"
        allowed.mkdir(parents=True)

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            allowed_paths=[str(allowed)],
        )

        hypothesis = {"action": "create_page", "path": str(allowed / "repo.md"), "content": "# Repo"}
        validation = pipeline._validate(hypothesis)
        assert validation["approved"] is True

        apply_result = pipeline._apply([hypothesis])
        assert apply_result["applied_count"] == 1

    def test_audit_logging(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="github", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        pipeline._log_audit("github_event_processed", {"event_key": "github:pr_merged:gh-9"})

        p = tmp_pipeline_dir / "audit.log"
        assert p.exists()
        rows = json.loads(p.read_text())
        assert any(r.get("action") == "github_event_processed" for r in rows)


class TestGithubSelfHealingReadonly:
    def test_self_healing_read_only_accumulates_evidence(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="github", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        pipeline._accumulate_self_healing_evidence({"candidate": "merge-person"})

        p = tmp_pipeline_dir / "self_healing_evidence.jsonl"
        assert p.exists()
        lines = [l for l in p.read_text().splitlines() if l.strip()]
        assert len(lines) == 1

    def test_self_healing_read_only_never_applies(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="github", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        pipeline.read_only_mode = True

        res = pipeline._apply_self_healing([{"action": "merge", "confidence": 0.99}])
        assert res["mode"] == "read_only"
        assert res["applied_count"] == 0


class TestGithubPipelineRun:
    @patch("vault.research.pipeline.GitHubClient")
    def test_full_run_executes_and_updates_state(self, mock_gh_client, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        mock_client = MagicMock()
        mock_client.fetch_events_since.return_value = [
            _make_github_event("gh-e2e-1", 10, datetime(2026, 4, 18, 13, 0, 0, tzinfo=timezone.utc))
        ]
        mock_client.fetch_pr.return_value = {
            "number": 10,
            "title": "feat: improve pipeline",
            "author": {"login": "alice", "email": "alice@example.com"},
            "merged_at": "2026-04-18T13:00:00Z",
        }
        mock_gh_client.return_value = mock_client

        pipeline = ResearchPipeline(source="github", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        result = pipeline.run()

        assert result["status"] in ("success", "partial")
        st = load_state(tmp_state_file)
        assert st["last_seen_at"]["github"] is not None
