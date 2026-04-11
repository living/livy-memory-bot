"""
Tests for fuzzy name deduplication in participant resolution.

Covers real duplicates found in production:
- Lincoln Quinan vs Lincoln Quinan Junior
- Luiz Rogério vs Luiz Rogério Carvalho
- Marcio Rocha vs marcio rocha (case)

Rule: if one name is a prefix of the other (word-level), they are the same person.
The longer (richer) name wins.
"""
import pytest
from unittest.mock import patch


class TestFuzzyNameDeduplication:
    """Cross-source fuzzy name matching for participants."""

    def test_prefix_match_lincoln(self):
        """'Lincoln Quinan' (speaker) should merge with 'Lincoln Quinan Junior' (API)."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {"id": "m1", "participants": []}
        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={
                "participants": [
                    {"id": "u1", "name": "Lincoln Quinan Junior", "email": "lincoln@livingnet.com.br"},
                ],
                "speakers": ["Lincoln Quinan"],
            },
        ):
            result = resolve_participants_for_meeting(raw, "tok")

        names = {p["name"] for p in result["participants"]}
        assert len(result["participants"]) == 1, f"Expected 1, got {len(result['participants'])}: {names}"
        assert "Lincoln Quinan Junior" in names  # longer name wins

    def test_prefix_match_luiz(self):
        """'Luiz Rogério' (speaker) should merge with 'Luiz Rogério Carvalho' (API)."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {"id": "m2", "participants": []}
        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={
                "participants": [
                    {"id": "u2", "name": "Luiz Rogério Carvalho", "email": "luiz@livingnet.com.br"},
                ],
                "speakers": ["Luiz Rogério"],
            },
        ):
            result = resolve_participants_for_meeting(raw, "tok")

        names = {p["name"] for p in result["participants"]}
        assert len(result["participants"]) == 1, f"Expected 1, got {len(result['participants'])}: {names}"
        assert "Luiz Rogério Carvalho" in names

    def test_case_insensitive_match(self):
        """'marcio rocha' (lowercase) should merge with 'Marcio Rocha' (title case)."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {"id": "m3", "participants": []}
        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={
                "participants": [
                    {"id": "u3", "name": "Marcio Rocha", "email": "marcio@livingnet.com.br"},
                ],
                "speakers": ["marcio rocha"],
            },
        ):
            result = resolve_participants_for_meeting(raw, "tok")

        names = {p["name"] for p in result["participants"]}
        assert len(result["participants"]) == 1, f"Expected 1, got {len(result['participants'])}: {names}"
        assert "Marcio Rocha" in names

    def test_different_names_no_merge(self):
        """Different names that aren't prefixes should NOT merge."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {"id": "m4", "participants": []}
        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={
                "participants": [
                    {"id": "u1", "name": "Alice Costa", "email": "alice@x.com"},
                    {"id": "u2", "name": "Bob Silva", "email": "bob@x.com"},
                ],
                "speakers": [],
            },
        ):
            result = resolve_participants_for_meeting(raw, "tok")

        assert len(result["participants"]) == 2

    def test_speaker_only_prefix_dedup(self):
        """Two speakers where one name is prefix of the other → merge, longer wins."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {"id": "m5", "participants": []}
        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={
                "participants": [],
                "speakers": ["Sergio Fraga", "Sergio"],
            },
        ):
            result = resolve_participants_for_meeting(raw, "tok")

        names = {p["name"] for p in result["participants"]}
        assert len(result["participants"]) == 1, f"Expected 1, got {len(result['participants'])}: {names}"
        assert "Sergio Fraga" in names

    def test_full_name_without_api_id(self):
        """Speaker 'Lincoln Quinan Junior' + API 'Lincoln Quinan' with ID → merge, keep full name + ID."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {"id": "m6", "participants": []}
        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={
                "participants": [
                    {"id": "u1", "name": "Lincoln Quinan", "email": "lincoln@x.com"},
                ],
                "speakers": ["Lincoln Quinan Junior"],
            },
        ):
            result = resolve_participants_for_meeting(raw, "tok")

        parts = result["participants"]
        assert len(parts) == 1, f"Expected 1, got {len(parts)}"
        # Should keep the richer name AND the ID + email
        assert parts[0]["name"] == "Lincoln Quinan Junior"
        assert parts[0]["id"] == "u1"
        assert parts[0]["email"] == "lincoln@x.com"

    def test_no_false_positive_partial_word(self):
        """'Robert' should NOT merge with 'Robert Urech' — wait, actually it should (prefix match).
        But 'Roberto' should NOT merge with 'Robert Urech'."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {"id": "m7", "participants": []}
        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={
                "participants": [
                    {"id": "u1", "name": "Robert Urech", "email": "robert@x.com"},
                ],
                "speakers": ["Roberto"],
            },
        ):
            result = resolve_participants_for_meeting(raw, "tok")

        assert len(result["participants"]) == 2  # different people

    def test_accented_name_match(self):
        """'André Chaves' and 'Andre Chaves' (no accent) should merge."""
        from vault.ingest.meeting_ingest import resolve_participants_for_meeting

        raw = {"id": "m8", "participants": []}
        with patch(
            "vault.ingest.meeting_ingest.fetch_participants_from_tldv_api",
            return_value={
                "participants": [
                    {"id": "u1", "name": "André Chaves", "email": "andre@x.com"},
                ],
                "speakers": ["Andre Chaves"],
            },
        ):
            result = resolve_participants_for_meeting(raw, "tok")

        names = {p["name"] for p in result["participants"]}
        assert len(result["participants"]) == 1, f"Expected 1, got {len(result['participants'])}: {names}"
        assert "André Chaves" in names  # accented version wins (richer)
