"""
Replay determinístico: regenera estado a partir de raw events (spec Section 9.5).

Executar:
    python vault/ops/replay_pipeline.py --since=2026-04-19T00:00:00Z
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vault.memory_core.models import Claim, SourceRef, AuditTrail
from vault.fusion_engine.engine import fuse


def _stable_claim_id(event: dict) -> str:
    """Derive a deterministic claim_id from event content for reproducible replay."""
    payload = json.dumps(event, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(payload.encode()).hexdigest()[:32]


def replay_events(
    audit_log_path: Path,
    since: datetime,
    state_path: Path,
) -> dict[str, int]:
    """Replay all events since `since` and return replay stats."""
    all_events_raw: list[tuple[int, dict]] = []
    for idx, line in enumerate(audit_log_path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        all_events_raw.append((idx, json.loads(line)))

    processed = 0
    errors = 0
    for idx, event in all_events_raw:
        try:
            event_at_str = event.get("event_at", "")
            if not event_at_str:
                errors += 1
                continue
            event_time = datetime.fromisoformat(event_at_str.replace("Z", "+00:00"))
            if event_time < since:
                continue
            existing_state = _load_state(state_path)
            existing_claims = _load_claims_from_state(existing_state)
            new_claim = _event_to_claim(event)
            result = fuse(new_claim, existing_claims)
            _persist_fusion_result(state_path, result, existing_state)
            processed += 1
        except Exception:
            errors += 1

    return {"processed": processed, "errors": errors, "total": len(all_events_raw)}


def _load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"claims": []}
    return json.loads(state_path.read_text(encoding="utf-8"))


def _load_claims_from_state(state: dict) -> list[Claim]:
    """Convert state dict claims into Claim objects."""
    claims = []
    for raw in state.get("claims", []):
        try:
            src = raw.get("source_ref") or {}
            source_ref = SourceRef(
                source_id=src.get("source_id", ""),
                url=src.get("url"),
                blob_path=src.get("blob_path"),
            )
            audit = raw.get("audit_trail")
            audit_trail = None
            if audit:
                audit_trail = AuditTrail(
                    model_used=audit.get("model_used", ""),
                    parser_version=audit.get("parser_version", ""),
                    trace_id=audit.get("trace_id", ""),
                )
            claim = Claim(
                claim_id=raw["claim_id"],
                entity_type=raw["entity_type"],
                entity_id=raw["entity_id"],
                topic_id=raw.get("topic_id"),
                claim_type=raw["claim_type"],
                text=raw["text"],
                source=raw["source"],
                source_ref=source_ref,
                evidence_ids=raw.get("evidence_ids", []),
                author=raw["author"],
                event_timestamp=raw["event_timestamp"],
                ingested_at=raw.get("ingested_at", ""),
                confidence=raw.get("confidence", 0.0),
                privacy_level=raw.get("privacy_level", "internal"),
                superseded_by=raw.get("superseded_by"),
                supersession_reason=raw.get("supersession_reason"),
                supersession_version=raw.get("supersession_version"),
                audit_trail=audit_trail,
            )
            claims.append(claim)
        except Exception:
            continue
    return claims


def _persist_fusion_result(state_path: Path, result, existing_state: dict) -> None:
    """Persist fusion result to state file."""
    new_claims = existing_state.get("claims", [])
    for superseded in result.superseded_claims:
        for raw in new_claims:
            if raw.get("claim_id") == superseded.claim_id:
                raw["superseded_by"] = superseded.superseded_by
                raw["supersession_reason"] = superseded.supersession_reason
                raw["supersession_version"] = superseded.supersession_version
    new_claims.append(_claim_to_dict(result.fused_claim))
    existing_state["claims"] = new_claims
    state_path.write_text(json.dumps(existing_state, indent=2, ensure_ascii=False), encoding="utf-8")


def _claim_to_dict(claim: Claim) -> dict:
    """Convert Claim to serializable dict."""
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
            "model_used": claim.audit_trail.model_used if claim.audit_trail else "",
            "parser_version": claim.audit_trail.parser_version if claim.audit_trail else "",
            "trace_id": claim.audit_trail.trace_id if claim.audit_trail else "",
        } if claim.audit_trail else None,
    }


def _event_to_claim(event: dict) -> Claim:
    """Converte evento do audit log em Claim para replay."""
    source_ref = SourceRef(
        source_id=str(event.get("id", "unknown")),
        url=event.get("url"),
        blob_path=event.get("blob_path"),
    )
    audit_trail = AuditTrail(
        model_used=event.get("model_used", "replay"),
        parser_version=event.get("parser_version", "v1"),
        trace_id=f"replay-{event.get('id', 'unknown')}",
    )
    claim_id = _stable_claim_id(event)
    event_at = event.get("event_at", datetime.now(timezone.utc).isoformat())
    # Use event_at as ingested_at for deterministic replay
    return Claim(
        claim_id=claim_id,
        entity_type=event.get("entity_type", "topic"),
        entity_id=str(event.get("entity_id", "unknown")),
        topic_id=event.get("topic_id"),
        claim_type=event.get("claim_type", "timeline_event"),
        text=str(event.get("text", "replayed event")),
        source=event.get("source", "github"),
        source_ref=source_ref,
        evidence_ids=[str(event.get("evidence_id", "replay-evidence"))],
        author=str(event.get("author", "system")),
        event_timestamp=event_at,
        ingested_at=event_at,
        confidence=0.0,
        privacy_level=event.get("privacy_level", "internal"),
        superseded_by=None,
        supersession_reason=None,
        supersession_version=None,
        audit_trail=audit_trail,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay pipeline events")
    parser.add_argument("--since", required=True, help="ISO 8601 timestamp")
    parser.add_argument("--audit-log", default="state/audit.log", help="Audit log path")
    parser.add_argument("--state", default="state/identity-graph/state.json")
    args = parser.parse_args()

    since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
    stats = replay_events(Path(args.audit_log), since, Path(args.state))
    print(f"Replay: {stats['processed']}/{stats['total']} events OK, {stats['errors']} errors")


if __name__ == "__main__":
    main()
