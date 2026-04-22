"""Tests for vault/research/tldv_client.py — TLDV polling client.

RED phase: write failing tests first.
GREEN phase: implement minimal code to pass.
"""
from unittest.mock import MagicMock, patch

import requests


class TestTLDVClientFetchEventsSince:
    def test_returns_normalized_meeting_events(self):
        """fetch_events_since returns normalized tldv:meeting events."""
        from vault.research.tldv_client import TLDVClient

        fake_rows = [
            {
                "id": "meet_abc123",
                "name": "Daily 2026-04-14",
                "created_at": "2026-04-14T10:00:00Z",
                "updated_at": "2026-04-14T11:00:00Z",
            }
        ]

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = fake_rows

        with patch("requests.get", return_value=fake_response):
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            events = client.fetch_events_since("2026-04-13T00:00:00Z")

        assert len(events) == 1
        ev = events[0]
        assert ev["source"] == "tldv"
        assert ev["event_type"] == "tldv:meeting"
        assert ev["meeting_id"] == "meet_abc123"
        assert ev["name"] == "Daily 2026-04-14"

    def test_returns_empty_if_supabase_env_missing(self):
        """Without URL/key configured, returns empty list."""
        from vault.research.tldv_client import TLDVClient

        # Empty strings explicitly disable credentials and must not fallback to env.
        client = TLDVClient(supabase_url="", supabase_key="")
        assert client.fetch_events_since("2026-04-13T00:00:00Z") == []

    def test_returns_empty_on_non_200_response(self):
        """Non-200 from Supabase returns empty list."""
        from vault.research.tldv_client import TLDVClient

        fake_response = MagicMock(status_code=500)
        fake_response.json.return_value = {"error": "boom"}

        with patch("requests.get", return_value=fake_response):
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_events_since("2026-04-13T00:00:00Z") == []

    def test_returns_empty_on_request_exception(self):
        """Request exceptions are handled gracefully with empty list."""
        from vault.research.tldv_client import TLDVClient

        with patch("requests.get", side_effect=requests.RequestException("network")):
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_events_since("2026-04-13T00:00:00Z") == []

    def test_uses_updated_at_cursor_param(self):
        """When last_seen_at provided, request includes updated_at gte filter."""
        from vault.research.tldv_client import TLDVClient

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = []

        with patch("requests.get", return_value=fake_response) as mock_get:
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            client.fetch_events_since("2026-04-13T00:00:00Z")

        kwargs = mock_get.call_args.kwargs
        params = kwargs["params"]
        assert "updated_at" in params
        assert params["updated_at"].startswith("gte.")

    def test_no_last_seen_applies_updated_at_lookback_filter(self):
        """If no last_seen_at, client still applies updated_at gte from default lookback."""
        from vault.research.tldv_client import TLDVClient

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = []

        with patch("requests.get", return_value=fake_response) as mock_get:
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            client.fetch_events_since(None)

        kwargs = mock_get.call_args.kwargs
        params = kwargs["params"]
        assert "updated_at" in params
        assert params["updated_at"].startswith("gte.")


class TestTLDVClientFetchMeeting:
    def test_fetch_meeting_returns_single_normalized_item(self):
        """fetch_meeting returns one normalized meeting by id."""
        from vault.research.tldv_client import TLDVClient

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = [
            {
                "id": "meet_abc123",
                "name": "Daily",
                "created_at": "2026-04-14T10:00:00Z",
                "updated_at": "2026-04-14T11:00:00Z",
            }
        ]

        with patch("requests.get", return_value=fake_response):
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            item = client.fetch_meeting("meet_abc123")

        assert item["meeting_id"] == "meet_abc123"
        assert item["event_type"] == "tldv:meeting"

    def test_fetch_meeting_returns_empty_when_not_found(self):
        """fetch_meeting returns empty dict when not found."""
        from vault.research.tldv_client import TLDVClient

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = []

        with patch("requests.get", return_value=fake_response):
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_meeting("nope") == {}


