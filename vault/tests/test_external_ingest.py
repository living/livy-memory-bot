"""Integration tests for run_external_ingest — full pipeline flow."""
from unittest.mock import patch
from pathlib import Path
import tempfile


class TestExternalIngestIntegration:
    """End-to-end flow: fetch → resolve → build → persist."""

    def test_full_pipeline_with_tldv_api_participants(self):
        """Meeting fetched from Supabase → TLDV API resolves participants → entities written."""
        from vault.ingest.external_ingest import run_external_ingest

        raw_meetings = [{
            "id": "int-test-001",
            "name": "Integration Test Meeting",
            "created_at": "2026-04-11T10:00:00Z",
            "participants": [],
            "whisper_transcript_json": [],
        }]

        tldv_result = {
            "participants": [
                {"id": "p1", "name": "Lincoln", "email": "lincoln@l.com"},
            ],
            "speakers": ["Lincoln"],
            "token_expired": False,
        }

        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp)
            with patch("vault.ingest.external_ingest.fetch_meetings_from_supabase", return_value=raw_meetings), \
                 patch("vault.ingest.external_ingest.resolve_participants_for_meeting", return_value={
                     "status": "ok",
                     "participants": [
                         {"id": "p1", "name": "Lincoln", "email": "lincoln@l.com",
                          "source_key": "tldv:participant:int-test-001:p1", "source": "tldv_api"}
                     ],
                 }), \
                 patch("vault.ingest.external_ingest.fetch_cards", return_value=([], [])):
                result = run_external_ingest(vault_root=vault_root, tldv_token="fake")

        assert result["meetings_fetched"] == 1
        assert result["meetings_resolved"] == 1
        assert result["meetings_skipped"] == 0

    def test_skip_meeting_without_participants(self):
        """All sources empty → meeting skipped, pipeline continues."""
        from vault.ingest.external_ingest import run_external_ingest

        raw_meetings = [{
            "id": "int-test-002",
            "name": "Empty Meeting",
            "created_at": "2026-04-11T10:00:00Z",
            "participants": [],
            "whisper_transcript_json": [],
        }]

        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp)
            with patch("vault.ingest.external_ingest.fetch_meetings_from_supabase", return_value=raw_meetings), \
                 patch("vault.ingest.external_ingest.resolve_participants_for_meeting", return_value={
                     "status": "skip",
                     "reason": "NO_PARTICIPANTS",
                     "tried": ["tldv_api"],
                 }), \
                 patch("vault.ingest.external_ingest.fetch_cards", return_value=([], [])):
                result = run_external_ingest(vault_root=vault_root, tldv_token="fake")

        assert result["meetings_skipped"] == 1
        assert result["meetings_written"] == 0
        assert len(result["skips"]) == 1
        assert result["skips"][0]["reason"] == "NO_PARTICIPANTS"

    def test_multiple_meetings_mixed_results(self):
        """2 meetings: 1 resolved, 1 skipped."""
        from vault.ingest.external_ingest import run_external_ingest

        raw_meetings = [
            {
                "id": "meet-ok",
                "name": "Good Meeting",
                "created_at": "2026-04-11T10:00:00Z",
                "participants": [],
                "whisper_transcript_json": [],
            },
            {
                "id": "meet-empty",
                "name": "Empty Meeting",
                "created_at": "2026-04-11T10:00:00Z",
                "participants": [],
                "whisper_transcript_json": [],
            },
        ]

        def mock_resolve(raw, token):
            mid = raw.get("id", "")
            if mid == "meet-ok":
                return {"status": "ok", "participants": [
                    {"id": "p1", "name": "Lincoln", "email": None,
                     "source_key": "tldv:participant:meet-ok:p1", "source": "tldv_api"}
                ]}
            return {"status": "skip", "reason": "NO_PARTICIPANTS", "tried": ["tldv_api"]}

        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp)
            with patch("vault.ingest.external_ingest.fetch_meetings_from_supabase", return_value=raw_meetings), \
                 patch("vault.ingest.external_ingest.resolve_participants_for_meeting", side_effect=mock_resolve), \
                 patch("vault.ingest.external_ingest.fetch_cards", return_value=([], [])):
                result = run_external_ingest(vault_root=vault_root, tldv_token="fake")

        assert result["meetings_fetched"] == 2
        assert result["meetings_resolved"] == 1
        assert result["meetings_skipped"] == 1

    def test_dry_run_does_not_write_files(self):
        """When dry_run=True, no files are written to vault_root."""
        from vault.ingest.external_ingest import run_external_ingest

        raw_meetings = [{
            "id": "dryrun-test-001",
            "name": "Dry Run Test Meeting",
            "created_at": "2026-04-11T10:00:00Z",
            "participants": [],
            "whisper_transcript_json": [],
        }]

        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp)
            with patch("vault.ingest.external_ingest.fetch_meetings_from_supabase", return_value=raw_meetings), \
                 patch("vault.ingest.external_ingest.resolve_participants_for_meeting", return_value={
                     "status": "ok",
                     "participants": [
                         {"id": "dr1", "name": "Alice", "email": "alice@example.com",
                          "source_key": "tldv:participant:dryrun-test-001:dr1", "source": "tldv_api"},
                         {"id": "dr2", "name": "Bob", "email": "bob@example.com",
                          "source_key": "tldv:participant:dryrun-test-001:dr2", "source": "tldv_api"},
                     ],
                 }), \
                 patch("vault.ingest.external_ingest.fetch_cards", return_value=([], [])):
                result = run_external_ingest(vault_root=vault_root, tldv_token="fake", dry_run=True)

            # Summary should reflect what was processed
            assert result["meetings_resolved"] == 1
            assert result["meetings_written"] == 0
            assert result["persons_written"] == 0
            assert result["relationships_written"] == 0
            assert result["cards_written"] == 0
            assert result["dry_run"] is True

            # NO files written anywhere under vault_root
            written_files = list(vault_root.rglob("*"))
            assert len(written_files) == 0, (
                f"dry_run=True should not write any files, but found: {written_files}"
            )


