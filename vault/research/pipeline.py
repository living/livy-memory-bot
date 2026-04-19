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
from vault.research.state_store import DEFAULT_STATE, load_state, save_state, upsert_processed_event_key, upsert_processed_content_key
from vault.research.github_client import GitHubClient
from vault.research.github_rich_client import GitHubRichClient, extract_github_refs, extract_trello_urls
from vault.research.trello_client import TrelloClient
from vault.research.tldv_client import TLDVClient
from vault.research.cadence_manager import record_budget_warning, record_healthy_run
from vault.ops.rollback import is_wiki_v2_enabled


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
        }
        cache_path = self.research_dir / "state.json"
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

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
            elif self.source == "github":
                pr_number = event.get("pr_number")
                payload = client.fetch_pr(pr_number) if pr_number is not None else event
                repo = event.get("repo") or (payload.get("repo") if isinstance(payload, dict) else "") or ""
                if pr_number is not None and repo:
                    payload = rich_client.normalize_rich_event(pr_number, repo)
            else:
                payload = event  # Trello events are already normalized

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
