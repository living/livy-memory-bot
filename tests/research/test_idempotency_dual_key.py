"""Tests for Task 6 — Idempotency dual key (event_key + content_key).

DUAL KEY MODEL (from wiki-v2-design.md §9.2):
  1. event_key  (ingest): source:type:object_id[:action_id]
     → dedupes the *event* itself (webhook, card update, etc.)
  2. content_key (semantic): {source}:{source_id}:{content_hash}
     → dedupes *identical content* even if it arrives via a different event_key
     (e.g. same content written twice from a retry / replay)

Both keys are checked before processing.  Both are persisted after a successful run.

Coverage:
  - content_key computation (stable SHA256 hash of canonical JSON)
  - pipeline rejects new event_key + existing content_key (semantic duplicate)
  - content_key persisted alongside event_key
  - load_state initialises processed_content_keys for legacy state
  - upsert_processed_content_key is idempotent
  - compact_processed_keys cleans both event_keys and contentKeys
  - monthly_snapshot includes content_keys
  - state_metrics reports content_key counts
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from vault.research.state_store import (
    DEFAULT_STATE,
    load_state,
    save_state,
    upsert_processed_event_key,
    upsert_processed_content_key,
    compact_processed_keys,
    monthly_snapshot,
    state_metrics,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash16(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


FULL_STATE = {
    "processed_event_keys": {"github": [], "tldv": [], "trello": []},
    "processed_content_keys": {"github": [], "tldv": [], "trello": []},
    "last_seen_at": {"github": None, "tldv": None, "trello": None},
    "pending_conflicts": [],
    "version": 1,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_state_file(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps(FULL_STATE))
    return p


# ---------------------------------------------------------------------------
# DEFAULT_STATE must include processed_content_keys
# ---------------------------------------------------------------------------

class TestDefaultStateDualKey:
    def test_default_state_has_processed_content_keys(self):
        """DEFAULT_STATE must pre-allocate processed_content_keys for all sources."""
        assert "processed_content_keys" in DEFAULT_STATE
        assert isinstance(DEFAULT_STATE["processed_content_keys"], dict)

    def test_default_state_content_keys_has_all_sources(self):
        for source in ("github", "tldv", "trello"):
            assert source in DEFAULT_STATE["processed_content_keys"]
            assert DEFAULT_STATE["processed_content_keys"][source] == []


# ---------------------------------------------------------------------------
# upsert_processed_content_key
# ---------------------------------------------------------------------------

class TestUpsertProcessedContentKey:
    def test_adds_new_content_key(self, tmp_state_file):
        content_key = "github:42:a1b2c3d4e5f6g7h8"
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_content_key("github", content_key, event_at, tmp_state_file)
        keys = [e["key"] for e in state["processed_content_keys"]["github"]]
        assert content_key in keys

    def test_is_idempotent(self, tmp_state_file):
        content_key = "github:99:deadbeef"
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_content_key("github", content_key, event_at, tmp_state_file)
        state = upsert_processed_content_key("github", content_key, event_at, tmp_state_file)
        keys = [e["key"] for e in state["processed_content_keys"]["github"]]
        assert keys.count(content_key) == 1

    def test_different_content_keys_for_same_source(self, tmp_state_file):
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_content_key("tldv", "tldv:123:aaa111", event_at, tmp_state_file)
        state = upsert_processed_content_key("tldv", "tldv:123:bbb222", event_at, tmp_state_file)
        keys = [e["key"] for e in state["processed_content_keys"]["tldv"]]
        assert "tldv:123:aaa111" in keys
        assert "tldv:123:bbb222" in keys
        assert len(keys) == 2

    def test_creates_source_if_missing(self, tmp_state_file):
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_content_key("new_src", "new_src:1:abc", event_at, tmp_state_file)
        assert "new_src" in state["processed_content_keys"]

    def test_stores_event_at(self, tmp_state_file):
        content_key = "trello:card_x:cafecafe"
        event_at = datetime(2026, 4, 19, 8, 0, 0, tzinfo=timezone.utc)
        state = upsert_processed_content_key("trello", content_key, event_at, tmp_state_file)
        entry = next(e for e in state["processed_content_keys"]["trello"] if e["key"] == content_key)
        assert "event_at" in entry
        assert "2026-04-19" in entry["event_at"]

    def test_persists_to_file(self, tmp_state_file):
        content_key = "github:77:feedface"
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_content_key("github", content_key, event_at, tmp_state_file)
        reloaded = json.loads(tmp_state_file.read_text())
        keys = [e["key"] for e in reloaded["processed_content_keys"]["github"]]
        assert content_key in keys


# ---------------------------------------------------------------------------
# load_state — processed_content_keys migration
# ---------------------------------------------------------------------------

class TestLoadStateContentKeysMigration:
    def test_load_state_returns_content_keys(self, tmp_state_file):
        state = load_state(tmp_state_file)
        assert "processed_content_keys" in state

    def test_load_state_adds_content_keys_to_legacy_state(self, tmp_path):
        """Legacy state without processed_content_keys must get it added on load."""
        legacy = {
            "processed_event_keys": {"github": [], "tldv": []},
            "last_seen_at": {"github": None, "tldv": None},
            "version": 1,
        }
        p = tmp_path / "state.json"
        p.write_text(json.dumps(legacy))
        state = load_state(p)
        assert "processed_content_keys" in state
        assert "github" in state["processed_content_keys"]
        assert "tldv" in state["processed_content_keys"]
        assert state["processed_content_keys"]["github"] == []
        assert state["processed_content_keys"]["tldv"] == []

    def test_load_state_adds_trello_to_content_keys_if_missing(self, tmp_path):
        """Legacy state that has github/tldv but not trello must get trello added."""
        legacy = {
            "processed_event_keys": {"github": [], "tldv": []},
            "processed_content_keys": {"github": [], "tldv": []},
            "last_seen_at": {"github": None, "tldv": None},
            "version": 1,
        }
        p = tmp_path / "state.json"
        p.write_text(json.dumps(legacy))
        state = load_state(p)
        assert "trello" in state["processed_content_keys"]


# ---------------------------------------------------------------------------
# compact_processed_keys — must clean both event_keys and contentKeys
# ---------------------------------------------------------------------------

class TestCompactBothKeys:
    def test_compact_removes_old_content_keys(self, tmp_state_file):
        old_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        recent_at = datetime.now(timezone.utc) - timedelta(days=10)
        state = load_state(tmp_state_file)
        state["processed_content_keys"]["github"] = [
            {"key": "github:old:a1b2", "event_at": old_at.isoformat()},
            {"key": "github:recent:c3d4", "event_at": recent_at.isoformat()},
        ]
        save_state(state, tmp_state_file)

        compacted = compact_processed_keys(state_path=tmp_state_file, retention_days=180)
        keys = [e["key"] for e in compacted["processed_content_keys"]["github"]]
        assert "github:old:a1b2" not in keys
        assert "github:recent:c3d4" in keys

    def test_compact_removes_old_event_keys_and_content_keys_together(self, tmp_state_file):
        old_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        recent_at = datetime.now(timezone.utc) - timedelta(days=5)
        state = load_state(tmp_state_file)
        state["processed_event_keys"]["github"] = [
            {"key": "github:pr_merged:old", "event_at": old_at.isoformat()},
            {"key": "github:pr_merged:recent", "event_at": recent_at.isoformat()},
        ]
        state["processed_content_keys"]["github"] = [
            {"key": "github:42:oldhash", "event_at": old_at.isoformat()},
            {"key": "github:42:newhash", "event_at": recent_at.isoformat()},
        ]
        save_state(state, tmp_state_file)

        compacted = compact_processed_keys(state_path=tmp_state_file, retention_days=180)
        evt_keys = [e["key"] for e in compacted["processed_event_keys"]["github"]]
        ctn_keys = [e["key"] for e in compacted["processed_content_keys"]["github"]]
        assert "github:pr_merged:old" not in evt_keys
        assert "github:pr_merged:recent" in evt_keys
        assert "github:42:oldhash" not in ctn_keys
        assert "github:42:newhash" in ctn_keys


# ---------------------------------------------------------------------------
# monthly_snapshot — must include content_keys
# ---------------------------------------------------------------------------

class TestMonthlySnapshotContentKeys:
    def test_snapshot_includes_content_keys(self, tmp_state_file):
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_content_key("github", "github:1:hash1", event_at, tmp_state_file)
        upsert_processed_content_key("tldv", "tldv:2:hash2", event_at, tmp_state_file)

        snapshot = monthly_snapshot(state_path=tmp_state_file)
        assert "processed_content_keys" in snapshot
        assert "github" in snapshot["processed_content_keys"]
        assert "tldv" in snapshot["processed_content_keys"]

    def test_snapshot_does_not_mutate_state(self, tmp_state_file):
        original = tmp_state_file.read_text()
        monthly_snapshot(state_path=tmp_state_file)
        assert tmp_state_file.read_text() == original


# ---------------------------------------------------------------------------
# state_metrics — must report content_key counts
# ---------------------------------------------------------------------------

class TestStateMetricsContentKeys:
    def test_metrics_includes_content_key_counts(self, tmp_state_file):
        event_at = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)
        upsert_processed_content_key("github", "github:x:h1", event_at, tmp_state_file)
        upsert_processed_content_key("github", "github:x:h2", event_at, tmp_state_file)
        upsert_processed_content_key("tldv", "tldv:y:h3", event_at, tmp_state_file)

        metrics = state_metrics(state_path=tmp_state_file)
        assert "content_key_count" in metrics["github"]
        assert "content_size_bytes" in metrics["github"]
        assert metrics["github"]["content_key_count"] == 2
        assert metrics["tldv"]["content_key_count"] == 1


# ---------------------------------------------------------------------------
# Pipeline integration — dual key dedupe
# ---------------------------------------------------------------------------

class TestPipelineDualKeyDedup:
    def test_pipeline_reads_processed_content_keys_from_state(self, tmp_state_file, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        save_state({
            "processed_event_keys": {"github": [], "tldv": [], "trello": []},
            "processed_content_keys": {
                "github": [{"key": "github:42:deadbeef", "event_at": "2026-04-18T10:00:00Z"}],
                "tldv": [],
                "trello": [],
            },
            "last_seen_at": {"github": None, "tldv": None, "trello": None},
            "version": 1,
        }, tmp_state_file)

        # Use a matching pre-seeded key from state to validate constructor loading.

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_path / ".research" / "github",
        )
        assert "github:42:deadbeef" in pipeline.processed_content_keys

    def test_pipeline_rejects_new_event_key_with_existing_content_key(self, tmp_state_file, tmp_path):
        """Dual key: same content via new event_key → semantic duplicate → reject."""
        from vault.research.pipeline import ResearchPipeline

        # New event_key (different PR event id) but same content
        new_event = {
            "id": "ev_different_id",
            "type": "pr_merged",
            "pr_number": 42,
            "event_at": "2026-04-18T11:00:00Z",
        }

        # Pre-seed the content_key that the pipeline will compute from this event
        # (content_key is deterministically computed from source + pr_number + event JSON)
        helper_pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_path / ".research" / "github",
        )
        precomputed_content_key = helper_pipeline._build_content_key(new_event)

        save_state({
            "processed_event_keys": {"github": [], "tldv": [], "trello": []},
            "processed_content_keys": {
                "github": [{"key": precomputed_content_key, "event_at": "2026-04-18T10:00:00Z"}],
                "tldv": [],
                "trello": [],
            },
            "last_seen_at": {"github": None, "tldv": None, "trello": None},
            "version": 1,
        }, tmp_state_file)

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_path / ".research" / "github",
        )

        # _is_duplicate checks event_key only
        assert pipeline._is_duplicate(new_event) is False

        # _is_content_duplicate checks content_key (same content → same hash)
        assert pipeline._is_content_duplicate(new_event) is True

    def test_pipeline_allows_new_event_and_content_keys(self, tmp_state_file, tmp_path):
        """Fresh event with new event_key and new content_key → process normally."""
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_path / ".research" / "github",
        )

        event = {
            "id": "ev_fresh",
            "type": "pr_merged",
            "pr_number": 99,
            "event_at": "2026-04-18T11:00:00Z",
        }

        assert pipeline._is_duplicate(event) is False
        assert pipeline._is_content_duplicate(event) is False

    def test_pipeline_persists_both_keys_after_processing(self, tmp_state_file, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_path / ".research" / "github",
        )

        event = {
            "id": "ev_both",
            "type": "pr_merged",
            "pr_number": 77,
            "event_at": "2026-04-18T13:00:00Z",
        }
        pipeline._persist_event_key(event)
        pipeline._persist_content_key(event)

        state = load_state(tmp_state_file)
        evt_keys = [e["key"] for e in state["processed_event_keys"]["github"]]
        ctn_keys = [e["key"] for e in state["processed_content_keys"]["github"]]
        assert "github:pr_merged:ev_both" in evt_keys
        assert any("github:77:" in k for k in ctn_keys)

    def test_pipeline_rejects_event_with_existing_event_key_and_existing_content_key(self, tmp_state_file, tmp_path):
        """Full dedupe: event_key already seen AND content_key already seen."""
        from vault.research.pipeline import ResearchPipeline

        event = {
            "id": "ev_replay",
            "type": "pr_merged",
            "pr_number": 77,
            "event_at": "2026-04-18T12:00:00Z",
        }

        event_key = "github:pr_merged:ev_replay"
        # Pre-compute the content_key the pipeline would generate for this event
        # so we can pre-seed the state with the exact same hash
        content_key = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_path / ".research" / "github",
        )._build_content_key(event)

        save_state({
            "processed_event_keys": {
                "github": [{"key": event_key, "event_at": "2026-04-18T10:00:00Z"}],
                "tldv": [],
                "trello": [],
            },
            "processed_content_keys": {
                "github": [{"key": content_key, "event_at": "2026-04-18T10:00:00Z"}],
                "tldv": [],
                "trello": [],
            },
            "last_seen_at": {"github": None, "tldv": None, "trello": None},
            "version": 1,
        }, tmp_state_file)

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_path / ".research" / "github",
        )

        # Both keys already seen
        assert pipeline._is_duplicate(event) is True
        assert pipeline._is_content_duplicate(event) is True

    def test_pipeline_skips_event_on_content_key_match_in_run(self, tmp_state_file, tmp_path):
        """Integration: run() must skip events whose content_key was already processed."""
        from unittest.mock import MagicMock, patch

        from vault.research.pipeline import GitHubClient, GitHubRichClient, ResearchPipeline

        # Pre-seed state with content_key only (simulates replay: same content)
        content_key = "github:88:replay_content_hash"
        save_state({
            "processed_event_keys": {"github": [], "tldv": [], "trello": []},
            "processed_content_keys": {
                "github": [{"key": content_key, "event_at": "2026-04-18T09:00:00Z"}],
                "tldv": [],
                "trello": [],
            },
            "last_seen_at": {"github": None, "tldv": None, "trello": None},
            "version": 1,
        }, tmp_state_file)

        # First event: new content (pr 88, hash abcdef)
        ev_new = {
            "id": "ev_new_content",
            "pr_number": 88,
            "type": "pr_merged",
            "repo": "living/livy-memory-bot",
            "event_at": "2026-04-18T11:00:00Z",
        }

        # Second event: same content via different event_id (pr 88, hash abcdef — REPLAY)
        ev_replay = {
            "id": "ev_replay_content",
            "pr_number": 88,
            "type": "pr_merged",
            "repo": "living/livy-memory-bot",
            "event_at": "2026-04-18T12:00:00Z",
        }

        mock_client = MagicMock(spec=GitHubClient)
        mock_rich_client = MagicMock(spec=GitHubRichClient)
        mock_rich_client.normalize_rich_event.return_value = {
            "pr_number": 88,
            "repo": "living/livy-memory-bot",
            "body": "Original PR body",
            "event_at": "2026-04-18T11:00:00Z",
            # event_key intentionally omitted — content hash must not depend on event identity
        }

        def fetch_pr_side_effect(pr_number):
            if pr_number == 88:
                return {"number": 88, "title": "Feat: replay test", "merged_at": "2026-04-18T12:00:00Z"}
            return {}

        mock_client.fetch_events_since.return_value = [ev_new, ev_replay]
        mock_client.fetch_pr.side_effect = fetch_pr_side_effect

        with patch("vault.research.pipeline.GitHubClient", return_value=mock_client):
            with patch("vault.research.pipeline.GitHubRichClient", return_value=mock_rich_client):
                pipeline = ResearchPipeline(
                    source="github",
                    state_path=tmp_state_file,
                    research_dir=tmp_path / ".research" / "github",
                )
                result = pipeline.run()

        # ev_new → processed (new content_key)
        # ev_replay → skipped (content_key already seen)
        assert result["events_processed"] >= 1
        assert result["events_skipped"] >= 1

        state = load_state(tmp_state_file)
        # At least one content_key should be persisted for pr 88
        github_content_keys = [e["key"] for e in state["processed_content_keys"]["github"]]
        assert any("github:88:" in k for k in github_content_keys)


# ---------------------------------------------------------------------------
# Content hash determinism
# ---------------------------------------------------------------------------

class TestContentKeyDeterminism:
    def test_content_key_is_based_on_stable_hash(self, tmp_state_file, tmp_path):
        """Content key must be a stable SHA256-derived value — same content = same hash."""
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_path / ".research" / "github",
        )

        content = '{"pr_number": 42, "body": "Fix bug"}'
        hash1 = pipeline._compute_content_hash(content)
        hash2 = pipeline._compute_content_hash(content)
        assert hash1 == hash2

    def test_different_content_produces_different_hash(self, tmp_state_file, tmp_path):
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_path / ".research" / "github",
        )

        hash1 = pipeline._compute_content_hash('{"a": 1}')
        hash2 = pipeline._compute_content_hash('{"a": 2}')
        assert hash1 != hash2

    def test_content_key_format_is_source_id_hash(self, tmp_state_file, tmp_path):
        """Content key format: {source}:{source_id}:{content_hash}"""
        from vault.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(
            source="github",
            state_path=tmp_state_file,
            research_dir=tmp_path / ".research" / "github",
        )

        content = '{"pr_number": 42, "body": "Hello"}'
        content_key = pipeline._build_content_key({"pr_number": 42, "body": "Hello"})

        parts = content_key.split(":")
        assert len(parts) == 3
        assert parts[0] == "github"
        assert parts[1] == "42"
        assert len(parts[2]) == 64  # SHA256 hex = 64 chars
