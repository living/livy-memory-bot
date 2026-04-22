"""Research pipeline core (v1) for TLDV, GitHub, and Trello."

Implements the 11-step pipeline in a minimal/YAGNI form:
1) State
2) Poll
3) Ingest
4) Dedupe
5) Context
6) Resolve
7) Hypothesize
8) Validate
9) Apply
10) Verify (audit evidence)
11) State persist

MVP self-healing mode is read-only: it only accumulates evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vault.research.event_key import build_event_key
from vault.research.identity_resolver import resolve_identity
from vault.research.state_store import (
    DEFAULT_STATE,
    DECISION_KEY_MIN_CONFIDENCE,
    load_state,
    save_state,
    upsert_processed_event_key,
    upsert_processed_content_key,
    upsert_processed_decision_key,
    upsert_processed_linkage_key,
)
from vault.research.github_client import GitHubClient
from vault.research.github_rich_client import GitHubRichClient, extract_github_refs, extract_trello_urls
from vault.research.github_parsers import pr_to_claims
from vault.research.trello_client import TrelloClient
from vault.research.trello_parsers import parse_trello_card, card_to_claims
from vault.research.tldv_client import TLDVClient, tldv_to_claims
from vault.research.cadence_manager import record_budget_warning, record_healthy_run
from vault.ops.rollback import is_wiki_v2_enabled
from vault.memory_core.models import Claim, SourceRef, AuditTrail
from vault.fusion_engine.engine import fuse


def _hash16(s: str) -> str:
    """Compute first 16 hex chars of SHA256 of a string."""
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _parse_ts_to_epoch(timestamp: str | None) -> int | None:
    """Parse ISO timestamp to Unix epoch seconds."""
    if not timestamp:
        return None
    try:
        # Handle both with and without 'Z' suffix
        ts = timestamp
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def build_trello_event_key(event: dict[str, Any]) -> str:
    """Build a collision-safe event_key for Trello events.

    Fallback hierarchy (first applicable):
    1. action_id (if present and non-empty)
    2. list_id + updated_at_ts (for card_created/card_updated)
    3. target_list_id + card_id + timestamp (for list_moved)
    4. member_id + timestamp (for member_added/member_removed)
    5. hash16(field1 + '_' + field2 + '_' + timestamp) — last resort

    Args:
        event: Normalized Trello event dict from TrelloClient

    Returns:
        A string event_key with no '::' separators (to avoid collision
        with the generic build_event_key format)
    """
    event_type = event.get("event_type", "")
    action_id = event.get("action_id")
    timestamp = event.get("timestamp") or event.get("date")
    ts_epoch = _parse_ts_to_epoch(timestamp)

    # 1. action_id if present and non-empty/non-whitespace
    if action_id and action_id.strip():
        return f"trello:{action_id}"

    # 2. list_id + updated_at_ts for card_created/card_updated
    if event_type in ("trello:card_created", "trello:card_updated"):
        list_id = event.get("list_id")
        if list_id and ts_epoch is not None:
            return f"{list_id}_{ts_epoch}"
        # Fall through to hash if list_id missing

    # 3. target_list_id + card_id + timestamp for list_moved
    if event_type == "trello:list_moved":
        target_list_id = event.get("target_list_id") or event.get("list_id")
        card_id = event.get("card_id")
        if target_list_id and card_id and ts_epoch is not None:
            return f"{target_list_id}_{card_id}_{ts_epoch}"
        # Fall through to hash if target_list_id or card_id missing

    # 4. member_id + timestamp for member_added/member_removed
    if event_type in ("trello:member_added", "trello:member_removed"):
        member_id = event.get("member_id")
        if member_id and ts_epoch is not None:
            return f"{member_id}_{ts_epoch}"
        # Fall through to hash if member_id missing

    # 5. Hash fallback: field1 + '_' + field2 + '_' + timestamp
    field1 = event.get("field1", event.get("list_id", ""))
    field2 = event.get("field2", event.get("card_id", ""))
    ts_str = timestamp or ""
    return _hash16(f"{field1}_{field2}_{ts_str}")


def get_claude_mem_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Placeholder context provider (patched in tests / replaced in production)."""
    return {"recent_sessions": [], "entities": [], "query": payload}


CROSS_SOURCE_IDENTITY_ENABLED = os.environ.get("CROSS_SOURCE_IDENTITY_ENABLED", "false").lower() == "true"


