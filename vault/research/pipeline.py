"""Research pipeline core (v1) for TLDV and GitHub.

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

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vault.research.event_key import build_event_key
from vault.research.identity_resolver import resolve_identity
from vault.research.state_store import load_state, save_state, upsert_processed_event_key


def get_claude_mem_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Placeholder context provider (patched in tests / replaced in production)."""
    return {"recent_sessions": [], "entities": [], "query": payload}


class TLDVClient:
    """Minimal placeholder client (patched in tests)."""

    def fetch_events_since(self, last_seen_at: str | None) -> list[dict[str, Any]]:
        return []

    def fetch_meeting(self, meeting_id: str) -> dict[str, Any]:
        return {"id": meeting_id}


class GitHubClient:
    """Minimal placeholder client (patched in tests)."""

    def fetch_events_since(self, last_seen_at: str | None) -> list[dict[str, Any]]:
        return []

    def fetch_pr(self, pr_number: int) -> dict[str, Any]:
        return {"number": pr_number}


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
        if source not in {"tldv", "github"}:
            raise ValueError(f"unsupported source: {source}")

        self.source = source
        self.state_path = Path(state_path)
        self.research_dir = Path(research_dir)
        self.research_dir.mkdir(parents=True, exist_ok=True)
        self.wiki_root = Path(wiki_root) if wiki_root else Path("memory/vault")
        self.allowed_paths = [str(Path(p).resolve()) for p in (allowed_paths or ["memory/vault"])]
        self.read_only_mode = read_only_mode

        self.audit_path = self.research_dir / "audit.log"
        self.self_healing_path = self.research_dir / "self_healing_evidence.jsonl"

        self.state = load_state(self.state_path)
        self.last_seen_at = self._parse_iso(self.state.get("last_seen_at", {}).get(self.source))

        entries = self.state.get("processed_event_keys", {}).get(self.source, [])
        self.processed_event_keys = {
            item.get("key")
            for item in entries
            if isinstance(item, dict) and isinstance(item.get("key"), str)
        }

    @staticmethod
    def _parse_iso(iso_value: str | None) -> datetime | None:
        if not iso_value:
            return None
        if iso_value.endswith("Z"):
            iso_value = iso_value.replace("Z", "+00:00")
        return datetime.fromisoformat(iso_value)

    @staticmethod
    def _to_iso(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    def _event_at(self, event: dict[str, Any]) -> datetime:
        raw = event.get("event_at")
        if isinstance(raw, str):
            parsed = self._parse_iso(raw)
            if parsed is not None:
                return parsed
        return datetime.now(timezone.utc)

    def _calculate_event_key(self, event: dict[str, Any]) -> str:
        event_type = str(event.get("type", "event"))
        object_id = str(event.get("id") or event.get("meeting_id") or event.get("pr_number") or "unknown")
        return build_event_key(self.source, event_type, object_id)

    def _is_duplicate(self, event: dict[str, Any]) -> bool:
        return self._calculate_event_key(event) in self.processed_event_keys

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
        }
        cache_path = self.research_dir / "state.json"
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    def run(self) -> dict[str, Any]:
        self._log_audit("run_started", {"last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None})

        if self.source == "tldv":
            client: Any = TLDVClient()
        else:
            client = GitHubClient()

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
            else:
                pr_number = event.get("pr_number")
                payload = client.fetch_pr(pr_number) if pr_number is not None else event

            _ = self._build_context(payload)

            # Step 6 resolve (minimal identity extraction)
            identities: list[dict[str, Any]] = []
            if self.source == "github":
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

            # Step 7/8/9 minimal hypothesis flow
            hypothesis = {
                "action": "create_page",
                "path": str(self.research_dir / f"evidence-{self._calculate_event_key(event).replace(':', '-')}.md"),
                "content": f"# Evidence\n\nsource={self.source}\nevent_key={self._calculate_event_key(event)}\n",
                "entity_type": "event",
            }
            validation = self._validate(hypothesis)
            if validation.get("approved") and self._is_path_allowed(hypothesis["path"]):
                self._apply([hypothesis])

            # Step 10/11
            self._persist_event_key(event)
            self._advance_last_seen_at(self._event_at(event))
            self._log_audit("event_processed", {"event_key": self._calculate_event_key(event)})
            processed += 1

        # self-healing MVP (read-only evidence)
        self._apply_self_healing([])

        self._rebuild_source_cache_from_ssot()
        self._log_audit("run_finished", {"events_processed": processed, "events_skipped": skipped})

        return {
            "status": "success",
            "events_processed": processed,
            "events_skipped": skipped,
        }
