from unittest.mock import patch


class TestResolveParticipants:
    def test_tldv_api_primary_source(self):
        """TLDV API returns participants → used as primary."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {
            "id": "meeting-123",
            "participants": [{"id": "sb1", "name": "Supabase User", "email": "sb@example.com"}],
        }

        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={
                "participants": [{"id": "u1", "name": "Alice", "email": "alice@example.com"}],
                "speakers": [],
                "token_expired": False,
            },
        ):
            result = resolve_participants_for_meeting(raw, "token-abc")

        assert result["status"] == "ok"
        assert len(result["participants"]) == 1
        assert result["participants"][0]["id"] == "u1"
        assert result["participants"][0]["name"] == "Alice"
        assert result["participants"][0]["source"] == "tldv_api"

    def test_supabase_fallback_when_api_empty(self):
        """TLDV API returns empty → Supabase participants used."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {
            "id": "meeting-123",
            "participants": [{"id": "sb1", "name": "Supabase User", "email": "sb@example.com"}],
        }

        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={"participants": [], "speakers": [], "token_expired": False},
        ):
            result = resolve_participants_for_meeting(raw, "token-abc")

        assert result["status"] == "ok"
        assert len(result["participants"]) == 1
        assert result["participants"][0]["id"] == "sb1"
        assert result["participants"][0]["source"] == "supabase_participants"

    def test_supabase_speaker_fallback(self):
        """TLDV API empty + participants empty → whisper_transcript_json speakers used."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {
            "id": "meeting-123",
            "participants": [],
            "whisper_transcript_json": [
                {"speaker": "Lincoln", "text": "Bom dia"},
                {"speaker": "Robert", "text": "Fechado"},
                {"speaker": "Lincoln", "text": "Vamos"},
            ],
        }

        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={"participants": [], "speakers": [], "token_expired": False},
        ):
            result = resolve_participants_for_meeting(raw, "token-abc")

        assert result["status"] == "ok"
        assert len(result["participants"]) == 2
        names = {p["name"] for p in result["participants"]}
        assert names == {"Lincoln", "Robert"}
        assert all(p["source"] == "supabase_whisper_speakers" for p in result["participants"])

    def test_skip_when_all_sources_empty(self):
        """All sources empty → Skip with reason NO_PARTICIPANTS."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {"id": "meeting-123", "participants": [], "whisper_transcript_json": []}

        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={"participants": [], "speakers": [], "token_expired": False},
        ):
            result = resolve_participants_for_meeting(raw, "token-abc")

        assert result == {
            "status": "skip",
            "reason": "NO_PARTICIPANTS",
            "tried": ["tldv_api", "supabase_participants", "supabase_whisper_speakers"],
        }

    def test_tldv_api_speakers_enrich_participants(self):
        """TLDV API returns speakers not in participants → both merged."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {"id": "meeting-123", "participants": []}

        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={
                "participants": [{"id": "u1", "name": "Alice", "email": "alice@example.com"}],
                "speakers": ["Alice", "Robert"],
                "token_expired": False,
            },
        ):
            result = resolve_participants_for_meeting(raw, "token-abc")

        assert result["status"] == "ok"
        names = {p["name"] for p in result["participants"]}
        assert names == {"Alice", "Robert"}

    def test_deduplication_by_id_and_name(self):
        """Dedupe by ID first, then by name for ID-less participants.

        - Same ID → collapsed (first wins)
        - Different non-empty IDs → both kept (even if same name)
        - ID-less participants with same name → collapsed
        """
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {"id": "meeting-123", "participants": []}

        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={
                "participants": [
                    {"id": "u1", "name": "Alice", "email": "alice@example.com"},
                    {"id": "u1", "name": "Alice Duplicate", "email": "alice2@example.com"},
                    {"id": "u2", "name": "  alice  ", "email": "alice3@example.com"},
                ],
                "speakers": ["Bob", "Bob"],
                "token_expired": False,
            },
        ):
            result = resolve_participants_for_meeting(raw, "token-abc")

        assert result["status"] == "ok"
        ids = {p["id"] for p in result["participants"]}
        # u1 and u2 are different non-empty IDs → both kept
        assert "u1" in ids
        assert "u2" in ids
        # Bob from speakers (no id) added once
        names = {p["name"] for p in result["participants"]}
        assert "Bob" in names
        assert len(result["participants"]) == 3
