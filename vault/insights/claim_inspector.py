"""Claims-first weekly insights extraction with markdown fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from vault.research.state_store import load_state


WEEK_DAYS = 7
STATE_PATH = "state/identity-graph/state.json"


@dataclass
class InsightsContradiction:
    entity_id: str
    claim_type: str
    delta: float
    claim_old: dict[str, Any]
    claim_new: dict[str, Any]


@dataclass
class InsightsAlert:
    level: str
    message: str


@dataclass
class InsightsBundle:
    total: int
    by_source: dict[str, int]
    active: int
    superseded_total: int
    new_this_week: dict[str, int]
    superseded_this_week: list[dict[str, Any]]
    contradictions: list[InsightsContradiction]
    alerts: list[InsightsAlert]
    week_start: str
    week_end: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _week_cutoff(now: datetime | None = None) -> datetime:
    ref = now or _utc_now()
    return ref - timedelta(days=WEEK_DAYS)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _count_by_source(claims: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in claims:
        source = str(claim.get("source") or "unknown")
        counts[source] = counts.get(source, 0) + 1
    return counts


def _is_this_week(claim: dict[str, Any], cutoff: datetime) -> bool:
    dt = _parse_iso(claim.get("event_timestamp"))
    return bool(dt and dt >= cutoff)


def week_covered_by_claims(claims: list[dict[str, Any]], now: datetime | None = None) -> bool:
    """Return True when claims contain at least one event inside weekly window."""
    if not claims:
        return False
    cutoff = _week_cutoff(now)
    return any(_is_this_week(c, cutoff) for c in claims)


def _find_contradictions(active_claims: list[dict[str, Any]]) -> list[InsightsContradiction]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for claim in active_claims:
        if claim.get("claim_type") != "status":
            continue
        entity_id = str(claim.get("entity_id") or "")
        if not entity_id:
            continue
        grouped.setdefault(entity_id, []).append(claim)

    contradictions: list[InsightsContradiction] = []
    for entity_id, claims in grouped.items():
        if len(claims) < 2:
            continue

        def _sort_key(item: dict[str, Any]) -> datetime:
            return _parse_iso(item.get("event_timestamp")) or datetime.min.replace(tzinfo=timezone.utc)

        ordered = sorted(claims, key=_sort_key)
        oldest = ordered[0]
        newest = ordered[-1]

        old_conf = float(oldest.get("confidence") or 0.0)
        new_conf = float(newest.get("confidence") or 0.0)
        delta = abs(new_conf - old_conf)
        if delta > 0.3:
            contradictions.append(
                InsightsContradiction(
                    entity_id=entity_id,
                    claim_type="status",
                    delta=delta,
                    claim_old=oldest,
                    claim_new=newest,
                )
            )
    return contradictions


def _alerts_from_stats(by_source: dict[str, int], superseded_this_week: list[dict[str, Any]]) -> list[InsightsAlert]:
    alerts: list[InsightsAlert] = []
    trello_superseded = sum(1 for c in superseded_this_week if c.get("source") == "trello")
    if trello_superseded >= 3:
        alerts.append(InsightsAlert(level="warning", message=f"trello: {trello_superseded} supersessions esta semana (taxa elevada)"))
    if not by_source:
        alerts.append(InsightsAlert(level="warning", message="Nenhuma claim encontrada nas fontes analisadas."))
    return alerts


def extract_insights(claims: list[dict[str, Any]], now: datetime | None = None) -> InsightsBundle:
    ref_now = now or _utc_now()
    cutoff = _week_cutoff(ref_now)

    active = [c for c in claims if not c.get("superseded_by")]
    superseded = [c for c in claims if c.get("superseded_by")]

    active_this_week = [c for c in active if _is_this_week(c, cutoff)]
    superseded_this_week = [c for c in superseded if _is_this_week(c, cutoff)]

    by_source = _count_by_source(claims)
    new_this_week = _count_by_source(active_this_week)
    contradictions = _find_contradictions(active)
    alerts = _alerts_from_stats(by_source, superseded_this_week)

    return InsightsBundle(
        total=len(claims),
        by_source=by_source,
        active=len(active),
        superseded_total=len(superseded),
        new_this_week=new_this_week,
        superseded_this_week=superseded_this_week,
        contradictions=contradictions,
        alerts=alerts,
        week_start=cutoff.strftime("%Y-%m-%d"),
        week_end=ref_now.strftime("%Y-%m-%d"),
    )


def _parse_markdown_claim(path: Path) -> dict[str, Any] | None:
    """Best-effort parser for legacy claim markdown frontmatter files."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        return None

    meta: dict[str, Any] = {}
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")

    body = ""
    for line in lines:
        if line.strip() and not line.startswith("---") and not line.lower().startswith(("source:", "event_timestamp:", "entity_id:", "claim_type:", "confidence:", "superseded_by:", "claim_id:")):
            body = line.strip()
            break

    claim_id = meta.get("claim_id") or path.stem
    source = meta.get("source") or "unknown"
    event_timestamp = meta.get("event_timestamp") or meta.get("created_at")

    try:
        confidence = float(meta.get("confidence", 0.0))
    except Exception:
        confidence = 0.0

    return {
        "claim_id": claim_id,
        "entity_type": meta.get("entity_type") or "topic",
        "entity_id": meta.get("entity_id") or claim_id,
        "topic_id": meta.get("topic_id"),
        "claim_type": meta.get("claim_type") or "status",
        "text": body or meta.get("text") or path.stem,
        "source": source,
        "source_ref": {"source_id": meta.get("source_id") or claim_id, "url": meta.get("url")},
        "evidence_ids": [meta.get("evidence_id") or claim_id],
        "author": meta.get("author") or "unknown",
        "event_timestamp": event_timestamp,
        "ingested_at": meta.get("ingested_at") or event_timestamp or _utc_now().isoformat(),
        "confidence": confidence,
        "privacy_level": meta.get("privacy_level") or "internal",
        "superseded_by": meta.get("superseded_by") or None,
        "supersession_reason": meta.get("supersession_reason"),
        "supersession_version": None,
        "audit_trail": None,
    }


def _load_markdown_claims(claims_dir: Path) -> list[dict[str, Any]]:
    if not claims_dir.exists():
        return []
    claims: list[dict[str, Any]] = []
    for path in sorted(claims_dir.glob("*.md")):
        try:
            parsed = _parse_markdown_claim(path)
            if parsed:
                claims.append(parsed)
        except Exception:
            continue
    return claims


def load_claims_with_fallback(
    state_path: str | Path = STATE_PATH,
    claims_dir: str | Path = "memory/vault/claims",
) -> tuple[list[dict[str, Any]], bool]:
    """Load SSOT claims, fallback to markdown when SSOT does not cover weekly window."""
    state = load_state(state_path)
    ssot_claims = list(state.get("claims") or [])

    if week_covered_by_claims(ssot_claims):
        return ssot_claims, False

    markdown_claims = _load_markdown_claims(Path(claims_dir))
    if markdown_claims:
        return markdown_claims, True

    return ssot_claims, False
