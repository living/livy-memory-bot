"""TLDV topic_ref ingestion → canonical project entities."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def topic_ref_to_project(topic_ref: str, run_id: str = "wave-b") -> dict[str, Any]:
    """Convert topic_ref into a canonical project payload."""
    slug = topic_ref.replace(".md", "").strip().lower()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    source_keys = [f"tldv:topic_ref:{slug}"]

    return {
        "id_canonical": f"project:{slug}",
        "slug": slug,
        "name": slug.replace("-", " ").title(),
        "status": "active",
        "aliases": [slug],
        "confidence": "medium",
        "lineage": {
            "run_id": run_id,
            "source_keys": source_keys,
            "transformed_at": now,
            "mapper_version": "wave-b-project-ingest-v1",
            "actor": "livy-agent",
        },
    }


def from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract unique topic_ref values from events and convert to projects."""
    seen: set[str] = set()
    projects: list[dict[str, Any]] = []
    for ev in events:
        topic_ref = ev.get("topic_ref")
        if not topic_ref:
            continue
        if topic_ref in seen:
            continue
        seen.add(topic_ref)
        projects.append(topic_ref_to_project(topic_ref))
    return projects