class TestTLDVClientFetchMeetingTranscript:
    def test_prefers_azure_blob_transcript_when_available(self):
        """fetch_meeting_transcript should return Azure blob text first."""
        from vault.research.tldv_client import TLDVClient

        with patch(
            "vault.research.azure_blob_client.AzureBlobClient"
        ) as mock_az_cls, patch(
            "vault.research.supabase_transcript.SupabaseTranscriptClient"
        ) as mock_sb_cls:
            mock_az = mock_az_cls.return_value
            mock_sb = mock_sb_cls.return_value
            mock_az.fetch_transcript.return_value = "blob transcript"
            mock_sb.fetch_transcript.return_value = "supabase transcript"

            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            transcript = client.fetch_meeting_transcript("meet_abc")

        assert transcript == "blob transcript"
        mock_az.fetch_transcript.assert_called_once_with("meet_abc")
        mock_sb.fetch_transcript.assert_not_called()

    def test_falls_back_to_supabase_when_blob_missing(self):
        """If Azure returns None, fallback to Supabase transcript client."""
        from vault.research.tldv_client import TLDVClient

        with patch(
            "vault.research.azure_blob_client.AzureBlobClient"
        ) as mock_az_cls, patch(
            "vault.research.supabase_transcript.SupabaseTranscriptClient"
        ) as mock_sb_cls:
            mock_az = mock_az_cls.return_value
            mock_sb = mock_sb_cls.return_value
            mock_az.fetch_transcript.return_value = None
            mock_sb.fetch_transcript.return_value = "supabase transcript"

            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            transcript = client.fetch_meeting_transcript("meet_abc")

        assert transcript == "supabase transcript"
        mock_az.fetch_transcript.assert_called_once_with("meet_abc")
        mock_sb.fetch_transcript.assert_called_once_with("meet_abc")

    def test_returns_none_when_both_sources_unavailable(self):
        """If Azure and Supabase fail, returns None."""
        from vault.research.tldv_client import TLDVClient

        with patch(
            "vault.research.azure_blob_client.AzureBlobClient"
        ) as mock_az_cls, patch(
            "vault.research.supabase_transcript.SupabaseTranscriptClient"
        ) as mock_sb_cls:
            mock_az_cls.return_value.fetch_transcript.return_value = None
            mock_sb_cls.return_value.fetch_transcript.return_value = None

            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_meeting_transcript("meet_abc") is None

    def test_returns_none_when_meeting_id_empty(self):
        """Empty meeting_id returns None without calling any transcript source."""
        from vault.research.tldv_client import TLDVClient

        with patch(
            "vault.research.azure_blob_client.AzureBlobClient"
        ) as mock_az_cls, patch(
            "vault.research.supabase_transcript.SupabaseTranscriptClient"
        ) as mock_sb_cls:
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_meeting_transcript("") is None
            assert client.fetch_meeting_transcript("  ") is None

            # Neither client should be called for empty meeting_id
            mock_az_cls.assert_not_called()
            mock_sb_cls.assert_not_called()


class TestTLDVClientFetchSummaries:
    """Tests for fetch_summaries — retrieves summaries records for a meeting."""

    def test_fetch_summaries_returns_summaries_for_meeting(self):
        """fetch_summaries returns the summaries array for the given meeting_id."""
        from vault.research.tldv_client import TLDVClient

        fake_summaries = [
            {
                "meeting_id": "meet_abc123",
                "topics": ["API design", "Auth flow"],
                "decisions": ["Usar JWT para autenticação"],
                "tags": ["backend", "security"],
            }
        ]
        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = fake_summaries

        with patch("requests.get", return_value=fake_response) as mock_get:
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            result = client.fetch_summaries("meet_abc123")

        assert result == fake_summaries
        kwargs = mock_get.call_args.kwargs
        params = kwargs["params"]
        assert "meeting_id" in params
        assert "eq.meet_abc123" in params["meeting_id"]

    def test_fetch_summaries_returns_empty_when_meeting_id_empty(self):
        """Empty meeting_id returns empty list without network call."""
        from vault.research.tldv_client import TLDVClient

        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = []

        with patch("requests.get", return_value=fake_response) as mock_get:
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            result = client.fetch_summaries("")
            assert result == []
            assert result == client.fetch_summaries("  ")

        mock_get.assert_not_called()

    def test_fetch_summaries_returns_empty_on_non_200(self):
        """Non-200 response returns empty list."""
        from vault.research.tldv_client import TLDVClient

        fake_response = MagicMock(status_code=500)
        fake_response.json.return_value = {"error": "boom"}

        with patch("requests.get", return_value=fake_response):
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            assert client.fetch_summaries("meet_abc123") == []


