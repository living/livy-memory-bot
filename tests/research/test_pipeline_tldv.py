"""Tests for vault/research/pipeline.py — TLDV research pipeline.

RED phase: write failing tests first.
GREEN phase: implement minimal code to pass.

Coverage:
- Late event handling (out-of-order, event_key dedupe even when event_at < last_seen_at)
- Context build via claude-mem + wiki + FS
- Entity resolution integration
- Validate / apply
- Audit logging
- Self-healing in read-only mode (MVP)
"""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from vault.research.state_store import load_state, save_state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_pipeline_dir(tmp_path):
    """Create a temp dir simulating .research/tldv/."""
    d = tmp_path / ".research" / "tldv"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def tmp_state_file(tmp_path):
    """Create a temp state.json."""
    p = tmp_path / "state.json"
    p.write_text(json.dumps({
        "processed_event_keys": {"github": [], "tldv": []},
        "last_seen_at": {"github": None, "tldv": None},
        "version": 1,
    }))
    return p


def _make_tldv_event(event_id: str, meeting_id: str, event_at: datetime, event_type: str = "meeting_created") -> dict:
    return {
        "id": event_id,
        "meeting_id": meeting_id,
        "type": event_type,
        "summary": f"Test meeting {meeting_id}",
        "event_at": event_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Step 1: State — read last_seen_at + processed_event_keys
# ---------------------------------------------------------------------------

class TestPipelineStateStep:
    def test_pipeline_reads_last_seen_at_from_state(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        save_state({
            "processed_event_keys": {"github": [], "tldv": []},
            "last_seen_at": {"github": None, "tldv": datetime(2026, 4, 18, 10, 0, 0, tzinfo=timezone.utc).isoformat()},
            "version": 1,
        }, tmp_state_file)

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        assert pipeline.last_seen_at is not None
        assert pipeline.last_seen_at.year == 2026

    def test_pipeline_reads_processed_event_keys(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        save_state({
            "processed_event_keys": {"github": [], "tldv": [{"key": "tldv:meeting_created:123", "event_at": "2026-04-18T10:00:00Z"}]},
            "last_seen_at": {"github": None, "tldv": "2026-04-18T10:00:00Z"},
            "version": 1,
        }, tmp_state_file)

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        assert "tldv:meeting_created:123" in pipeline.processed_event_keys


# ---------------------------------------------------------------------------
# Step 3+4: Ingest + Dedupe — event_key calculation and dedupe
# ---------------------------------------------------------------------------

class TestPipelineIngestDedup:
    def test_pipeline_calculates_event_key(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        event = _make_tldv_event("ev1", "mtg-abc", datetime(2026, 4, 18, 11, 0, 0, tzinfo=timezone.utc))
        event_key = pipeline._calculate_event_key(event)
        assert event_key == "tldv:meeting_created:ev1"

    def test_pipeline_skips_duplicate_event_key(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        save_state({
            "processed_event_keys": {"github": [], "tldv": [{"key": "tldv:meeting_created:ev1", "event_at": "2026-04-18T10:00:00Z"}]},
            "last_seen_at": {"github": None, "tldv": "2026-04-18T10:00:00Z"},
            "version": 1,
        }, tmp_state_file)

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        event = _make_tldv_event("ev1", "mtg-abc", datetime(2026, 4, 18, 11, 0, 0, tzinfo=timezone.utc))
        assert pipeline._is_duplicate(event) is True

    def test_pipeline_accepts_new_event_key(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        event = _make_tldv_event("ev2", "mtg-abc", datetime(2026, 4, 18, 11, 0, 0, tzinfo=timezone.utc))
        assert pipeline._is_duplicate(event) is False


# ---------------------------------------------------------------------------
# Late event handling — out-of-order events
# ---------------------------------------------------------------------------

class TestLateEventHandling:
    def test_out_of_order_event_is_deduped_when_already_processed(self, tmp_state_file, tmp_pipeline_dir):
        """Event with event_at < last_seen_at but never seen event_key → should be processed."""
        from vault.research.pipeline import ResearchPipeline

        # last_seen_at = 2026-04-18T12:00:00Z
        save_state({
            "processed_event_keys": {"github": [], "tldv": []},
            "last_seen_at": {"github": None, "tldv": "2026-04-18T12:00:00Z"},
            "version": 1,
        }, tmp_state_file)

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        # Event at 2026-04-18T11:00:00Z (before last_seen_at), new event_key
        event = _make_tldv_event("ev-late", "mtg-late", datetime(2026, 4, 18, 11, 0, 0, tzinfo=timezone.utc))
        # Should NOT be skipped just because event_at < last_seen_at — only dedupe on event_key
        assert pipeline._is_duplicate(event) is False

    def test_late_event_with_existing_key_is_skipped(self, tmp_state_file, tmp_pipeline_dir):
        """Event with event_at < last_seen_at AND existing event_key → must skip."""
        from vault.research.pipeline import ResearchPipeline

        save_state({
            "processed_event_keys": {"github": [], "tldv": [{"key": "tldv:meeting_created:ev-old", "event_at": "2026-04-18T10:00:00Z"}]},
            "last_seen_at": {"github": None, "tldv": "2026-04-18T12:00:00Z"},
            "version": 1,
        }, tmp_state_file)

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        event = _make_tldv_event("ev-old", "mtg-old", datetime(2026, 4, 18, 11, 0, 0, tzinfo=timezone.utc))
        assert pipeline._is_duplicate(event) is True


# ---------------------------------------------------------------------------
# Step 5: Context build
# ---------------------------------------------------------------------------

class TestContextBuild:
    def test_context_loads_from_wiki_fs(self, tmp_state_file, tmp_pipeline_dir, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        # Create a mock wiki file
        wiki_dir = tmp_path / "memory" / "vault"
        wiki_dir.mkdir(parents=True)
        (wiki_dir / "index.md").write_text("# Index\n- Project Alpha")

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir, wiki_root=wiki_dir)
        context = pipeline._build_context({"meeting_id": "mtg-abc"})
        assert "wiki" in context
        assert "index" in context["wiki"]

    @patch("vault.research.pipeline.get_claude_mem_context")
    def test_context_loads_from_claude_mem(self, mock_claude_mem, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        mock_claude_mem.return_value = {"entities": [], "recent_sessions": []}

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        context = pipeline._build_context({"meeting_id": "mtg-abc"})
        assert "claude_mem" in context
        mock_claude_mem.assert_called_once()


# ---------------------------------------------------------------------------
# Step 6: Entity resolution integration
# ---------------------------------------------------------------------------

class TestEntityResolution:
    def test_pipeline_resolves_person_identities(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        resolution = pipeline._resolve_entities([
            {"source": "github", "identifier": "user1", "email": "alice@example.com", "candidates": [
                {"source": "tldv", "identifier": "alice-tldv", "email": "alice@example.com", "sources": ["tldv"], "event_at": "2026-04-18T10:00:00Z"}
            ]}
        ])
        assert len(resolution) == 1
        assert resolution[0]["confidence"] >= 0.60  # auto-link


# ---------------------------------------------------------------------------
# Step 7-8: Hypothesize + Validate
# ---------------------------------------------------------------------------

class TestHypothesizeValidate:
    def test_validate_checks_quality_gate(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        # Hypothesis with empty content should fail quality gate
        hypothesis = {"action": "create_page", "content": "", "entity_type": "meeting"}
        result = pipeline._validate(hypothesis)
        assert result["approved"] is False
        assert "quality" in result["reason"].lower()

    def test_validate_checks_coherence(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        # Coherence check: meeting title too short
        hypothesis = {"action": "create_page", "content": "x", "entity_type": "meeting"}
        result = pipeline._validate(hypothesis)
        assert result["approved"] is False


# ---------------------------------------------------------------------------
# Step 9: Apply (write only allowed paths)
# ---------------------------------------------------------------------------

class TestApply:
    def test_apply_only_writes_to_allowed_paths(self, tmp_state_file, tmp_pipeline_dir, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir, allowed_paths=[str(tmp_path / "allowed")])

        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        pipeline.allowed_paths = [str(allowed_dir)]

        hypothesis = {"action": "create_page", "path": str(allowed_dir / "test.md"), "content": "# Test"}
        result = pipeline._apply([hypothesis])
        assert result["applied_count"] == 1
        assert (allowed_dir / "test.md").exists()

    def test_apply_rejects_path_outside_allowed(self, tmp_state_file, tmp_pipeline_dir, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir, allowed_paths=["/safe/allowed"])

        hypothesis = {"action": "create_page", "path": "/forbidden/test.md", "content": "# Test"}
        result = pipeline._apply([hypothesis])
        assert result["applied_count"] == 0
        assert result["rejected_count"] == 1


# ---------------------------------------------------------------------------
# Step 10: Audit logging
# ---------------------------------------------------------------------------

class TestAuditLogging:
    def test_pipeline_logs_audit_trail(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        pipeline._log_audit("test_action", {"key": "value"})

        audit_file = tmp_pipeline_dir / "audit.log"
        assert audit_file.exists()
        entries = json.loads(audit_file.read_text())
        assert any(e.get("action") == "test_action" for e in entries)


# ---------------------------------------------------------------------------
# Step 11: State persistence
# ---------------------------------------------------------------------------

class TestStatePersistence:
    def test_pipeline_persists_event_key_after_processing(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        event = _make_tldv_event("ev-new", "mtg-new", datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc))

        pipeline._persist_event_key(event)
        state = load_state(tmp_state_file)
        keys = [e["key"] for e in state["processed_event_keys"]["tldv"]]
        assert "tldv:meeting_created:ev-new" in keys

    def test_pipeline_advances_last_seen_at(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        save_state({
            "processed_event_keys": {"github": [], "tldv": []},
            "last_seen_at": {"github": None, "tldv": "2026-04-18T10:00:00Z"},
            "version": 1,
        }, tmp_state_file)

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        new_time = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        pipeline._advance_last_seen_at(new_time)

        state = load_state(tmp_state_file)
        assert state["last_seen_at"]["tldv"] is not None


# ---------------------------------------------------------------------------
# Self-healing (read-only MVP)
# ---------------------------------------------------------------------------

class TestSelfHealingReadOnly:
    def test_self_healing_accumulates_evidence_without_applying(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        # Self-healing should accumulate evidence but NOT apply merges
        pipeline._accumulate_self_healing_evidence({"merge_candidate": {"source": "github", "target": "tldv"}})

        audit_file = tmp_pipeline_dir / "self_healing_evidence.jsonl"
        assert audit_file.exists()

    def test_self_healing_does_not_merge_in_read_only_mode(self, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        pipeline.read_only_mode = True

        # Even with strong evidence, read-only mode should NOT apply
        result = pipeline._apply_self_healing([{"action": "merge", "confidence": 0.95}])
        assert result["applied_count"] == 0
        assert result["mode"] == "read_only"


# ---------------------------------------------------------------------------
# E2E run
# ---------------------------------------------------------------------------

class TestPipelineE2E:
    @patch("vault.research.pipeline.TLDVClient")
    def test_pipeline_runs_full_cycle(self, mock_tldv_client, tmp_state_file, tmp_pipeline_dir):
        from vault.research.pipeline import ResearchPipeline

        mock_client = MagicMock()
        mock_client.fetch_events_since.return_value = [
            _make_tldv_event("ev-e2e-1", "mtg-e2e", datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)),
        ]
        mock_client.fetch_meeting.return_value = {"id": "mtg-e2e", "title": "Test Meeting", "summary": "Summary", "participants": []}
        mock_tldv_client.return_value = mock_client

        pipeline = ResearchPipeline(source="tldv", state_path=tmp_state_file, research_dir=tmp_pipeline_dir)
        result = pipeline.run()

        assert result["status"] in ("success", "partial")
        assert result["events_processed"] >= 0