class TestExternalIngestLockAndCursors:
    """Lock, cursors, run_id, and log integration — Task 5b."""

    def test_lock_prevents_concurrent_runs(self):
        """If lock is active, run returns skipped_reason='locked'."""
        from vault.ingest.cursor import acquire_lock
        from vault.ingest.external_ingest import run_external_ingest

        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp)
            acquire_lock(vault_root, "vault-lint", pid=99999)
            result = run_external_ingest(
                vault_root=vault_root,
                tldv_token="fake",
                meeting_days=1,
            )
            assert result.get("skipped_reason") == "locked"
            assert result.get("run_id") is not None

    def test_cursors_updated_on_success(self):
        """After successful run, tldv cursor is written."""
        from vault.ingest.cursor import read_cursor
        from vault.ingest.external_ingest import run_external_ingest

        raw = [{
            "id": "c1",
            "name": "Test",
            "created_at": "2026-04-11T10:00:00Z",
            "participants": [{
                "id": "p1",
                "name": "Bob",
                "email": None,
                "source_key": "tldv:participant:c1:p1",
                "source": "tldv_api",
            }],
            "whisper_transcript_json": [],
        }]

        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp)
            with patch("vault.ingest.external_ingest.fetch_meetings_from_supabase", return_value=raw), \
                 patch("vault.ingest.external_ingest.fetch_cards", return_value=([], [])):
                result = run_external_ingest(
                    vault_root=vault_root,
                    tldv_token="fake",
                    meeting_days=1,
                )

            cursor = read_cursor(vault_root, "tldv")
            assert cursor["last_run_at"] is not None
            assert cursor["last_run_id"] is not None

    def test_run_returns_run_id(self):
        """Every run has a run_id."""
        from vault.ingest.external_ingest import run_external_ingest

        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp)
            with patch("vault.ingest.external_ingest.fetch_meetings_from_supabase", return_value=[]), \
                 patch("vault.ingest.external_ingest.fetch_cards", return_value=([], [])):
                result = run_external_ingest(
                    vault_root=vault_root,
                    tldv_token="fake",
                    meeting_days=1,
                )

            assert result.get("run_id") is not None
            assert len(result["run_id"]) == 36  # UUID4

    def test_log_written_after_run(self):
        """log.md has entry after run."""
        from vault.ingest.external_ingest import run_external_ingest

        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp)
            with patch("vault.ingest.external_ingest.fetch_meetings_from_supabase", return_value=[]), \
                 patch("vault.ingest.external_ingest.fetch_cards", return_value=([], [])):
                run_external_ingest(
                    vault_root=vault_root,
                    tldv_token="fake",
                    meeting_days=1,
                )

            assert (vault_root / "log.md").exists()
            log_text = (vault_root / "log.md").read_text()
            assert "vault-ingest" in log_text

    def test_lock_released_after_exception(self):
        """Lock is released even if ingest raises."""
        from vault.ingest.cursor import is_locked
        from vault.ingest.external_ingest import run_external_ingest

        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp)
            with patch("vault.ingest.external_ingest.fetch_meetings_from_supabase", side_effect=RuntimeError("boom")), \
                 patch("vault.ingest.external_ingest.fetch_cards", return_value=([], [])):
                result = run_external_ingest(
                    vault_root=vault_root,
                    tldv_token="fake",
                    meeting_days=1,
                )

            # Even with error, lock should be released
            assert is_locked(vault_root) is False
            # And run_id should still be present
            assert result.get("run_id") is not None

    def test_index_updated_after_meeting_written(self):
        """After successful meeting, index.md has entry."""
        from vault.ingest.external_ingest import run_external_ingest
        from vault.ingest.index_manager import read_index

        raw = [{
            "id": "idx-test-001",
            "name": "Indexed Meeting",
            "created_at": "2026-04-11T10:00:00Z",
            "participants": [{
                "id": "p1",
                "name": "Alice",
                "email": None,
                "source_key": "tldv:participant:idx-test-001:p1",
                "source": "tldv_api",
            }],
            "whisper_transcript_json": [],
        }]

        with tempfile.TemporaryDirectory() as tmp:
            vault_root = Path(tmp)
            with patch("vault.ingest.external_ingest.fetch_meetings_from_supabase", return_value=raw), \
                 patch("vault.ingest.external_ingest.fetch_cards", return_value=([], [])):
                run_external_ingest(
                    vault_root=vault_root,
                    tldv_token="fake",
                    meeting_days=1,
                )

            assert (vault_root / "index.md").exists()
            index = read_index(vault_root)
            # Should have at least one entry for the meeting or person
            assert len(index) > 0