class TestTLDVClientFetchEnrichmentContext:
    """Tests for fetch_enrichment_context — retrieves PRs, cards, and related meetings."""

    def test_fetch_enrichment_context_returns_linked_entities(self):
        """fetch_enrichment_context returns linked_prs, linked_cards, and related_meetings."""
        from vault.research.tldv_client import TLDVClient

        fake_linked_prs = [
            {"meeting_id": "meet_abc123", "pr_url": "https://github.com/living/repo/pull/42"}
        ]
        fake_linked_cards = [
            {"meeting_id": "meet_abc123", "card_id": "card_xyz", "card_url": "https://trello.com/c/xyz"}
        ]
        fake_related_meetings = [
            {"meeting_id": "meet_abc123", "related_meeting_id": "meet_aaa"}
        ]

        def fake_get(url, headers=None, params=None, timeout=None):
            resp = MagicMock()
            if "linked_prs" in url:
                resp.status_code = 200
                resp.json.return_value = fake_linked_prs
            elif "linked_cards" in url:
                resp.status_code = 200
                resp.json.return_value = fake_linked_cards
            elif "related_meetings" in url:
                resp.status_code = 200
                resp.json.return_value = fake_related_meetings
            else:
                resp.status_code = 200
                resp.json.return_value = []
            return resp

        with patch("requests.get", side_effect=fake_get):
            client = TLDVClient(
                supabase_url="https://example.supabase.co",
                supabase_key="key123",
            )
            result = client.fetch_enrichment_context("meet_abc123")

        assert result["linked_prs"] == fake_linked_prs
        assert result["linked_cards"] == fake_linked_cards
        assert result["related_meetings"] == fake_related_meetings

    def test_fetch_enrichment_context_returns_empty_on_empty_meeting_id(self):
        """Empty meeting_id returns empty context without network calls."""
        from vault.research.tldv_client import TLDVClient

        client = TLDVClient(
            supabase_url="https://example.supabase.co",
            supabase_key="key123",
        )
        result = client.fetch_enrichment_context("")
        assert result == {"linked_prs": [], "linked_cards": [], "related_meetings": []}


