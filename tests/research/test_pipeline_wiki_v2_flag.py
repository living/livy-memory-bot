"""Tests for WIKI_V2_ENABLED feature flag gating in ResearchPipeline.

RED phase: write failing tests first.
GREEN phase: minimal code to pass.

Coverage:
- WIKI_V2_ENABLED=true → pipeline.wiki_v2_active = True
- WIKI_V2_ENABLED=false/unset → pipeline.wiki_v2_active = False
- Audit log records wiki_v2_active flag state at run start
- WIKI_V2_ENABLED=true → github pipeline writes claims (not raw markdown) to wiki v2 store
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
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


# ---------------------------------------------------------------------------
# Wiki v2 production behavior — claims fusion + blob persistence
# When WIKI_V2_ENABLED=true the pipeline routes events through FusionEngine
# instead of writing raw markdown hypothesis via _apply().
# ---------------------------------------------------------------------------

class TestWikiV2ProductionBehavior:
    """RED phase: write failing tests that describe the desired v2 behavior."""

    def test_wiki_v2_writes_claims_to_v2_store_not_raw_markdown(
        self, tmp_state_file, tmp_pipeline_dir, monkeypatch
    ):
        """When wiki_v2_active=True, github pipeline writes fused claims to wiki v2 store.

        The pipeline should:
        1. Build claims from the rich github event (via pr_to_claims)
        2. Call fuse() with existing claims from state
        3. Persist the fused claim to state/identity-graph/state.json
        4. Write a wiki v2 blob to memory/vault/claims/<claim_id>.md
        5. NOT write the raw markdown hypothesis via _apply()
        """
        monkeypatch.setenv("WIKI_V2_ENABLED", "true")

        from vault.research.pipeline import ResearchPipeline
        from vault.research.state_store import load_state

        wiki_root = tmp_pipeline_dir.parent.parent / "memory" / "vault"
        wiki_root.mkdir(parents=True, exist_ok=True)

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            wiki_root=wiki_root,
        )

        rich_event = {
            "id": "gh-ev-1",
            "pr_number": 42,
            "repo": "living/livy-memory-bot",
            "type": "pr_merged",
            "event_at": datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
            "body": "Closes #99",
            "merged": True,
            "merged_at": datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
            "reviews": [],
            "labels": [{"name": "enhancement", "color": "aaee00"}],
            "milestone": {"title": "v1.0", "number": 3},
        }

        with patch("vault.research.pipeline.GitHubClient") as mock_gh, \
             patch("vault.research.pipeline.GitHubRichClient") as mock_rich:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = [rich_event]
            mock_client.fetch_pr.return_value = {}
            mock_gh.return_value = mock_client

            mock_rich_client = MagicMock()
            mock_rich_client.normalize_rich_event.return_value = rich_event
            mock_rich_client.fetch_rich_pr.return_value = {
                "number": 42,
                "title": "feat: wiki v2",
                "body": "Closes #99",
                "merged": True,
                "merged_at": datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
                "created_at": datetime(2026, 4, 19, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
                "base": {"repo": {"full_name": "living/livy-memory-bot"}},
                "html_url": "https://github.com/living/livy-memory-bot/pull/42",
                "user": {"login": "alice"},
                "state": "closed",
                "labels": [{"name": "enhancement", "color": "aaee00"}],
                "milestone": {"title": "v1.0", "number": 3},
                "reviews": [],
            }
            mock_rich_client.fetch_reviews.return_value = []
            mock_rich.return_value = mock_rich_client

            result = pipeline.run()

        # Should be marked success
        assert result["status"] == "success"
        assert result["events_processed"] == 1

        # State should contain at least one fused claim
        state = load_state(tmp_state_file)
        assert "claims" in state, "wiki v2 state should have 'claims' key"
        claims = state["claims"]
        assert len(claims) > 0, "at least one claim should be persisted to state"

        # First claim should be github source with canonical pull_request entity
        first = claims[0]
        assert first["source"] == "github"
        assert first["entity_type"] == "pull_request"
        assert first["claim_id"] is not None
        assert first["confidence"] > 0.0

        # Wiki v2 blob should exist for the claim
        claim_id = first["claim_id"]
        blob_path = wiki_root / "claims" / f"{claim_id}.md"
        assert blob_path.exists(), f"wiki v2 blob should exist at {blob_path}"
        blob_content = blob_path.read_text()
        assert "github" in blob_content.lower() or "PR" in blob_content

        # Raw markdown hypothesis should NOT be written to old research dir
        old_path = tmp_pipeline_dir / "github-pr_merged-gh-ev-1.md"
        assert not old_path.exists(), "raw markdown should not be written when wiki v2 is active"

    def test_wiki_v2_false_uses_old_markdown_path(self, tmp_state_file, tmp_pipeline_dir, monkeypatch):
        """When wiki_v2_active=False (flag unset), github pipeline uses old _apply() path."""
        monkeypatch.delenv("WIKI_V2_ENABLED", raising=False)

        from vault.research.pipeline import ResearchPipeline
        from vault.research.state_store import load_state

        wiki_root = tmp_pipeline_dir.parent.parent / "memory" / "vault"
        wiki_root.mkdir(parents=True, exist_ok=True)

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            wiki_root=wiki_root,
            allowed_paths=[str(wiki_root)],
        )

        rich_event = {
            "id": "gh-ev-2",
            "pr_number": 43,
            "repo": "living/livy-memory-bot",
            "type": "pr_merged",
            "event_at": datetime(2026, 4, 19, 13, 0, 0, tzinfo=timezone.utc).isoformat(),
            "body": "Fixes #100",
            "merged": True,
            "merged_at": datetime(2026, 4, 19, 13, 0, 0, tzinfo=timezone.utc).isoformat(),
            "reviews": [],
            "labels": [],
        }

        with patch("vault.research.pipeline.GitHubClient") as mock_gh, \
             patch("vault.research.pipeline.GitHubRichClient") as mock_rich:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = [rich_event]
            mock_client.fetch_pr.return_value = {}
            mock_gh.return_value = mock_client

            mock_rich_client = MagicMock()
            mock_rich_client.normalize_rich_event.return_value = rich_event
            mock_rich.return_value = mock_rich_client

            result = pipeline.run()

        # State should NOT have 'claims' key (old path doesn't write wiki v2 state)
        state = load_state(tmp_state_file)
        assert "claims" not in state or len(state.get("claims", [])) == 0, \
            "old path should not write claims to state"

        # Audit should record wiki_v2_active=False
        audit_log = tmp_pipeline_dir / "audit.log"
        entries = json.loads(audit_log.read_text())
        run_started = next((e for e in entries if e.get("action") == "run_started"), None)
        assert run_started is not None
        assert run_started["data"]["wiki_v2_active"] is False

    def test_wiki_v2_fusion_supersedes_older_claims(self, tmp_state_file, tmp_pipeline_dir, monkeypatch):
        """Newer claim should supersede older claim for same entity_id."""
        monkeypatch.setenv("WIKI_V2_ENABLED", "true")

        from vault.research.pipeline import ResearchPipeline
        from vault.research.state_store import load_state

        wiki_root = tmp_pipeline_dir.parent.parent / "memory" / "vault"
        wiki_root.mkdir(parents=True, exist_ok=True)

        # Pre-seed state with an older claim for the same entity (repo#43)
        old_ts = datetime(2026, 4, 19, 10, 0, 0, tzinfo=timezone.utc).isoformat()
        old_claim = {
            "claim_id": "old-claim-id",
            "entity_type": "github_pr",
            "entity_id": "living/livy-memory-bot#43",
            "topic_id": None,
            "claim_type": "status",
            "text": "PR #43 older status",
            "source": "github",
            "source_ref": {"source_id": "43", "url": "https://github.com/living/livy-memory-bot/pull/43"},
            "evidence_ids": ["ev-old"],
            "author": "bob",
            "event_timestamp": old_ts,
            "ingested_at": old_ts,
            "confidence": 0.5,
            "privacy_level": "internal",
            "superseded_by": None,
            "supersession_reason": None,
            "supersession_version": None,
            "audit_trail": {"model_used": "test", "parser_version": "v1", "trace_id": "tr-old"},
        }
        existing_state = {
            "processed_event_keys": {"github": [], "tldv": [], "trello": []},
            "processed_content_keys": {"github": [], "tldv": [], "trello": []},
            "last_seen_at": {"github": None, "tldv": None, "trello": None},
            "pending_conflicts": [],
            "version": 1,
            "claims": [old_claim],
        }
        tmp_state_file.write_text(json.dumps(existing_state))

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            wiki_root=wiki_root,
        )

        rich_event = {
            "id": "gh-ev-3",
            "pr_number": 43,
            "repo": "living/livy-memory-bot",
            "type": "pr_merged",
            "event_at": datetime(2026, 4, 19, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "body": "Closes #43",
            "merged": True,
            "merged_at": datetime(2026, 4, 19, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
            "reviews": [],
            "labels": [],
        }

        with patch("vault.research.pipeline.GitHubClient") as mock_gh, \
             patch("vault.research.pipeline.GitHubRichClient") as mock_rich:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = [rich_event]
            mock_client.fetch_pr.return_value = {}
            mock_gh.return_value = mock_client

            mock_rich_client = MagicMock()
            mock_rich_client.normalize_rich_event.return_value = rich_event
            mock_rich_client.fetch_rich_pr.return_value = {
                "number": 43,
                "title": "PR #43 newer",
                "body": "Closes #43",
                "merged": True,
                "merged_at": datetime(2026, 4, 19, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
                "created_at": datetime(2026, 4, 19, 11, 0, 0, tzinfo=timezone.utc).isoformat(),
                "base": {"repo": {"full_name": "living/livy-memory-bot"}},
                "html_url": "https://github.com/living/livy-memory-bot/pull/43",
                "user": {"login": "alice"},
                "state": "closed",
                "labels": [],
                "milestone": None,
                "reviews": [],
            }
            mock_rich_client.fetch_reviews.return_value = []
            mock_rich.return_value = mock_rich_client

            result = pipeline.run()

        assert result["events_processed"] == 1
        state = load_state(tmp_state_file)
        claims = state.get("claims", [])

        # Should have 3 claims total: old (superseded) + 2 new (status + linkage)
        assert len(claims) == 3

        # Old claim should be marked as superseded
        old = next(c for c in claims if c["claim_id"] == "old-claim-id")
        assert old["superseded_by"] is not None, "old claim should be marked superseded_by"
        assert old["supersession_reason"] is not None

        # New claims should have positive confidence
        new_claims = [c for c in claims if c["claim_id"] != "old-claim-id"]
        assert len(new_claims) == 2
        for new in new_claims:
            assert new["confidence"] > 0.0
