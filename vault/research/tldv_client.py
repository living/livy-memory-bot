"""TLDV polling client for research pipeline.

Uses Supabase REST to fetch meetings updated within lookback window.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
import re
from typing import Any

import requests

from vault.capture.azure_blob_client import load_transcript_segments

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_DAYS = 7

DECISION_KEYWORDS_PATTERN = re.compile(
    r"\b(?:decis[aã]o|decidid[oa]s?|decidimos|aprovad[oa]s?|definid[oa]s?|confirmad[oa]s?|vamos|deve(?:mos)?|agreed|approved|decided)\b",
    re.IGNORECASE,
)


class TLDVClient:
    """Client for polling TLDV meeting events from Supabase."""

    def __init__(
        self,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
    ) -> None:
        self.lookback_days = lookback_days
        self.supabase_url = (
            supabase_url if supabase_url is not None else os.environ.get("SUPABASE_URL", "")
        )
        self.supabase_key = (
            supabase_key if supabase_key is not None else os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        )

    def _transcript_clients(self) -> tuple[Any, Any]:
        """Lazy import transcript clients to keep module import-safe."""
        from vault.research.azure_blob_client import AzureBlobClient
        from vault.research.supabase_transcript import SupabaseTranscriptClient

        return (
            AzureBlobClient(),
            SupabaseTranscriptClient(
                supabase_url=self.supabase_url,
                supabase_key=self.supabase_key,
            ),
        )

    def fetch_events_since(self, last_seen_at: str | None) -> list[dict[str, Any]]:
        """Fetch normalized tldv:meeting events since last_seen_at."""
        if not self.supabase_url or not self.supabase_key:
            return []

        cutoff = self._compute_cutoff(last_seen_at)
        headers = self._headers()
        params: dict[str, Any] = {
            "select": "id,name,created_at,updated_at,meeting_id",
            "order": "updated_at.desc",
            "limit": 100,
        }
        params["updated_at"] = f"gte.{cutoff.isoformat()}"

        try:
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/meetings",
                headers=headers,
                params=params,
                timeout=30,
            )

            # Production schema fallback: some environments do not expose
            # meetings.updated_at (only created_at). Retry once with created_at.
            if resp.status_code == 400 and "updated_at" in (resp.text or ""):
                fallback_params = {
                    "select": "id,name,created_at",
                    "order": "created_at.desc",
                    "limit": 100,
                    "created_at": f"gte.{cutoff.isoformat().replace('+00:00', 'Z')}",
                }
                resp = requests.get(
                    f"{self.supabase_url}/rest/v1/meetings",
                    headers=headers,
                    params=fallback_params,
                    timeout=30,
                )

            if resp.status_code != 200:
                logger.warning(
                    "source=tldv status_code=%s url=%s",
                    resp.status_code,
                    self.supabase_url,
                )
                return []

            rows = resp.json() or []
            return [self._normalize_meeting(row) for row in rows]
        except requests.RequestException as exc:
            logger.warning(
                "source=tldv exception=%s url=%s",
                exc,
                self.supabase_url,
            )
            return []

    def fetch_meeting(self, meeting_id: str) -> dict[str, Any]:
        """Fetch one meeting by ID and normalize it."""
        normalized_meeting_id = (meeting_id or "").strip()
        if not self.supabase_url or not self.supabase_key or not normalized_meeting_id:
            return {}

        headers = self._headers()
        params = {
            "id": f"eq.{normalized_meeting_id}",
            "limit": 1,
        }

        try:
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/meetings",
                headers=headers,
                params=params,
                timeout=15,
            )
            if resp.status_code != 200:
                return {}
            rows = resp.json() or []
            if not rows:
                return {}
            return self._normalize_meeting(rows[0])
        except requests.RequestException:
            return {}

    def fetch_meeting_transcript(self, meeting_id: str) -> str | None:
        """Fetch transcript preferring Azure Blob, fallback to Supabase transcript fields."""
        normalized_meeting_id = (meeting_id or "").strip()
        if not normalized_meeting_id:
            return None

        azure_client, supabase_client = self._transcript_clients()
        transcript = azure_client.fetch_transcript(normalized_meeting_id)
        if transcript:
            return transcript

        return supabase_client.fetch_transcript(normalized_meeting_id)

    def fetch_summaries(self, meeting_id: str) -> list[dict[str, Any]]:
        """Fetch summaries rows for a given meeting_id."""
        normalized_meeting_id = (meeting_id or "").strip()
        if not self.supabase_url or not self.supabase_key or not normalized_meeting_id:
            return []

        headers = self._headers()
        params: dict[str, Any] = {
            "select": "meeting_id,topics,decisions,tags",
            "meeting_id": f"eq.{normalized_meeting_id}",
            "limit": 100,
        }

        try:
            resp = requests.get(
                f"{self.supabase_url}/rest/v1/summaries",
                headers=headers,
                params=params,
                timeout=15,
            )
            if resp.status_code != 200:
                return []
            rows = resp.json() or []
            return rows if isinstance(rows, list) else []
        except requests.RequestException:
            return []

    def fetch_enrichment_context(self, meeting_id: str) -> dict[str, list[dict[str, Any]]]:
        """Fetch enrichment link context: PRs, Trello cards, and related meetings."""
        normalized_meeting_id = (meeting_id or "").strip()
        empty = {"linked_prs": [], "linked_cards": [], "related_meetings": []}
        if not self.supabase_url or not self.supabase_key or not normalized_meeting_id:
            return empty

        headers = self._headers()

        def _fetch(path: str) -> list[dict[str, Any]]:
            try:
                resp = requests.get(
                    f"{self.supabase_url}/rest/v1/{path}",
                    headers=headers,
                    params={"meeting_id": f"eq.{normalized_meeting_id}", "limit": 100},
                    timeout=15,
                )
                if resp.status_code != 200:
                    return []
                rows = resp.json() or []
                return rows if isinstance(rows, list) else []
            except requests.RequestException:
                return []

        return {
            "linked_prs": _fetch("linked_prs"),
            "linked_cards": _fetch("linked_cards"),
            "related_meetings": _fetch("related_meetings"),
        }

    def load_transcript_segments(self, meeting_id: str) -> list[dict[str, Any]]:
        """Load structured transcript segments via vault.capture module.

        Tries Azure Blob first (two naming patterns), falls back to Supabase
        meetings table. Returns empty list for empty/missing meeting_id or when
        no source is available.
        """
        return load_transcript_segments(meeting_id)

    def _compute_cutoff(self, last_seen_at: str | None) -> datetime:
        if last_seen_at:
            return datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - timedelta(days=self.lookback_days)

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }

    def _normalize_meeting(self, row: dict[str, Any]) -> dict[str, Any]:
        meeting_id = row.get("id") or row.get("meeting_id")
        return {
            "source": "tldv",
            "event_type": "tldv:meeting",
            "meeting_id": meeting_id,
            "name": row.get("name"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "raw": row,
        }


def _is_decision_text(text: str) -> bool:
    return bool(DECISION_KEYWORDS_PATTERN.search((text or "").strip()))


def tldv_to_claims(
    meeting: dict[str, Any],
    summaries: list[dict[str, Any]],
    enrichment_context: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Generate normalized claims from TLDV meeting + summaries + enrichment links."""
    meeting_id = str(meeting.get("meeting_id") or meeting.get("id") or "")
    event_ts = str(meeting.get("updated_at") or meeting.get("created_at") or "")
    meeting_name = str(meeting.get("name") or f"Meeting {meeting_id}")
    source_ref = {
        "source_id": meeting_id,
        "url": meeting.get("url"),
    }

    claims: list[dict[str, Any]] = [
        {
            "source": "tldv",
            "claim_type": "status",
            "entity_type": "meeting",
            "entity_id": meeting_id,
            "text": meeting_name,
            "event_timestamp": event_ts,
            "source_ref": source_ref,
            "metadata": {"author": "system"},
        }
    ]

    for summary in summaries or []:
        tags = summary.get("tags", []) if isinstance(summary.get("tags"), list) else []
        for tag in tags:
            if not str(tag).strip():
                continue
            claims.append(
                {
                    "source": "tldv",
                    "claim_type": "tag",
                    "entity_type": "meeting",
                    "entity_id": meeting_id,
                    "text": f"Meeting tagged with '{tag}'",
                    "event_timestamp": event_ts,
                    "source_ref": source_ref,
                    "metadata": {"tag": str(tag)},
                }
            )

        decisions = summary.get("decisions") if isinstance(summary, dict) else None
        if isinstance(decisions, list) and any(str(d).strip() for d in decisions):
            for decision in decisions:
                decision_text = str(decision or "").strip()
                if not decision_text:
                    continue
                claims.append(
                    {
                        "source": "tldv",
                        "claim_type": "decision",
                        "entity_type": "meeting",
                        "entity_id": meeting_id,
                        "text": decision_text,
                        "event_timestamp": event_ts,
                        "source_ref": source_ref,
                        "metadata": {"source": "summaries.decisions"},
                        "needs_review": False,
                    }
                )
        else:
            topics = summary.get("topics", []) if isinstance(summary.get("topics"), list) else []
            for topic in topics:
                topic_text = str(topic or "").strip()
                if not topic_text or not _is_decision_text(topic_text):
                    continue
                claims.append(
                    {
                        "source": "tldv",
                        "claim_type": "decision",
                        "entity_type": "meeting",
                        "entity_id": meeting_id,
                        "text": topic_text,
                        "event_timestamp": event_ts,
                        "source_ref": source_ref,
                        "metadata": {"source": "summaries.topics"},
                        "confidence": 0.45,
                        "needs_review": True,
                        "review_reason": "regex_fallback",
                    }
                )

    context = enrichment_context or {}

    for pr in context.get("linked_prs", []) if isinstance(context.get("linked_prs"), list) else []:
        pr_url = str(pr.get("pr_url") or pr.get("url") or "").strip()
        pr_ref = str(pr.get("repo") or pr.get("pr_number") or pr_url).strip()
        if not (pr_url or pr_ref):
            continue
        claims.append(
            {
                "source": "tldv",
                "claim_type": "linkage",
                "entity_type": "meeting",
                "entity_id": meeting_id,
                "text": f"Meeting discusses PR {pr_url or pr_ref}",
                "event_timestamp": event_ts,
                "source_ref": source_ref,
                "metadata": {
                    "relation": "discusses",
                    "link_type": "github_pr",
                    "ref": pr_ref,
                    "url": pr_url,
                },
            }
        )

    for card in context.get("linked_cards", []) if isinstance(context.get("linked_cards"), list) else []:
        card_id = str(card.get("card_id") or "").strip()
        card_url = str(card.get("card_url") or card.get("url") or "").strip()
        card_ref = card_id or card_url
        if not card_ref:
            continue
        claims.append(
            {
                "source": "tldv",
                "claim_type": "linkage",
                "entity_type": "meeting",
                "entity_id": meeting_id,
                "text": f"Meeting mentions Trello card {card_ref}",
                "event_timestamp": event_ts,
                "source_ref": source_ref,
                "metadata": {
                    "relation": "mentions",
                    "link_type": "trello_card",
                    "ref": card_ref,
                    "url": card_url,
                },
            }
        )

    for related in context.get("related_meetings", []) if isinstance(context.get("related_meetings"), list) else []:
        related_id = str(
            related.get("related_meeting_id")
            or related.get("meeting_id")
            or related.get("id")
            or ""
        ).strip()
        if not related_id:
            continue
        claims.append(
            {
                "source": "tldv",
                "claim_type": "linkage",
                "entity_type": "meeting",
                "entity_id": meeting_id,
                "text": f"Meeting relates to meeting {related_id}",
                "event_timestamp": event_ts,
                "source_ref": source_ref,
                "metadata": {
                    "relation": "relates_to",
                    "link_type": "meeting",
                    "ref": related_id,
                },
            }
        )

    return claims
