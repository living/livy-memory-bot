"""Tests for wiki v2 production behavior on Trello source.

RED phase: write failing tests first.
GREEN phase: minimal code to pass.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tmp_pipeline_dir(tmp_path):
    d = tmp_path / ".research" / "trello"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def tmp_state_file(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(
        json.dumps(
            {
                "processed_event_keys": {"github": [], "tldv": [], "trello": []},
                "processed_content_keys": {"github": [], "tldv": [], "trello": []},
                "last_seen_at": {"github": None, "tldv": None, "trello": None},
                "pending_conflicts": [],
                "version": 1,
            }
        )
    )
    return p


def _make_trello_card_event(
    action_id: str,
    card_id: str,
    list_id: str,
    board_id: str = "board-1",
    event_type: str = "trello:card_updated",
    card_name: str = "Test Card",
    github_links: list[str] | None = None,
) -> dict:
    ev = {
        "source": "trello",
        "event_type": event_type,
        "action_id": action_id,
        "card_id": card_id,
        "list_id": list_id,
        "board_id": board_id,
        "card_name": card_name,
        "timestamp": datetime(2026, 4, 19, 14, 0, 0, tzinfo=timezone.utc).isoformat(),
        "raw": {"type": event_type.replace("trello:", "")},
    }
    if github_links:
        ev["github_links"] = github_links
    return ev


class TestTrelloWikiV2Production:
    """RED: failing tests that describe the desired v2 behavior for Trello."""

    def test_wiki_v2_writes_trello_claims_to_state_not_raw_markdown(
        self, tmp_state_file, tmp_pipeline_dir, monkeypatch
    ):
        """When wiki_v2_active=True and source=trello, pipeline writes fused claims to state."""
        monkeypatch.setenv("WIKI_V2_ENABLED", "true")

        from vault.research.pipeline import ResearchPipeline
        from vault.research.state_store import load_state

        wiki_root = tmp_pipeline_dir.parent.parent / "memory" / "vault"
        wiki_root.mkdir(parents=True, exist_ok=True)

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            wiki_root=wiki_root,
        )

        event = _make_trello_card_event(
            action_id="act-t1",
            card_id="card-abc",
            list_id="list-doing",
            event_type="trello:card_updated",
            card_name="Implementar feature X",
            github_links=["https://github.com/living/livy-memory-bot/pull/99"],
        )

        with patch("vault.research.pipeline.TrelloClient") as mock_trello:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = [event]
            mock_trello.return_value = mock_client

            result = pipeline.run()

        assert result["status"] == "success"
        assert result["events_processed"] == 1

        state = load_state(tmp_state_file)
        assert "claims" in state, "wiki v2 state should have 'claims' key"
        claims = state["claims"]
        assert len(claims) > 0, "at least one claim should be persisted"

        # Claims should be from Trello source
        for c in claims:
            assert c["source"] == "trello", f"expected source=trello, got {c['source']}"

        # At least one claim with card entity
        card_claims = [c for c in claims if c["entity_id"] == "card-abc"]
        assert len(card_claims) > 0, "expected at least one claim for card-abc"

        # Wiki v2 blob should exist
        first = claims[0]
        blob_path = wiki_root / "claims" / f"{first['claim_id']}.md"
        assert blob_path.exists(), f"wiki v2 blob should exist at {blob_path}"

    def test_wiki_v2_false_trello_uses_old_markdown_path(
        self, tmp_state_file, tmp_pipeline_dir, monkeypatch
    ):
        """When wiki_v2_active=False, trello pipeline uses old _apply() path."""
        monkeypatch.delenv("WIKI_V2_ENABLED", raising=False)

        from vault.research.pipeline import ResearchPipeline
        from vault.research.state_store import load_state

        wiki_root = tmp_pipeline_dir.parent.parent / "memory" / "vault"
        wiki_root.mkdir(parents=True, exist_ok=True)

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            wiki_root=wiki_root,
            allowed_paths=[str(wiki_root)],
        )

        event = _make_trello_card_event(
            action_id="act-t2",
            card_id="card-xyz",
            list_id="list-done",
        )

        with patch("vault.research.pipeline.TrelloClient") as mock_trello:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = [event]
            mock_trello.return_value = mock_client

            result = pipeline.run()

        # Old path should NOT write claims to state
        state = load_state(tmp_state_file)
        assert "claims" not in state or len(state.get("claims", [])) == 0

    def test_wiki_v2_trello_fusion_supersedes_older_card_claims(
        self, tmp_state_file, tmp_pipeline_dir, monkeypatch
    ):
        """Newer card status claim should supersede older claim for same entity_id."""
        monkeypatch.setenv("WIKI_V2_ENABLED", "true")

        from vault.research.pipeline import ResearchPipeline
        from vault.research.state_store import load_state

        wiki_root = tmp_pipeline_dir.parent.parent / "memory" / "vault"
        wiki_root.mkdir(parents=True, exist_ok=True)

        # Pre-seed with older claim
        old_ts = datetime(2026, 4, 19, 10, 0, 0, tzinfo=timezone.utc).isoformat()
        old_claim = {
            "claim_id": "old-trello-claim",
            "entity_type": "project",
            "entity_id": "card-old",
            "topic_id": None,
            "claim_type": "status",
            "text": "Card antigo estava no TODO",
            "source": "trello",
            "source_ref": {"source_id": "card-old", "url": "https://trello.com/c/card-old"},
            "evidence_ids": ["ev-old"],
            "author": "system",
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
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            wiki_root=wiki_root,
        )

        # Newer event for the same card (card-old)
        event = {
            "source": "trello",
            "event_type": "trello:card_updated",
            "action_id": "act-newer",
            "card_id": "card-old",
            "list_id": "list-done",
            "board_id": "board-1",
            "card_name": "Card atualizado",
            "timestamp": datetime(2026, 4, 19, 15, 0, 0, tzinfo=timezone.utc).isoformat(),
            "raw": {"type": "updateCard"},
        }

        with patch("vault.research.pipeline.TrelloClient") as mock_trello:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = [event]
            mock_trello.return_value = mock_client

            result = pipeline.run()

        assert result["events_processed"] == 1
        state = load_state(tmp_state_file)
        claims = state.get("claims", [])

        # Old claim should be marked superseded
        old = next((c for c in claims if c["claim_id"] == "old-trello-claim"), None)
        assert old is not None
        assert old["superseded_by"] is not None, "old claim should be superseded"