class TestTLDVToClaimsSummariesDecisions:
    """Tests for tldv_to_claims — decision extraction from summaries[].decisions."""

    def test_summaries_decisions_generate_decision_claims(self):
        """When summaries[].decisions is present and non-empty, generates decision claims."""
        from vault.research.tldv_client import tldv_to_claims

        meeting = {
            "meeting_id": "meet_abc123",
            "name": "Daily 2026-04-21",
            "created_at": "2026-04-21T10:00:00Z",
            "updated_at": "2026-04-21T11:00:00Z",
            "url": "https://tldv.io/meetings/meet_abc123",
        }
        summaries = [
            {
                "meeting_id": "meet_abc123",
                "topics": ["API design", "Auth flow"],
                "decisions": [
                    "Usar JWT para autenticação",
                    "Migrar para PostgreSQL",
                ],
                "tags": ["backend"],
            }
        ]

        claims = tldv_to_claims(meeting, summaries)

        decision_claims = [c for c in claims if c.get("claim_type") == "decision"]
        assert len(decision_claims) == 2
        texts = {c["text"] for c in decision_claims}
        assert "Usar JWT para autenticação" in texts
        assert "Migrar para PostgreSQL" in texts

        for claim in decision_claims:
            assert claim["source"] == "tldv"
            assert claim["entity_type"] == "meeting"
            assert claim["entity_id"] == "meet_abc123"
            assert claim["needs_review"] is False
            assert "review_reason" not in claim

    def test_topics_regex_fallback_generates_low_confidence_decision(self):
        """When decisions array is absent/empty, scan topics with regex for decision language."""
        from vault.research.tldv_client import tldv_to_claims

        meeting = {
            "meeting_id": "meet_abc123",
            "name": "Daily 2026-04-21",
            "created_at": "2026-04-21T10:00:00Z",
            "url": "https://tldv.io/meetings/meet_abc123",
        }
        summaries = [
            {
                "meeting_id": "meet_abc123",
                "topics": [
                    "Decidimos usar JWT para autenticação",
                    "Discussão sobre banco de dados",
                ],
                "decisions": [],  # empty — triggers regex fallback
                "tags": [],
            }
        ]

        claims = tldv_to_claims(meeting, summaries)

        decision_claims = [c for c in claims if c.get("claim_type") == "decision"]
        # Only the topic with decision language should produce a claim
        assert len(decision_claims) == 1
        assert decision_claims[0]["text"] == "Decidimos usar JWT para autenticação"
        assert decision_claims[0]["confidence"] == 0.45
        assert decision_claims[0]["needs_review"] is True
        assert decision_claims[0]["review_reason"] == "regex_fallback"

    def test_missing_decisions_triggers_regex_fallback_with_correct_review_flags(self):
        """When decisions key is absent entirely, regex fallback still triggers correctly."""
        from vault.research.tldv_client import tldv_to_claims

        meeting = {
            "meeting_id": "meet_abc123",
            "name": "Daily",
            "created_at": "2026-04-21T10:00:00Z",
            "url": "https://tldv.io/meetings/meet_abc123",
        }
        # No 'decisions' key at all
        summaries = [
            {
                "meeting_id": "meet_abc123",
                "topics": ["Aprovado: usar Redis para cache"],
                "tags": [],
            }
        ]

        claims = tldv_to_claims(meeting, summaries)

        decision_claims = [c for c in claims if c.get("claim_type") == "decision"]
        assert len(decision_claims) == 1
        assert decision_claims[0]["confidence"] == 0.45
        assert decision_claims[0]["needs_review"] is True
        assert decision_claims[0]["review_reason"] == "regex_fallback"

    def test_topics_without_decision_language_produces_no_fallback_claim(self):
        """Topics without decision-like language produce no decision claims."""
        from vault.research.tldv_client import tldv_to_claims

        meeting = {
            "meeting_id": "meet_abc123",
            "name": "Daily",
            "created_at": "2026-04-21T10:00:00Z",
            "url": "https://tldv.io/meetings/meet_abc123",
        }
        summaries = [
            {
                "meeting_id": "meet_abc123",
                "topics": [
                    "Discussão sobre API design",
                    "Revisão de código",
                ],
                "decisions": [],
                "tags": [],
            }
        ]

        claims = tldv_to_claims(meeting, summaries)
        decision_claims = [c for c in claims if c.get("claim_type") == "decision"]
        assert len(decision_claims) == 0


