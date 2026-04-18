"""Tests for Trello flow in ResearchPipeline.run().

RED phase: write failing tests first for the source="trello" branch.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vault.research.state_store import load_state, save_state


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
                "last_seen_at": {"github": None, "tldv": None, "trello": None},
                "version": 1,
            }
        )
    )
    return p


def _make_trello_event(
    event_type: str,
    action_id: str,
    card_id: str | None = None,
    list_id: str | None = None,
    target_list_id: str | None = None,
    member_id: str | None = None,
    board_id: str | None = None,
    timestamp: str = "2026-04-18T10:00:00.000Z",
) -> dict:
    """Build a normalized Trello event dict matching TrelloClient.normalize_action output."""
    ev = {
        "source": "trello",
        "event_type": event_type,
        "action_id": action_id,
        "timestamp": timestamp,
        "raw": {"type": event_type.replace("trello:", "")},
    }
    if card_id is not None:
        ev["card_id"] = card_id
    if list_id is not None:
        ev["list_id"] = list_id
    if target_list_id is not None:
        ev["target_list_id"] = target_list_id
    if member_id is not None:
        ev["member_id"] = member_id
    if board_id is not None:
        ev["board_id"] = board_id
    return ev


# ---------------------------------------------------------------------------
# Constructor / source validation
# ---------------------------------------------------------------------------


class TestTrelloPipelineConstructor:
    def test_trello_is_a_valid_source(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        assert pipeline.source == "trello"

    def test_unsupported_source_raises(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        with pytest.raises(ValueError, match="unsupported source"):
            ResearchPipeline(
                source="unknown",
                state_path=tmp_state_file,
                research_dir=tmp_pipeline_dir,
            )


# ---------------------------------------------------------------------------
# Event key calculation (uses build_trello_event_key)
# ---------------------------------------------------------------------------


class TestTrelloPipelineEventKey:
    def test_event_key_uses_action_id_for_card_created(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        ev = _make_trello_event("trello:card_created", action_id="action_abc123", card_id="card_x", list_id="list_y")
        # The pipeline uses build_trello_event_key internally
        key = pipeline._calculate_event_key(ev)
        assert key == "action_abc123"

    def test_event_key_for_list_moved_uses_target_list_when_present(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        ev = _make_trello_event(
            "trello:list_moved",
            action_id="",
            card_id="card_xyz",
            list_id="list_src",
            target_list_id="list_dst",
        )
        key = pipeline._calculate_event_key(ev)
        # Must include target_list_id in the key when present
        assert "list_dst" in key

    def test_duplicate_event_is_skipped(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        save_state(
            {
                "processed_event_keys": {
                    "github": [],
                    "tldv": [],
                    "trello": [{"key": "action_dup123", "event_at": "2026-04-18T09:00:00Z"}],
                },
                "last_seen_at": {"github": None, "tldv": None, "trello": "2026-04-18T10:00:00Z"},
                "version": 1,
            },
            tmp_state_file,
        )
        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        ev = _make_trello_event("trello:card_created", action_id="action_dup123")
        assert pipeline._is_duplicate(ev) is True


# ---------------------------------------------------------------------------
# Hypothesis / evidence path contracts per event type
# ---------------------------------------------------------------------------


class TestTrelloHypothesisContracts:
    """Each event type has a specific hypothesis contract."""

    def test_card_created_uses_card_entity_path(self, tmp_state_file, tmp_pipeline_dir, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        allowed = tmp_path / "memory" / "vault"
        allowed.mkdir(parents=True)

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            allowed_paths=[str(allowed)],
        )

        ev = _make_trello_event("trello:card_created", action_id="act_new", card_id="card_new")

        hypothesis = pipeline._build_trello_hypothesis(ev)
        assert hypothesis["action"] == "create_page"
        assert hypothesis["path"] == "memory/vault/entities/cards/card_new.md"
        assert "card_id: card_new" in hypothesis["content"]

    def test_card_updated_uses_upsert_entity_semantics(self, tmp_state_file, tmp_pipeline_dir, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        allowed = tmp_path / "memory" / "vault"
        allowed.mkdir(parents=True)

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            allowed_paths=[str(allowed)],
        )

        ev = _make_trello_event("trello:card_updated", action_id="act_upd", card_id="card_upd", list_id="list_doing")

        hypothesis = pipeline._build_trello_hypothesis(ev)
        assert hypothesis["entity_type"] == "card"
        assert hypothesis["action"] == "upsert_page"
        assert hypothesis["path"] == "memory/vault/entities/cards/card_upd.md"

    def test_list_moved_captures_old_and_new_list(self, tmp_state_file, tmp_pipeline_dir, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        allowed = tmp_path / "memory" / "vault"
        allowed.mkdir(parents=True)

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            allowed_paths=[str(allowed)],
        )

        ev = _make_trello_event(
            "trello:list_moved",
            action_id="act_move",
            card_id="card_mv",
            list_id="list_todo",
            target_list_id="list_done",
        )

        hypothesis = pipeline._build_trello_hypothesis(ev)
        content = hypothesis.get("content", "")
        # Must capture both old (source) list and target (destination) list
        assert "source_list_id: list_todo" in content
        assert "target_list_id: list_done" in content

    def test_member_added_is_identity_reinforcement_event(self, tmp_state_file, tmp_pipeline_dir, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        allowed = tmp_path / "memory" / "vault"
        allowed.mkdir(parents=True)

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            allowed_paths=[str(allowed)],
        )

        ev = _make_trello_event("trello:member_added", action_id="act_add_mem", member_id="member_jane")

        hypothesis = pipeline._build_trello_hypothesis(ev)
        assert hypothesis["entity_type"] == "identity_reinforcement"
        assert hypothesis["identities"][0]["identifier"] == "member_jane"

    def test_member_removed_is_soft_unlink_event(self, tmp_state_file, tmp_pipeline_dir, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        allowed = tmp_path / "memory" / "vault"
        allowed.mkdir(parents=True)

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            allowed_paths=[str(allowed)],
        )

        ev = _make_trello_event("trello:member_removed", action_id="act_rem_mem", member_id="member_john")

        hypothesis = pipeline._build_trello_hypothesis(ev)
        # member_removed should NOT create a new evidence page (soft unlink)
        assert hypothesis["action"] == "unlink"
        assert hypothesis["skip_apply"] is True


# ---------------------------------------------------------------------------
# Full run() integration
# ---------------------------------------------------------------------------


class TestTrelloPipelineRun:
    @patch("vault.research.pipeline.TrelloClient")
    def test_full_run_processes_trello_events(self, mock_trello_cls, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        mock_client = MagicMock()
        mock_client.fetch_events_since.return_value = [
            _make_trello_event(
                "trello:card_created",
                action_id="act_run1",
                card_id="card_run1",
                list_id="list_backlog",
                timestamp="2026-04-18T15:00:00.000Z",
            )
        ]
        mock_trello_cls.return_value = mock_client

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        result = pipeline.run()

        assert result["status"] == "success"
        assert result["events_processed"] == 1
        assert result["events_skipped"] == 0

        st = load_state(tmp_state_file)
        assert st["last_seen_at"]["trello"] is not None

    @patch("vault.research.pipeline.TrelloClient")
    def test_run_skips_duplicates(self, mock_trello_cls, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        save_state(
            {
                "processed_event_keys": {
                    "github": [],
                    "tldv": [],
                    "trello": [{"key": "act_dup", "event_at": "2026-04-18T14:00:00Z"}],
                },
                "last_seen_at": {"github": None, "tldv": None, "trello": "2026-04-18T14:00:00Z"},
                "version": 1,
            },
            tmp_state_file,
        )

        mock_client = MagicMock()
        mock_client.fetch_events_since.return_value = [
            _make_trello_event(
                "trello:card_created",
                action_id="act_dup",
                card_id="card_dup",
                list_id="list_todo",
                timestamp="2026-04-18T15:00:00.000Z",
            )
        ]
        mock_trello_cls.return_value = mock_client

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        result = pipeline.run()

        assert result["events_processed"] == 0
        assert result["events_skipped"] == 1

    @patch("vault.research.pipeline.TrelloClient")
    def test_run_rebuilds_trello_state_json(self, mock_trello_cls, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        mock_client = MagicMock()
        mock_client.fetch_events_since.return_value = [
            _make_trello_event(
                "trello:card_updated",
                action_id="act_state",
                card_id="card_state",
                list_id="list_doing",
                timestamp="2026-04-18T16:00:00.000Z",
            )
        ]
        mock_trello_cls.return_value = mock_client

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        pipeline.run()

        state_cache = tmp_pipeline_dir / "state.json"
        assert state_cache.exists()
        cached = json.loads(state_cache.read_text())
        assert cached["source"] == "trello"
        assert "processed_event_keys" in cached
        assert "last_seen_at" in cached

    @patch("vault.research.pipeline.TrelloClient")
    def test_multiple_events_of_different_types_all_processed(self, mock_trello_cls, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        mock_client = MagicMock()
        mock_client.fetch_events_since.return_value = [
            _make_trello_event("trello:card_created", action_id="act_c1", card_id="c1", list_id="l1"),
            _make_trello_event("trello:card_updated", action_id="act_c2", card_id="c2", list_id="l2"),
            _make_trello_event("trello:list_moved", action_id="act_lm1", card_id="c3", list_id="l_src", target_list_id="l_dst"),
            _make_trello_event("trello:member_added", action_id="act_ma1", member_id="m1"),
            _make_trello_event("trello:member_removed", action_id="act_mr1", member_id="m2"),
        ]
        mock_trello_cls.return_value = mock_client

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        result = pipeline.run()

        assert result["events_processed"] == 5
        assert result["events_skipped"] == 0

        st = load_state(tmp_state_file)
        assert len(st["processed_event_keys"]["trello"]) == 5

    @patch("vault.research.pipeline.TrelloClient")
    def test_run_logs_audit_entries(self, mock_trello_cls, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        mock_client = MagicMock()
        mock_client.fetch_events_since.return_value = [
            _make_trello_event("trello:card_created", action_id="act_audit1", card_id="c1", list_id="l1"),
        ]
        mock_trello_cls.return_value = mock_client

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        pipeline.run()

        audit = tmp_pipeline_dir / "audit.log"
        assert audit.exists()
        rows = json.loads(audit.read_text())
        assert any(r.get("action") == "event_processed" for r in rows)
        assert any(r.get("source") == "trello" for r in rows)


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


class TestTrelloStatePersistence:
    @patch("vault.research.pipeline.TrelloClient")
    def test_persists_event_key_after_processing(self, mock_trello_cls, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        mock_client = MagicMock()
        mock_client.fetch_events_since.return_value = [
            _make_trello_event("trello:card_created", action_id="act_persist1", card_id="c1", list_id="l1"),
        ]
        mock_trello_cls.return_value = mock_client

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        pipeline.run()

        st = load_state(tmp_state_file)
        keys = [e["key"] for e in st["processed_event_keys"].get("trello", [])]
        assert "act_persist1" in keys

    @patch("vault.research.pipeline.TrelloClient")
    def test_advance_last_seen_at_is_updated(self, mock_trello_cls, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        mock_client = MagicMock()
        mock_client.fetch_events_since.return_value = [
            _make_trello_event(
                "trello:card_created",
                action_id="act_ls1",
                card_id="c1",
                list_id="l1",
                timestamp="2026-04-18T17:00:00.000Z",
            ),
        ]
        mock_trello_cls.return_value = mock_client

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        pipeline.run()

        st = load_state(tmp_state_file)
        assert st["last_seen_at"]["trello"] is not None
        assert "2026-04-18" in st["last_seen_at"]["trello"]


# ---------------------------------------------------------------------------
# Identity resolution for Trello member events
# ---------------------------------------------------------------------------


class TestTrelloIdentityResolution:
    def test_member_added_resolves_identity(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        out = pipeline._resolve_entities(
            [
                {
                    "source": "trello",
                    "identifier": "member_jane",
                    "email": None,
                    "username": None,
                    "name": "Jane Doe",
                    "candidates": [],
                }
            ]
        )
        assert len(out) == 1
        assert "confidence" in out[0]
        assert "reason" in out[0]


class TestTrelloEventAtFieldResolution:
    """_event_at() must resolve both event_at and timestamp fields."""

    def test_event_at_prefers_explicit_event_at_field(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        ev = {"event_at": "2026-04-18T11:00:00.000Z", "timestamp": "2026-04-18T12:00:00.000Z"}
        result = pipeline._event_at(ev)
        assert result.isoformat().startswith("2026-04-18T11:00:00")

    def test_event_at_falls_back_to_timestamp_field(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        ev = {"timestamp": "2026-04-18T14:30:00.000Z"}
        result = pipeline._event_at(ev)
        assert result.isoformat().startswith("2026-04-18T14:30:00")

    def test_event_at_handles_malformed_timestamp(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        ev = {"timestamp": "not-a-timestamp", "event_at": "garbage"}
        result = pipeline._event_at(ev)
        # Must not raise — should fall back to now()
        assert result is not None
        assert result.tzinfo is not None


class TestTrelloLastSeenAtAdvances:
    """last_seen_at must advance from event timestamp, not from now()."""

    @patch("vault.research.pipeline.TrelloClient")
    def test_last_seen_at_advances_from_event_timestamp(self, mock_trello_cls, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        mock_client = MagicMock()
        mock_client.fetch_events_since.return_value = [
            _make_trello_event(
                "trello:card_created",
                action_id="act_ts1",
                card_id="c1",
                list_id="l1",
                timestamp="2026-04-18T09:00:00.000Z",
            ),
        ]
        mock_trello_cls.return_value = mock_client

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        pipeline.run()

        st = load_state(tmp_state_file)
        lsa = st["last_seen_at"]["trello"]
        assert lsa.startswith("2026-04-18T09:00:00")

    @patch("vault.research.pipeline.TrelloClient")
    def test_last_seen_at_advances_to_latest_event(self, mock_trello_cls, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        mock_client = MagicMock()
        mock_client.fetch_events_since.return_value = [
            _make_trello_event("trello:card_created", action_id="act_old", card_id="c_old", list_id="l1", timestamp="2026-04-18T08:00:00.000Z"),
            _make_trello_event("trello:card_updated", action_id="act_new", card_id="c_new", list_id="l2", timestamp="2026-04-18T10:00:00.000Z"),
        ]
        mock_trello_cls.return_value = mock_client

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        pipeline.run()

        st = load_state(tmp_state_file)
        lsa = st["last_seen_at"]["trello"]
        assert lsa.startswith("2026-04-18T10:00:00")


class TestTrelloUnknownEventType:
    """Unknown Trello event types must not crash the pipeline."""

    def test_unknown_event_type_returns_generic_hypothesis(self, tmp_state_file, tmp_pipeline_dir, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        allowed = tmp_path / "memory" / "vault"
        allowed.mkdir(parents=True)

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
            allowed_paths=[str(allowed)],
        )

        ev = _make_trello_event("trello:someNewAction", action_id="act_unknown")
        hypothesis = pipeline._build_trello_hypothesis(ev)

        # Must not raise — should return a generic create_page hypothesis
        assert hypothesis["action"] == "create_page"
        assert "path" in hypothesis
        assert "event_type: trello:someNewAction" in hypothesis["content"]


class TestGithubTldvPayloadEnrichment:
    """GitHub/TLDV must use source-specific enriched payload, not raw event."""

    @patch("vault.research.pipeline.GitHubClient")
    @patch("vault.research.pipeline.TrelloClient")
    def test_github_run_uses_fetch_pr_for_payload(
        self, mock_trello_cls, mock_github_cls, tmp_state_file, tmp_pipeline_dir
    ):
        from vault.research.pipeline import GitHubClient, ResearchPipeline

        mock_gh_client = MagicMock()
        mock_gh_client.fetch_events_since.return_value = [{"pr_number": 42, "type": "PullRequestEvent"}]
        mock_gh_client.fetch_pr.return_value = {"number": 42, "title": "Feat: Trello integration", "state": "open"}
        mock_github_cls.return_value = mock_gh_client

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        pipeline.run()

        mock_gh_client.fetch_pr.assert_called_once_with(42)

    @patch("vault.research.pipeline.TLDVClient")
    @patch("vault.research.pipeline.TrelloClient")
    def test_tldv_run_uses_fetch_meeting_for_payload(
        self, mock_trello_cls, mock_tldv_cls, tmp_state_file, tmp_pipeline_dir
    ):
        from vault.research.pipeline import ResearchPipeline, TLDVClient

        mock_tldv_client = MagicMock()
        mock_tldv_client.fetch_events_since.return_value = [{"meeting_id": "mtg-abc", "type": "MeetingEvent"}]
        mock_tldv_client.fetch_meeting.return_value = {
            "id": "mtg-abc",
            "title": "Daily standup",
            "summary": "Discussed Trello integration",
        }
        mock_tldv_cls.return_value = mock_tldv_client

        pipeline = ResearchPipeline(
            source="tldv",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        pipeline.run()

        mock_tldv_client.fetch_meeting.assert_called_once_with("mtg-abc")

    @patch("vault.research.pipeline.TrelloClient")
    def test_trello_run_does_not_call_fetch_pr_or_meeting(self, mock_trello_cls, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        mock_client = MagicMock()
        mock_client.fetch_events_since.return_value = [
            _make_trello_event("trello:card_created", action_id="act_foo", card_id="c1", list_id="l1"),
        ]
        mock_trello_cls.return_value = mock_client

        pipeline = ResearchPipeline(
            source="trello",
            state_path=tmp_state_file,
            research_dir=tmp_pipeline_dir,
        )
        pipeline.run()

        # Trello must NOT invoke fetch_pr or fetch_meeting
        assert not hasattr(mock_client, "fetch_pr") or not callable(getattr(mock_client, "fetch_pr", None)) or mock_client.fetch_pr.call_count == 0