class ResearchPipeline:
    def __init__(
        self,
        source: str,
        state_path: str | Path,
        research_dir: str | Path,
        wiki_root: str | Path | None = None,
        allowed_paths: list[str] | None = None,
        read_only_mode: bool = False,
    ) -> None:
        if source not in {"tldv", "github", "trello"}:
            raise ValueError(f"unsupported source: {source}")

        self.source = source
        self.state_path = Path(state_path)
        self.research_dir = Path(research_dir)
        self.research_dir.mkdir(parents=True, exist_ok=True)
        self.wiki_root = Path(wiki_root) if wiki_root else Path("memory/vault")
        self.allowed_paths = [str(Path(p).resolve()) for p in (allowed_paths or ["memory/vault"])]
        self.read_only_mode = read_only_mode
        self.cross_source_identity_enabled = CROSS_SOURCE_IDENTITY_ENABLED

        self.audit_path = self.research_dir / "audit.log"
        self.self_healing_path = self.research_dir / "self_healing_evidence.jsonl"
        self.cadence_state_path = Path("state/identity-graph/cadence.json")

        self.state = load_state(self.state_path)
        self.last_seen_at = self._parse_iso(self.state.get("last_seen_at", {}).get(self.source))

        event_entries = self.state.get("processed_event_keys", {}).get(self.source, [])
        self.processed_event_keys = {
            item.get("key")
            for item in event_entries
            if isinstance(item, dict) and isinstance(item.get("key"), str)
        }

        content_entries = self.state.get("processed_content_keys", {}).get(self.source, [])
        self.processed_content_keys = {
            item.get("key")
            for item in content_entries
            if isinstance(item, dict) and isinstance(item.get("key"), str)
        }

        decision_entries = self.state.get("processed_decision_keys", {}).get(self.source, [])
        self.processed_decision_keys = {
            item.get("key")
            for item in decision_entries
            if isinstance(item, dict) and isinstance(item.get("key"), str)
        }

        linkage_entries = self.state.get("processed_linkage_keys", {}).get(self.source, [])
        self.processed_linkage_keys = {
            item.get("key")
            for item in linkage_entries
            if isinstance(item, dict) and isinstance(item.get("key"), str)
        }

    @staticmethod
    def _parse_iso(iso_value: str | None) -> datetime | None:
        if not iso_value:
            return None
        if iso_value.endswith("Z"):
            iso_value = iso_value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(iso_value)
        except ValueError:
            return None

    @staticmethod
    def _to_iso(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    def _event_at(self, event: dict[str, Any]) -> datetime:
        for field in ("event_at", "timestamp"):
            raw = event.get(field)
            if isinstance(raw, str):
                parsed = self._parse_iso(raw)
                if parsed is not None:
                    return parsed
        return datetime.now(timezone.utc)

    def _calculate_event_key(self, event: dict[str, Any]) -> str:
        if self.source == "trello":
            return build_trello_event_key(event)
        event_type = str(event.get("type", "event"))
        object_id = str(event.get("id") or event.get("meeting_id") or event.get("pr_number") or "unknown")
        return build_event_key(self.source, event_type, object_id)

    def _build_trello_hypothesis(self, event: dict[str, Any]) -> dict[str, Any]:
        """Build a hypothesis for a Trello event, with semantics per event type.

        contract:
          - trello:card_created  -> evidence markdown path (create_page)
          - trello:card_updated  -> upsert entity semantics
          - trello:list_moved   -> status transition old->new (captures both lists)
          - trello:member_added  -> identity reinforcement event
          - trello:member_removed -> soft unlink event (skip_apply)
        """
        event_type = event.get("event_type", "")
        event_key = self._calculate_event_key(event)
        card_id = event.get("card_id", "")
        list_id = event.get("list_id", "")
        target_list_id = event.get("target_list_id", "") or list_id
        member_id = event.get("member_id", "")
        member_name = event.get("member_name", "")
        card_name = event.get("card_name", "")
        timestamp = event.get("timestamp", "")
        board_id = event.get("board_id", "")

        base_path = str(self.research_dir / f"trello-{event_key}.md")
        card_entity_path = f"memory/vault/entities/cards/{card_id}.md" if card_id else base_path

        if event_type == "trello:card_created":
            content = (
                f"# Trello Card Created\n\n"
                f"- card_id: {card_id}\n"
                f"- card_name: {card_name}\n"
                f"- list_id: {list_id}\n"
                f"- board_id: {board_id}\n"
                f"- timestamp: {timestamp}\n"
                f"- event_key: {event_key}\n"
            )
            return {"action": "create_page", "path": card_entity_path, "content": content, "entity_type": "card"}

        elif event_type == "trello:card_updated":
            content = (
                f"# Trello Card Updated\n\n"
                f"- card_id: {card_id}\n"
                f"- card_name: {card_name}\n"
                f"- list_id: {list_id}\n"
                f"- board_id: {board_id}\n"
                f"- timestamp: {timestamp}\n"
                f"- event_key: {event_key}\n"
            )
            return {"action": "upsert_page", "path": card_entity_path, "content": content, "entity_type": "card"}

        elif event_type == "trello:list_moved":
            # Capture both source (old) list and target (new) list
            content = (
                f"# Trello Card Moved\n\n"
                f"- card_id: {card_id}\n"
                f"- card_name: {card_name}\n"
                f"- source_list_id: {list_id}\n"
                f"- target_list_id: {target_list_id}\n"
                f"- board_id: {board_id}\n"
                f"- timestamp: {timestamp}\n"
                f"- event_key: {event_key}\n"
            )
            return {"action": "create_page", "path": base_path, "content": content, "entity_type": "status_transition"}

        elif event_type == "trello:member_added":
            content = (
                f"# Trello Member Added\n\n"
                f"- member_id: {member_id}\n"
                f"- member_name: {member_name}\n"
                f"- card_id: {card_id}\n"
                f"- board_id: {board_id}\n"
                f"- timestamp: {timestamp}\n"
                f"- event_key: {event_key}\n"
            )
            return {
                "action": "create_page",
                "path": base_path,
                "content": content,
                "entity_type": "identity_reinforcement",
                "identities": [{"source": "trello", "identifier": member_id, "name": member_name}],
            }

        elif event_type == "trello:member_removed":
            content = (
                f"# Trello Member Removed (Soft Unlink)\n\n"
                f"- member_id: {member_id}\n"
                f"- member_name: {member_name}\n"
                f"- card_id: {card_id}\n"
                f"- board_id: {board_id}\n"
                f"- timestamp: {timestamp}\n"
                f"- event_key: {event_key}\n"
            )
            # Soft unlink: accumulate evidence but do not apply a new page
            return {
                "action": "unlink",
                "path": base_path,
                "content": content,
                "entity_type": "soft_unlink",
                "skip_apply": True,
                "identities": [{"source": "trello", "identifier": member_id, "name": member_name}],
            }

        else:
            content = (
                f"# Trello Event\n\n"
                f"- event_type: {event_type}\n"
                f"- card_id: {card_id}\n"
                f"- board_id: {board_id}\n"
                f"- timestamp: {timestamp}\n"
                f"- event_key: {event_key}\n"
            )
            return {"action": "create_page", "path": base_path, "content": content, "entity_type": "event"}

    def _compute_content_hash(self, content: str) -> str:
        """Compute deterministic SHA256 hex digest for content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _build_content_key(self, event: dict[str, Any], payload: dict[str, Any] | None = None) -> str:
        """Build semantic content key: {source}:{source_id}:{content_hash}."""
        source_id = str(
            event.get("pr_number")
            or event.get("meeting_id")
            or event.get("card_id")
            or event.get("id")
            or "unknown"
        )

        base_content: dict[str, Any] = payload if isinstance(payload, dict) else event
        canonical = json.dumps(base_content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        content_hash = self._compute_content_hash(canonical)
        return f"{self.source}:{source_id}:{content_hash}"

    def _build_decision_key(self, normalized_claim: dict[str, Any]) -> str:
        """Build decision key from a normalized claim dict.

        Decision key = SHA256 of (entity_id + claim.text), used for semantic
        deduplication of decision claims (confidence-gated at 0.7).
        """
        entity_id = str(normalized_claim.get("entity_id", ""))
        text = str(normalized_claim.get("text", ""))
        return f"decision:{self.source}:{entity_id}:{_hash16(text)}"

    def _build_linkage_key(self, normalized_claim: dict[str, Any]) -> str:
        """Build linkage key from a normalized claim dict.

        Linkage key = SHA256 of (entity_id + link_url), used for semantic
        deduplication of linkage claims (no confidence gate).
        """
        entity_id = str(normalized_claim.get("entity_id", ""))
        metadata = normalized_claim.get("metadata", {}) or {}
        link_url = str(metadata.get("link_url", ""))
        return f"linkage:{self.source}:{entity_id}:{_hash16(link_url)}"

    def _is_duplicate(self, event: dict[str, Any]) -> bool:
        return self._calculate_event_key(event) in self.processed_event_keys

    def _is_content_duplicate(self, event: dict[str, Any], payload: dict[str, Any] | None = None) -> bool:
        return self._build_content_key(event, payload) in self.processed_content_keys

    def _build_github_hypothesis(self, event: dict[str, Any]) -> dict[str, Any]:
        """Build a hypothesis for a rich GitHub PR event with crosslink relations."""
        event_key = self._calculate_event_key(event)
        pr_number = event.get("pr_number")
        repo = event.get("repo", "")

        # Collect text surfaces for crosslink extraction.
        text_parts: list[str] = [str(event.get("body") or "")]
        for collection_name in ("issue_comments", "review_comments", "reviews"):
            for item in event.get(collection_name, []) or []:
                if isinstance(item, dict):
                    text_parts.append(str(item.get("body") or ""))

        trello_urls: list[str] = []
        github_refs: list[str] = []
        for text in text_parts:
            trello_urls.extend(extract_trello_urls(text))
            github_refs.extend(extract_github_refs(text))

        # Dedupe while preserving order.
        trello_urls = list(dict.fromkeys(trello_urls))
        github_refs = list(dict.fromkeys(github_refs))

        relations: list[dict[str, Any]] = []
        for ref in github_refs:
            relation_type = "mentions"
            low = ref.lower()
            full_text = "\n".join(text_parts).lower()
            if "implements" in full_text or "fixes" in full_text or "closes" in full_text:
                relation_type = "implements"
            if "blocks" in full_text:
                relation_type = "blocks"
            relations.append({"type": relation_type, "target": ref, "source": f"{repo}#{pr_number}"})

        for url in trello_urls:
            relations.append({"type": "mentions", "target": url, "source": f"{repo}#{pr_number}"})

        for review in event.get("reviews", []) or []:
            if not isinstance(review, dict):
                continue
            reviewer = review.get("user", {}).get("login") if isinstance(review.get("user"), dict) else None
            if review.get("state"):
                relations.append({"type": "reviews", "target": reviewer, "state": review.get("state")})
            if str(review.get("state", "")).upper() == "APPROVED" and reviewer:
                relations.append({"type": "approved_by", "target": reviewer})

        content = (
            f"# GitHub PR Rich Event\n\n"
            f"- repo: {repo}\n"
            f"- pr_number: {pr_number}\n"
            f"- event_key: {event_key}\n"
            f"- trello_urls: {', '.join(trello_urls) if trello_urls else '-'}\n"
            f"- github_refs: {', '.join(github_refs) if github_refs else '-'}\n"
            f"- relations: {len(relations)}\n"
        )

        return {
            "action": "create_page",
            "path": str(self.research_dir / f"github-{event_key.replace(':', '-')}.md"),
            "content": content,
            "entity_type": "github_pr",
            "crosslinks": relations,
            "relations": relations,
        }

    def _build_context(self, payload: dict[str, Any]) -> dict[str, Any]:
        wiki: dict[str, str] = {}
        if self.wiki_root.exists():
            for md in self.wiki_root.glob("*.md"):
                try:
                    wiki[md.stem] = md.read_text(encoding="utf-8")
                except OSError:
                    continue

        fs_summary = {
            "research_dir": str(self.research_dir),
            "source": self.source,
        }

        return {
            "claude_mem": get_claude_mem_context(payload),
            "wiki": wiki,
            "fs": fs_summary,
        }

    def _resolve_entities(self, identities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in identities:
            out.append(
                resolve_identity(
                    source=item.get("source", self.source),
                    identifier=item.get("identifier", "unknown"),
                    email=item.get("email"),
                    username=item.get("username"),
                    name=item.get("name"),
                    candidates=item.get("candidates", []),
                )
            )
        return out

    def _validate(self, hypothesis: dict[str, Any]) -> dict[str, Any]:
        content = hypothesis.get("content")
        if not isinstance(content, str) or not content.strip():
            return {"approved": False, "reason": "quality gate: empty content"}

        # Minimal coherence rule for MVP
        if len(content.strip()) < 3:
            return {"approved": False, "reason": "coherence gate: content too short"}

        return {"approved": True, "reason": "ok"}

    def _is_path_allowed(self, path: str | Path) -> bool:
        target = Path(path).resolve()
        for allowed in self.allowed_paths:
            allowed_path = Path(allowed).resolve()
            try:
                target.relative_to(allowed_path)
                return True
            except ValueError:
                continue
        return False

    def _apply(self, hypotheses: list[dict[str, Any]]) -> dict[str, Any]:
        applied = 0
        rejected = 0

        for h in hypotheses:
            path = h.get("path")
            content = h.get("content", "")
            if not path or not self._is_path_allowed(path):
                rejected += 1
                continue

            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(str(content), encoding="utf-8")
            applied += 1

        return {"applied_count": applied, "rejected_count": rejected}

    def _log_audit(self, action: str, data: dict[str, Any]) -> None:
        rows: list[dict[str, Any]] = []
        if self.audit_path.exists():
            try:
                rows = json.loads(self.audit_path.read_text(encoding="utf-8"))
                if not isinstance(rows, list):
                    rows = []
            except json.JSONDecodeError:
                rows = []

        rows.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": self.source,
                "action": action,
                "data": data,
            }
        )
        self.audit_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def _persist_event_key(self, event: dict[str, Any]) -> None:
        event_key = self._calculate_event_key(event)
        event_at = self._event_at(event)
        upsert_processed_event_key(self.source, event_key, event_at, self.state_path)
        self.processed_event_keys.add(event_key)

    def _persist_content_key(self, event: dict[str, Any], payload: dict[str, Any] | None = None) -> str:
        """Compute and persist content_key. Returns the computed key."""
        content_key = self._build_content_key(event, payload)
        event_at = self._event_at(event)
        upsert_processed_content_key(self.source, content_key, event_at, self.state_path)
        self.processed_content_keys.add(content_key)
        return content_key

    def _advance_last_seen_at(self, event_at: datetime) -> None:
        state = load_state(self.state_path)
        current = self._parse_iso(state.get("last_seen_at", {}).get(self.source))

        if current is None or event_at > current:
            state.setdefault("last_seen_at", {})[self.source] = self._to_iso(event_at)
            save_state(state, self.state_path)
            self.last_seen_at = event_at

    def _accumulate_self_healing_evidence(self, evidence: dict[str, Any]) -> None:
        self.self_healing_path.parent.mkdir(parents=True, exist_ok=True)
        with self.self_healing_path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "source": self.source,
                        "evidence": evidence,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    def _apply_self_healing(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        for c in candidates:
            self._accumulate_self_healing_evidence(c)

        if self.read_only_mode:
            return {"mode": "read_only", "applied_count": 0}

        # MVP still no-op even when not read-only (future extension point)
        return {"mode": "no_op", "applied_count": 0}

    def _rebuild_source_cache_from_ssot(self) -> None:
        """Rebuild .research/<source>/state.json cache from SSOT state store."""
        ssot = load_state(self.state_path)
        cache = {
            "source": self.source,
            "version": ssot.get("version", 1),
            "last_seen_at": ssot.get("last_seen_at", {}).get(self.source),
            "processed_event_keys": ssot.get("processed_event_keys", {}).get(self.source, []),
            "processed_content_keys": ssot.get("processed_content_keys", {}).get(self.source, []),
            "processed_decision_keys": ssot.get("processed_decision_keys", {}).get(self.source, []),
            "processed_linkage_keys": ssot.get("processed_linkage_keys", {}).get(self.source, []),
        }
        cache_path = self.research_dir / "state.json"
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _normalize_claim_type(claim_type: str) -> str:
        allowed = {"status", "decision", "action_item", "risk", "ownership", "timeline_event", "linkage"}
        if claim_type in allowed:
            return claim_type
        return "timeline_event"

    @staticmethod
    def _normalize_entity_type(entity_type: str) -> str:
        if entity_type == "github_pr":
            return "pull_request"
        allowed = {
            "person", "project", "repository", "pull_request", "meeting", "topic", "decision", "email_thread"
        }
        if entity_type in allowed:
            return entity_type
        return "topic"

    def _claim_from_state_dict(self, raw: dict[str, Any]) -> Claim | None:
        try:
            src = raw.get("source_ref") or {}
            source_ref = SourceRef(
                source_id=str(src.get("source_id", "")),
                url=src.get("url"),
                blob_path=src.get("blob_path"),
            )
            audit_raw = raw.get("audit_trail") or {}
            audit = AuditTrail(
                model_used=str(audit_raw.get("model_used", "omniroute/fastest")),
                parser_version=str(audit_raw.get("parser_version", "v1")),
                trace_id=str(audit_raw.get("trace_id", "trace-missing")),
            )
            claim = Claim(
                claim_id=str(raw.get("claim_id")),
                entity_type=self._normalize_entity_type(str(raw.get("entity_type", "topic"))),
                entity_id=str(raw.get("entity_id", "unknown")),
                topic_id=raw.get("topic_id"),
                claim_type=self._normalize_claim_type(str(raw.get("claim_type", "timeline_event"))),
                text=str(raw.get("text", "")),
                source=str(raw.get("source", self.source)),
                source_ref=source_ref,
                evidence_ids=[str(e) for e in raw.get("evidence_ids", []) or []],
                author=str(raw.get("author", "system")),
                event_timestamp=str(raw.get("event_timestamp", datetime.now(timezone.utc).isoformat())),
                ingested_at=str(raw.get("ingested_at", datetime.now(timezone.utc).isoformat())),
                confidence=float(raw.get("confidence", 0.0) or 0.0),
                privacy_level=str(raw.get("privacy_level", "internal")),
                superseded_by=raw.get("superseded_by"),
                supersession_reason=raw.get("supersession_reason"),
                supersession_version=raw.get("supersession_version"),
                audit_trail=audit,
            )
            claim.validate()
            return claim
        except Exception:
            return None

    def _claim_to_state_dict(self, claim: Claim) -> dict[str, Any]:
        return {
            "claim_id": claim.claim_id,
            "entity_type": claim.entity_type,
            "entity_id": claim.entity_id,
            "topic_id": claim.topic_id,
            "claim_type": claim.claim_type,
            "text": claim.text,
            "source": claim.source,
            "source_ref": {
                "source_id": claim.source_ref.source_id,
                "url": claim.source_ref.url,
                "blob_path": claim.source_ref.blob_path,
            },
            "evidence_ids": claim.evidence_ids,
            "author": claim.author,
            "event_timestamp": claim.event_timestamp,
            "ingested_at": claim.ingested_at,
            "confidence": claim.confidence,
            "privacy_level": claim.privacy_level,
            "superseded_by": claim.superseded_by,
            "supersession_reason": claim.supersession_reason,
            "supersession_version": claim.supersession_version,
            "audit_trail": {
                "model_used": claim.audit_trail.model_used if claim.audit_trail else "omniroute/fastest",
                "parser_version": claim.audit_trail.parser_version if claim.audit_trail else "v1",
                "trace_id": claim.audit_trail.trace_id if claim.audit_trail else "trace-missing",
            } if claim.audit_trail else None,
        }

    def _new_claim_from_normalized(self, normalized: dict[str, Any], event_key: str, idx: int) -> Claim:
        source_ref_raw = normalized.get("source_ref") or {}
        source_ref = SourceRef(
            source_id=str(source_ref_raw.get("source_id", f"{event_key}:{idx}")),
            url=source_ref_raw.get("url"),
            blob_path=source_ref_raw.get("blob_path"),
        )
        metadata = normalized.get("metadata") if isinstance(normalized.get("metadata"), dict) else {}
        author = str(metadata.get("author") or normalized.get("author") or "system")
        event_ts = str(normalized.get("event_timestamp") or datetime.now(timezone.utc).isoformat())

        return Claim.new(
            entity_type=self._normalize_entity_type(str(normalized.get("entity_type", "topic"))),
            entity_id=str(normalized.get("entity_id", "unknown")),
            claim_type=self._normalize_claim_type(str(normalized.get("claim_type", "timeline_event"))),
            text=str(normalized.get("text", "")),
            source=str(normalized.get("source", self.source)),
            source_ref=source_ref,
            evidence_ids=[f"{event_key}:{idx}"],
            author=author,
            event_timestamp=event_ts,
            privacy_level=str(normalized.get("privacy_level", "internal")),
            topic_id=normalized.get("topic_id"),
            model_used="omniroute/fastest",
            parser_version="wiki-v2",
        )

    def _write_claim_blob(self, claim: Claim) -> str:
        claims_dir = self.wiki_root / "claims"
        claims_dir.mkdir(parents=True, exist_ok=True)
        claim_path = claims_dir / f"{claim.claim_id}.md"
        content = (
            f"# Claim {claim.claim_id}\n\n"
            f"- source: {claim.source}\n"
            f"- entity_type: {claim.entity_type}\n"
            f"- entity_id: {claim.entity_id}\n"
            f"- claim_type: {claim.claim_type}\n"
            f"- confidence: {claim.confidence:.3f}\n"
            f"- event_timestamp: {claim.event_timestamp}\n"
            f"- superseded_by: {claim.superseded_by or '-'}\n\n"
            f"## Text\n{claim.text}\n"
        )
        claim_path.write_text(content, encoding="utf-8")
        return str(claim_path)

    def _fuse_and_persist_normalized_claims(
        self,
        event: dict[str, Any],
        claims_normalized: list[dict[str, Any]],
    ) -> dict[str, Any]:
        state = load_state(self.state_path)
        claims_raw = list(state.get("claims", []))

        existing_claims: list[Claim] = []
        for raw in claims_raw:
            if isinstance(raw, dict):
                c = self._claim_from_state_dict(raw)
                if c is not None:
                    existing_claims.append(c)

        event_key = self._calculate_event_key(event)
        event_at = self._event_at(event)
        superseded_total = 0
        written = 0
        decision_keys_persisted = 0
        linkage_keys_persisted = 0

        for idx, normalized in enumerate(claims_normalized):
            new_claim = self._new_claim_from_normalized(normalized, event_key, idx)
            result = fuse(new_claim, existing_claims)

            for superseded in result.superseded_claims:
                superseded_total += 1
                for raw in claims_raw:
                    if isinstance(raw, dict) and raw.get("claim_id") == superseded.claim_id:
                        raw["superseded_by"] = superseded.superseded_by
                        raw["supersession_reason"] = superseded.supersession_reason
                        raw["supersession_version"] = superseded.supersession_version

            claims_raw.append(self._claim_to_state_dict(result.fused_claim))
            existing_claims.append(result.fused_claim)
            blob_path = self._write_claim_blob(result.fused_claim)

            claim_type = str(normalized.get("claim_type", "")).lower()
            if claim_type == "decision":
                decision_key = self._build_decision_key(normalized)
                confidence = float(getattr(result.fused_claim, "confidence", 0.0) or 0.0)
                if confidence >= DECISION_KEY_MIN_CONFIDENCE and decision_key not in self.processed_decision_keys:
                    upsert_processed_decision_key(
                        source=self.source,
                        decision_key=decision_key,
                        entity_id=str(normalized.get("entity_id", "")),
                        claim_id=str(result.fused_claim.claim_id),
                        confidence=confidence,
                        event_at=event_at,
                        state_path=self.state_path,
                    )
                    self.processed_decision_keys.add(decision_key)
                    decision_keys_persisted += 1
            elif claim_type == "linkage":
                linkage_key = self._build_linkage_key(normalized)
                if linkage_key not in self.processed_linkage_keys:
                    metadata = normalized.get("metadata", {}) or {}
                    upsert_processed_linkage_key(
                        source=self.source,
                        linkage_key=linkage_key,
                        entity_id=str(normalized.get("entity_id", "")),
                        source_entity_id=str(metadata.get("from_entity") or normalized.get("entity_id", "")),
                        target_entity_id=str(metadata.get("to_entity") or metadata.get("link_url", "")),
                        linkage_type=str(metadata.get("relation") or metadata.get("link_type") or "linkage"),
                        event_at=event_at,
                        state_path=self.state_path,
                    )
                    self.processed_linkage_keys.add(linkage_key)
                    linkage_keys_persisted += 1

            self._log_audit(
                "wiki_v2_claim_written",
                {
                    "claim_id": result.fused_claim.claim_id,
                    "blob_path": blob_path,
                    "entity_id": result.fused_claim.entity_id,
                    "claim_type": result.fused_claim.claim_type,
                },
            )
            written += 1

        state["claims"] = claims_raw
        save_state(state, self.state_path)
        return {
            "claims_written": written,
            "claims_superseded": superseded_total,
            "decision_keys_persisted": decision_keys_persisted,
            "linkage_keys_persisted": linkage_keys_persisted,
        }

    def _process_wiki_v2_github_event(self, event: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        pr_number = payload.get("pr_number") or event.get("pr_number")
        repo = payload.get("repo") or event.get("repo") or ""
        if pr_number is None or not repo:
            return {"claims_written": 0, "claims_superseded": 0}

        # Convert rich GitHub payload to normalized claims.
        # pr_to_claims expects GitHub API-like PR shape (number/base.repo/user/html_url).
        if isinstance(payload, dict) and isinstance(payload.get("base"), dict):
            pr_payload = payload
        else:
            pr_payload = {
                "number": pr_number,
                "title": payload.get("title") if isinstance(payload, dict) else "",
                "body": payload.get("body") if isinstance(payload, dict) else "",
                "state": payload.get("state") if isinstance(payload, dict) else "closed",
                "merged": payload.get("merged") if isinstance(payload, dict) else False,
                "merged_at": payload.get("merged_at") if isinstance(payload, dict) else None,
                "created_at": payload.get("created_at") if isinstance(payload, dict) else None,
                "base": {"repo": {"full_name": repo}},
                "html_url": f"https://github.com/{repo}/pull/{pr_number}",
                "user": payload.get("author") if isinstance(payload.get("author"), dict) else payload.get("user", {}) if isinstance(payload, dict) else {},
                "labels": payload.get("labels", []) if isinstance(payload, dict) else [],
                "milestone": payload.get("milestone") if isinstance(payload, dict) else None,
            }

        claims_normalized = pr_to_claims(pr_payload, payload.get("reviews", []) if isinstance(payload, dict) else [])
        return self._fuse_and_persist_normalized_claims(event, claims_normalized)

    def _process_wiki_v2_trello_event(self, event: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        card_id = str(event.get("card_id", ""))
        if not card_id:
            return {"claims_written": 0, "claims_superseded": 0}

        card_payload = {
            "id": card_id,
            "name": event.get("card_name", ""),
            "url": event.get("card_url", f"https://trello.com/c/{card_id}"),
            "idBoard": event.get("board_id", ""),
            "desc": str(payload.get("desc") or ""),
            "labels": payload.get("labels", []) if isinstance(payload.get("labels"), list) else [],
            "due": payload.get("due") or event.get("due_date"),
            "dateLastActivity": payload.get("dateLastActivity") or event.get("timestamp") or event.get("event_at"),
            "_comments": payload.get("_comments", []) if isinstance(payload.get("_comments"), list) else [],
            "_checklists": payload.get("_checklists", []) if isinstance(payload.get("_checklists"), list) else [],
        }
        list_name = str(event.get("list_name") or payload.get("list_name") or event.get("list_id") or "unknown")
        parsed = parse_trello_card(card_payload, list_name=list_name)
        claims_normalized = card_to_claims(parsed)
        return self._fuse_and_persist_normalized_claims(event, claims_normalized)

    def _process_wiki_v2_tldv_event(self, event: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        meeting_id = str(payload.get("meeting_id") or payload.get("id") or event.get("meeting_id") or "")
        if not meeting_id:
            return {"claims_written": 0, "claims_superseded": 0}

        # Reuse canonical TLDV claim extraction (status + decision + linkage)
        # from Task 5 implementation in tldv_client.py.
        summaries = payload.get("_summaries") if isinstance(payload.get("_summaries"), list) else []
        enrichment_context = payload.get("_enrichment_context") if isinstance(payload.get("_enrichment_context"), dict) else {}

        claims_normalized = tldv_to_claims(payload, summaries, enrichment_context)

        return self._fuse_and_persist_normalized_claims(event, claims_normalized)

    def run(self) -> dict[str, Any]:
        # WIKI_V2_ENABLED feature flag — gates wiki v2 behavior (Memory Core + Fusion Engine)
        self.wiki_v2_active = is_wiki_v2_enabled()
        self._log_audit("run_started", {
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "wiki_v2_active": self.wiki_v2_active,
        })

        if self.source == "tldv":
            client: Any = TLDVClient()
        elif self.source == "github":
            client = GitHubClient()
            rich_client = GitHubRichClient()
        else:  # trello
            client = TrelloClient()

        events = client.fetch_events_since(self.last_seen_at.isoformat() if self.last_seen_at else None)
        processed = 0
        skipped = 0

        for event in events:
            if self._is_duplicate(event):
                skipped += 1
                self._log_audit("event_skipped_duplicate", {"event_key": self._calculate_event_key(event)})
                continue

            # Step 5 context
            payload: dict[str, Any]
            if self.source == "tldv":
                meeting_id = event.get("meeting_id")
                payload = client.fetch_meeting(meeting_id) if meeting_id else event
                if meeting_id and isinstance(payload, dict):
                    # Enrich payload so wiki v2 TLDV path can generate decision/linkage claims.
                    summaries = client.fetch_summaries(meeting_id)
                    enrichment_context = client.fetch_enrichment_context(meeting_id)
                    payload["_summaries"] = summaries if isinstance(summaries, list) else []
                    payload["_enrichment_context"] = enrichment_context if isinstance(enrichment_context, dict) else {}
            elif self.source == "github":
                pr_number = event.get("pr_number")
                payload = client.fetch_pr(pr_number) if pr_number is not None else event
                repo = event.get("repo") or (payload.get("repo") if isinstance(payload, dict) else "") or ""
                if pr_number is not None and repo:
                    payload = rich_client.normalize_rich_event(pr_number, repo)
            else:
                payload = dict(event)  # Trello events are normalized; enrich with card details for wiki v2
                card_id = payload.get("card_id")
                if self.wiki_v2_active and card_id:
                    comments = client.get_card_comments(card_id)
                    checklists = client.get_card_checklists(card_id)
                    payload["_comments"] = comments if isinstance(comments, list) else []
                    payload["_checklists"] = checklists if isinstance(checklists, list) else []

            _ = self._build_context(payload)

            if self._is_content_duplicate(event, payload):
                skipped += 1
                self._log_audit(
                    "event_skipped_duplicate_content",
                    {
                        "event_key": self._calculate_event_key(event),
                        "content_key": self._build_content_key(event, payload),
                    },
                )
                continue

            # Step 6 resolve — Trello-specific identity extraction
            identities: list[dict[str, Any]] = []
            if self.source == "trello":
                member_id = event.get("member_id", "")
                if member_id:
                    identities.append(
                        {
                            "source": "trello",
                            "identifier": member_id,
                            "name": event.get("member_name", ""),
                            "candidates": [],
                        }
                    )
            elif self.source == "github":
                author = payload.get("author", {}) if isinstance(payload, dict) else {}
                if isinstance(author, dict):
                    identities.append(
                        {
                            "source": "github",
                            "identifier": str(author.get("login", "unknown")),
                            "email": author.get("email"),
                            "candidates": [],
                        }
                    )
            self._resolve_entities(identities)

            # Step 7/8/9 hypothesis flow
            if self.source == "trello":
                hypothesis = self._build_trello_hypothesis(event)
            elif self.source == "github":
                github_payload = payload if isinstance(payload, dict) else {}
                has_rich_data = any(
                    bool(github_payload.get(field))
                    for field in ("body", "reviews", "issue_comments", "review_comments", "linked_issues")
                )
                if has_rich_data:
                    hypothesis = self._build_github_hypothesis(github_payload)
                else:
                    hypothesis = {
                        "action": "create_page",
                        "path": str(self.research_dir / f"evidence-{self._calculate_event_key(event).replace(':', '-')}.md"),
                        "content": (
                            "# Evidence\n\n"
                            f"source={self.source}\n"
                            f"event_key={self._calculate_event_key(event)}\n"
                            "note=github event without rich payload; skipped github hypothesis build\n"
                        ),
                        "entity_type": "event",
                        "skip_apply": True,
                    }
            else:
                hypothesis = {
                    "action": "create_page",
                    "path": str(self.research_dir / f"evidence-{self._calculate_event_key(event).replace(':', '-')}.md"),
                    "content": f"# Evidence\n\nsource={self.source}\nevent_key={self._calculate_event_key(event)}\n",
                    "entity_type": "event",
                }

            if self.wiki_v2_active:
                v2_stats = {"claims_written": 0, "claims_superseded": 0}
                if self.source == "github" and isinstance(payload, dict):
                    v2_stats = self._process_wiki_v2_github_event(event, payload)
                elif self.source == "trello":
                    v2_stats = self._process_wiki_v2_trello_event(event, payload)
                elif self.source == "tldv" and isinstance(payload, dict):
                    v2_stats = self._process_wiki_v2_tldv_event(event, payload)

                self._log_audit("wiki_v2_event_processed", {
                    "event_key": self._calculate_event_key(event),
                    **v2_stats,
                })
            else:
                validation = self._validate(hypothesis)
                skip_apply = hypothesis.get("skip_apply", False)
                if validation.get("approved") and self._is_path_allowed(hypothesis["path"]) and not skip_apply:
                    self._apply([hypothesis])

            # Step 10/11
            self._persist_event_key(event)
            content_key = self._persist_content_key(event, payload)
            self._advance_last_seen_at(self._event_at(event))
            self._log_audit(
                "event_processed",
                {
                    "event_key": self._calculate_event_key(event),
                    "content_key": content_key,
                },
            )
            processed += 1

        # self-healing MVP (read-only evidence)
        self._apply_self_healing([])

        # Cadence integration (global): use API/event volume as budget-pressure
        # signal for now; high-volume runs push cadence to safer interval.
        if len(events) >= 100:
            record_budget_warning(self.cadence_state_path)
        else:
            record_healthy_run(self.cadence_state_path)

        self._rebuild_source_cache_from_ssot()
        self._log_audit("run_finished", {"events_processed": processed, "events_skipped": skipped})

        return {
            "status": "success",
            "events_processed": processed,
            "events_skipped": skipped,
            "token_used": 0,
            "token_budget": 0,
            "api_calls": len(events),
            "api_cost_usd_estimate": 0.0,
            "cost_usd_estimate": 0.0,
            "source": self.source,
        }