class TestTLDVToClaimsCrossLinkage:
    """Tests for cross-linkage claims from enrichment context."""

    def test_cross_linkage_to_pr_uses_discusses_relation(self):
        """Linked PRs from enrichment_context produce linkage claims with relation=discusses."""
        from vault.research.tldv_client import tldv_to_claims

        meeting = {
            "meeting_id": "meet_abc123",
            "name": "Daily",
            "created_at": "2026-04-21T10:00:00Z",
            "url": "https://tldv.io/meetings/meet_abc123",
        }
        summaries = [{"meeting_id": "meet_abc123", "topics": [], "decisions": [], "tags": []}]
        enrichment_context = {
            "linked_prs": [
                {
                    "pr_url": "https://github.com/living/repo/pull/42",
                    "pr_number": 42,
                    "repo": "living/repo",
                    "title": "Add authentication",
                }
            ],
            "linked_cards": [],
            "related_meetings": [],
        }

        claims = tldv_to_claims(meeting, summaries, enrichment_context=enrichment_context)

        linkage_claims = [c for c in claims if c.get("claim_type") == "linkage"]
        assert len(linkage_claims) == 1
        pr_claim = linkage_claims[0]
        assert pr_claim["source"] == "tldv"
        assert pr_claim["metadata"]["relation"] == "discusses"
        assert pr_claim["metadata"]["link_type"] == "github_pr"
        assert "https://github.com/living/repo/pull/42" in pr_claim["text"]

    def test_cross_linkage_to_trello_card_uses_mentions_relation(self):
        """Linked Trello cards from enrichment_context produce linkage claims with relation=mentions."""
        from vault.research.tldv_client import tldv_to_claims

        meeting = {
            "meeting_id": "meet_abc123",
            "name": "Daily",
            "created_at": "2026-04-21T10:00:00Z",
            "url": "https://tldv.io/meetings/meet_abc123",
        }
        summaries = [{"meeting_id": "meet_abc123", "topics": [], "decisions": [], "tags": []}]
        enrichment_context = {
            "linked_prs": [],
            "linked_cards": [
                {
                    "card_id": "card_xyz",
                    "card_url": "https://trello.com/c/xyz",
                    "card_name": "Implement auth",
                }
            ],
            "related_meetings": [],
        }

        claims = tldv_to_claims(meeting, summaries, enrichment_context=enrichment_context)

        linkage_claims = [c for c in claims if c.get("claim_type") == "linkage"]
        assert len(linkage_claims) == 1
        card_claim = linkage_claims[0]
        assert card_claim["source"] == "tldv"
        assert card_claim["metadata"]["relation"] == "mentions"
        assert card_claim["metadata"]["link_type"] == "trello_card"
        assert "card_xyz" in card_claim["text"]

    def test_cross_linkage_to_related_meeting_uses_relates_to_relation(self):
        """Related meetings produce linkage claims with relation=relates_to."""
        from vault.research.tldv_client import tldv_to_claims

        meeting = {
            "meeting_id": "meet_abc123",
            "name": "Daily",
            "created_at": "2026-04-21T10:00:00Z",
            "url": "https://tldv.io/meetings/meet_abc123",
        }
        summaries = [{"meeting_id": "meet_abc123", "topics": [], "decisions": [], "tags": []}]
        enrichment_context = {
            "linked_prs": [],
            "linked_cards": [],
            "related_meetings": [
                {
                    "related_meeting_id": "meet_aaa",
                    "related_meeting_name": "Sprint Planning",
                }
            ],
        }

        claims = tldv_to_claims(meeting, summaries, enrichment_context=enrichment_context)

        linkage_claims = [c for c in claims if c.get("claim_type") == "linkage"]
        assert len(linkage_claims) == 1
        rel_claim = linkage_claims[0]
        assert rel_claim["metadata"]["relation"] == "relates_to"
        assert "meet_aaa" in rel_claim["text"]

    def test_all_three_linkage_types_together(self):
        """PR, Trello card, and related meeting all produce distinct linkage claims."""
        from vault.research.tldv_client import tldv_to_claims

        meeting = {
            "meeting_id": "meet_abc123",
            "name": "Daily",
            "created_at": "2026-04-21T10:00:00Z",
            "url": "https://tldv.io/meetings/meet_abc123",
        }
        summaries = [{"meeting_id": "meet_abc123", "topics": [], "decisions": [], "tags": []}]
        enrichment_context = {
            "linked_prs": [
                {"pr_url": "https://github.com/living/repo/pull/1", "pr_number": 1, "repo": "living/repo", "title": "PR 1"}
            ],
            "linked_cards": [
                {"card_id": "card_1", "card_url": "https://trello.com/c/1", "card_name": "Card 1"}
            ],
            "related_meetings": [
                {"related_meeting_id": "meet_aaa", "related_meeting_name": "Sprint Planning"}
            ],
        }

        claims = tldv_to_claims(meeting, summaries, enrichment_context=enrichment_context)

        linkage_claims = [c for c in claims if c.get("claim_type") == "linkage"]
        relations = {c["metadata"]["relation"] for c in linkage_claims}
        assert relations == {"discusses", "mentions", "relates_to"}


