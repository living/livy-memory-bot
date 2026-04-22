"""Tests for wiki v2 production behavior on TLDV source.

RED phase: write failing tests first.
GREEN phase: minimal code to pass.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
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
                "processed_content_keys": {"github": [], "tldv": [], "trello": []},
                "last_seen_at": {"github": None, "tldv": None, "trello": None},
                "pending_conflicts": [],
                "version": 1,
            }
        )
    )
    return p


def _make_tldv_event(meeting_id: str, event_id: str = "ev-1") -> dict:
    return {
        "id": event_id,
        "source": "tldv",
        "type": "meeting_updated",
        "event_type": "tldv:meeting",
        "meeting_id": meeting_id,
        "name": f"Daily {meeting_id}",
        "event_at": datetime(2026, 4, 19, 14, 30, 0, tzinfo=timezone.utc).isoformat(),
        "updated_at": datetime(2026, 4, 19, 14, 30, 0, tzinfo=timezone.utc).isoformat(),
        "created_at": datetime(2026, 4, 19, 13, 0, 0, tzinfo=timezone.utc).isoformat(),
    }


class TestTldvWikiV2Production:
    """RED: failing tests that define desired wiki v2 behavior for TLDV."""

    def test_wiki_v2_writes_tldv_claims_to_state_not_raw_markdown(
        self, tmp_state_file, tmp_pipeline_dir, monkeypatch
    ):
        monkeypatch.setenv("WIKI_V2_ENABLED", "true")

        from vault.research.pipeline import ResearchPipeline
        from vault.research.state_store import load_state

        wiki_root = tmp_pipeline_dir.parent.parent / "memory" / "vault"
        wiki_root.mkdir(parents=True, exist_ok=True)

        pipeline = ResearchPipeline(
            source="tldv",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            wiki_root=wiki_root,
        )

        event = _make_tldv_event("mtg-123", "tldv-ev-1")
        meeting_payload = {
            "meeting_id": "mtg-123",
            "id": "mtg-123",
            "name": "Daily Engenharia",
            "summary": "Discussão de deploy e incidentes",
            "created_at": datetime(2026, 4, 19, 13, 0, 0, tzinfo=timezone.utc).isoformat(),
            "updated_at": datetime(2026, 4, 19, 14, 30, 0, tzinfo=timezone.utc).isoformat(),
            "event_at": datetime(2026, 4, 19, 14, 30, 0, tzinfo=timezone.utc).isoformat(),
        }

        with patch("vault.research.pipeline.TLDVClient") as mock_tldv:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = [event]
            mock_client.fetch_meeting.return_value = meeting_payload
            mock_tldv.return_value = mock_client

            result = pipeline.run()

        assert result["status"] == "success"
        assert result["events_processed"] == 1

        state = load_state(tmp_state_file)
        assert "claims" in state, "wiki v2 state should have 'claims' key"
        claims = state["claims"]
        assert len(claims) > 0, "at least one tldv claim should be persisted"

        for c in claims:
            assert c["source"] == "tldv", f"expected source=tldv, got {c['source']}"

        # At least one meeting claim
        meeting_claims = [c for c in claims if c["entity_id"] == "mtg-123"]
        assert len(meeting_claims) > 0

        first = claims[0]
        blob_path = wiki_root / "claims" / f"{first['claim_id']}.md"
        assert blob_path.exists()

    def test_wiki_v2_false_tldv_uses_old_markdown_path(
        self, tmp_state_file, tmp_pipeline_dir, monkeypatch
    ):
        monkeypatch.delenv("WIKI_V2_ENABLED", raising=False)

        from vault.research.pipeline import ResearchPipeline
        from vault.research.state_store import load_state

        wiki_root = tmp_pipeline_dir.parent.parent / "memory" / "vault"
        wiki_root.mkdir(parents=True, exist_ok=True)

        pipeline = ResearchPipeline(
            source="tldv",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            wiki_root=wiki_root,
            allowed_paths=[str(wiki_root)],
        )

        event = _make_tldv_event("mtg-legacy", "tldv-ev-legacy")

        with patch("vault.research.pipeline.TLDVClient") as mock_tldv:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = [event]
            mock_client.fetch_meeting.return_value = {
                "meeting_id": "mtg-legacy",
                "name": "Daily legado",
                "summary": "fluxo antigo",
                "event_at": datetime(2026, 4, 19, 14, 30, 0, tzinfo=timezone.utc).isoformat(),
            }
            mock_tldv.return_value = mock_client

            result = pipeline.run()

        state = load_state(tmp_state_file)
        assert "claims" not in state or len(state.get("claims", [])) == 0

    def test_wiki_v2_tldv_fusion_supersedes_older_meeting_claims(
        self, tmp_state_file, tmp_pipeline_dir, monkeypatch
    ):
        monkeypatch.setenv("WIKI_V2_ENABLED", "true")

        from vault.research.pipeline import ResearchPipeline
        from vault.research.state_store import load_state

        wiki_root = tmp_pipeline_dir.parent.parent / "memory" / "vault"
        wiki_root.mkdir(parents=True, exist_ok=True)

        old_ts = datetime(2026, 4, 19, 9, 0, 0, tzinfo=timezone.utc).isoformat()
        old_claim = {
            "claim_id": "old-tldv-claim",
            "entity_type": "meeting",
            "entity_id": "mtg-old",
            "topic_id": None,
            "claim_type": "status",
            "text": "Resumo antigo",
            "source": "tldv",
            "source_ref": {"source_id": "mtg-old", "url": None},
            "evidence_ids": ["ev-old"],
            "author": "system",
            "event_timestamp": old_ts,
            "ingested_at": old_ts,
            "confidence": 0.4,
            "privacy_level": "internal",
            "superseded_by": None,
            "supersession_reason": None,
            "supersession_version": None,
            "audit_trail": {"model_used": "test", "parser_version": "v1", "trace_id": "tr-old"},
        }
        state = {
            "processed_event_keys": {"github": [], "tldv": [], "trello": []},
            "processed_content_keys": {"github": [], "tldv": [], "trello": []},
            "last_seen_at": {"github": None, "tldv": None, "trello": None},
            "pending_conflicts": [],
            "version": 1,
            "claims": [old_claim],
        }
        tmp_state_file.write_text(json.dumps(state))

        pipeline = ResearchPipeline(
            source="tldv",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            wiki_root=wiki_root,
        )

        event = _make_tldv_event("mtg-old", "tldv-ev-new")
        meeting_payload = {
            "meeting_id": "mtg-old",
            "id": "mtg-old",
            "name": "Daily Atualizada",
            "summary": "Novo resumo com decisões",
            "event_at": datetime(2026, 4, 19, 16, 0, 0, tzinfo=timezone.utc).isoformat(),
            "updated_at": datetime(2026, 4, 19, 16, 0, 0, tzinfo=timezone.utc).isoformat(),
            "created_at": datetime(2026, 4, 19, 13, 0, 0, tzinfo=timezone.utc).isoformat(),
        }

        with patch("vault.research.pipeline.TLDVClient") as mock_tldv:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = [event]
            mock_client.fetch_meeting.return_value = meeting_payload
            mock_tldv.return_value = mock_client

            result = pipeline.run()

        assert result["events_processed"] == 1
        state2 = load_state(tmp_state_file)
        claims = state2.get("claims", [])

        old = next((c for c in claims if c["claim_id"] == "old-tldv-claim"), None)
        assert old is not None
        assert old["superseded_by"] is not None, "old meeting claim should be superseded"


# =============================================================================
# NEW TESTS — decision + linkage extraction for TLDV wiki v2 pipeline
# =============================================================================

class TestTldvDecisionExtraction:
    """RED failing tests → GREEN minimal fix to call tldv_to_claims()."""

    def test_wiki_v2_tldv_generates_decision_claims_from_summaries_decisions(
        self, tmp_state_file, tmp_pipeline_dir, monkeypatch
    ):
        """When a meeting has summaries[].decisions, pipeline must generate decision claims."""
        monkeypatch.setenv("WIKI_V2_ENABLED", "true")

        from vault.research.pipeline import ResearchPipeline
        from vault.research.state_store import load_state

        wiki_root = tmp_pipeline_dir.parent.parent / "memory" / "vault"
        wiki_root.mkdir(parents=True, exist_ok=True)

        pipeline = ResearchPipeline(
            source="tldv",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            wiki_root=wiki_root,
        )

        event = _make_tldv_event("mtg-decision-test", "tldv-ev-decision")
        meeting_payload = {
            "meeting_id": "mtg-decision-test",
            "id": "mtg-decision-test",
            "name": "Daily Engenharia",
            "summary": "Discussão de arquitetura",
            "created_at": datetime(2026, 4, 19, 13, 0, 0, tzinfo=timezone.utc).isoformat(),
            "updated_at": datetime(2026, 4, 19, 14, 30, 0, tzinfo=timezone.utc).isoformat(),
        }

        with patch("vault.research.pipeline.TLDVClient") as mock_tldv_cls:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = [event]
            mock_client.fetch_meeting.return_value = meeting_payload
            mock_client.fetch_summaries.return_value = [
                {
                    "meeting_id": "mtg-decision-test",
                    "decisions": ["Adotar Postgres como banco principal", "Migrar para API REST"],
                    "topics": ["Discussão sobre infraestrutura"],
                    "tags": ["engenharia"],
                }
            ]
            mock_client.fetch_enrichment_context.return_value = {
                "linked_prs": [],
                "linked_cards": [],
                "related_meetings": [],
            }
            mock_tldv_cls.return_value = mock_client

            result = pipeline.run()

        assert result["status"] == "success"
        state = load_state(tmp_state_file)
        claims = state.get("claims", [])
        decision_claims = [c for c in claims if c.get("claim_type") == "decision"]
        assert len(decision_claims) >= 1, (
            f"Expected >= 1 decision claim from summaries.decisions, got {len(decision_claims)}. "
            f"Claim types: {[c.get('claim_type') for c in claims]}"
        )
        assert any("Postgres" in c.get("text", "") for c in decision_claims)

    def test_wiki_v2_tldv_generates_linkage_claims_from_enrichment_context(
        self, tmp_state_file, tmp_pipeline_dir, monkeypatch
    ):
        """When a meeting has linked PRs/cards, pipeline must generate linkage claims."""
        monkeypatch.setenv("WIKI_V2_ENABLED", "true")

        from vault.research.pipeline import ResearchPipeline
        from vault.research.state_store import load_state

        wiki_root = tmp_pipeline_dir.parent.parent / "memory" / "vault"
        wiki_root.mkdir(parents=True, exist_ok=True)

        pipeline = ResearchPipeline(
            source="tldv",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            wiki_root=wiki_root,
        )

        event = _make_tldv_event("mtg-linkage-test", "tldv-ev-linkage")
        meeting_payload = {
            "meeting_id": "mtg-linkage-test",
            "id": "mtg-linkage-test",
            "name": "Planning",
            "summary": "Revisão de PRs",
            "created_at": datetime(2026, 4, 19, 13, 0, 0, tzinfo=timezone.utc).isoformat(),
            "updated_at": datetime(2026, 4, 19, 14, 30, 0, tzinfo=timezone.utc).isoformat(),
        }

        with patch("vault.research.pipeline.TLDVClient") as mock_tldv_cls:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = [event]
            mock_client.fetch_meeting.return_value = meeting_payload
            mock_client.fetch_summaries.return_value = [
                {"meeting_id": "mtg-linkage-test", "decisions": [], "topics": [], "tags": []}
            ]
            mock_client.fetch_enrichment_context.return_value = {
                "linked_prs": [{"pr_url": "https://github.com/living/livy-memory-bot/pull/24", "repo": "living/livy-memory-bot", "pr_number": "24"}],
                "linked_cards": [{"card_id": "abc123", "card_url": "https://trello.com/c/abc123"}],
                "related_meetings": [],
            }
            mock_tldv_cls.return_value = mock_client

            result = pipeline.run()

        assert result["status"] == "success"
        state = load_state(tmp_state_file)
        claims = state.get("claims", [])
        linkage_claims = [c for c in claims if c.get("claim_type") == "linkage"]
        assert len(linkage_claims) >= 1, (
            f"Expected >= 1 linkage claim from enrichment_context, got {len(linkage_claims)}. "
            f"Claim types: {[c.get('claim_type') for c in claims]}"
        )

    def test_wiki_v2_tldv_fuses_decision_with_existing_status_claim(
        self, tmp_state_file, tmp_pipeline_dir, monkeypatch
    ):
        """A meeting with decisions should produce both status AND decision claims (not replace)."""
        monkeypatch.setenv("WIKI_V2_ENABLED", "true")

        from vault.research.pipeline import ResearchPipeline
        from vault.research.state_store import load_state

        wiki_root = tmp_pipeline_dir.parent.parent / "memory" / "vault"
        wiki_root.mkdir(parents=True, exist_ok=True)

        pipeline = ResearchPipeline(
            source="tldv",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            wiki_root=wiki_root,
        )

        event = _make_tldv_event("mtg-both-claims", "tldv-ev-both")
        meeting_payload = {
            "meeting_id": "mtg-both-claims",
            "id": "mtg-both-claims",
            "name": "Weekly Engineering",
            "summary": "Reunião semanal",
            "created_at": datetime(2026, 4, 19, 13, 0, 0, tzinfo=timezone.utc).isoformat(),
            "updated_at": datetime(2026, 4, 19, 14, 30, 0, tzinfo=timezone.utc).isoformat(),
        }

        with patch("vault.research.pipeline.TLDVClient") as mock_tldv_cls:
            mock_client = MagicMock()
            mock_client.fetch_events_since.return_value = [event]
            mock_client.fetch_meeting.return_value = meeting_payload
            mock_client.fetch_summaries.return_value = [
                {"meeting_id": "mtg-both-claims", "decisions": ["Adotar novo pipeline"], "topics": [], "tags": []}
            ]
            mock_client.fetch_enrichment_context.return_value = {"linked_prs": [], "linked_cards": [], "related_meetings": []}
            mock_tldv_cls.return_value = mock_client

            result = pipeline.run()

        assert result["status"] == "success"
        state = load_state(tmp_state_file)
        claims = state.get("claims", [])
        types = [c.get("claim_type") for c in claims]
        assert "decision" in types, f"Expected decision in {types}"
        assert "status" in types, f"Expected status in {types}"