class TestTLDVToClaimsPreservesExistingBehavior:
    """Tests that tldv_to_claims preserves existing behavior for non-decision fields."""

    def test_meeting_without_summaries_produces_status_claim(self):
        """A meeting with no summaries at all still produces a status claim."""
        from vault.research.tldv_client import tldv_to_claims

        meeting = {
            "meeting_id": "meet_abc123",
            "name": "Daily",
            "created_at": "2026-04-21T10:00:00Z",
            "url": "https://tldv.io/meetings/meet_abc123",
        }

        claims = tldv_to_claims(meeting, [])

        status_claims = [c for c in claims if c.get("claim_type") == "status"]
        assert len(status_claims) == 1
        assert status_claims[0]["source"] == "tldv"
        assert status_claims[0]["entity_id"] == "meet_abc123"

    def test_summaries_with_tags_produce_tag_claims(self):
        """Summaries with tags produce tag claims (unchanged behavior)."""
        from vault.research.tldv_client import tldv_to_claims

        meeting = {
            "meeting_id": "meet_abc123",
            "name": "Daily",
            "created_at": "2026-04-21T10:00:00Z",
            "url": "https://tldv.io/meetings/meet_abc123",
        }
        summaries = [
            {
                "meeting_id": "meet_abc123",
                "topics": ["API design"],
                "decisions": [],
                "tags": ["backend", "security"],
            }
        ]

        claims = tldv_to_claims(meeting, summaries)

        tag_claims = [c for c in claims if c.get("claim_type") == "tag"]
        assert len(tag_claims) == 2
        tag_names = {c["metadata"]["tag"] for c in tag_claims}
        assert tag_names == {"backend", "security"}

    def test_decision_claim_has_correct_source_ref(self):
        """Decision claims include correct source_ref pointing to meeting."""
        from vault.research.tldv_client import tldv_to_claims

        meeting = {
            "meeting_id": "meet_abc123",
            "name": "Daily",
            "created_at": "2026-04-21T10:00:00Z",
            "url": "https://tldv.io/meetings/meet_abc123",
        }
        summaries = [
            {
                "meeting_id": "meet_abc123",
                "topics": [],
                "decisions": ["Decisão: usar JWT"],
                "tags": [],
            }
        ]

        claims = tldv_to_claims(meeting, summaries)

        decision_claim = [c for c in claims if c.get("claim_type") == "decision"][0]
        assert decision_claim["source_ref"]["source_id"] == "meet_abc123"
        assert decision_claim["source_ref"]["url"] == "https://tldv.io/meetings/meet_abc123"

    def test_decision_claim_uses_event_timestamp_from_meeting(self):
        """Decision claims use the meeting created_at as event_timestamp."""
        from vault.research.tldv_client import tldv_to_claims

        meeting = {
            "meeting_id": "meet_abc123",
            "name": "Daily",
            "created_at": "2026-04-21T10:00:00Z",
            "url": "https://tldv.io/meetings/meet_abc123",
        }
        summaries = [
            {
                "meeting_id": "meet_abc123",
                "topics": [],
                "decisions": ["Decisão: usar JWT"],
                "tags": [],
            }
        ]

        claims = tldv_to_claims(meeting, summaries)

        decision_claim = [c for c in claims if c.get("claim_type") == "decision"][0]
        assert decision_claim["event_timestamp"] == "2026-04-21T10:00:00Z"
