"""Wave C entity writer — persist canonical meeting/card entities to vault.

Provides idempotent upsert for meeting and card entities:
- Meeting:  memory/vault/entities/meeting-{slug}.md
- Card:     memory/vault/entities/card-{board_id}-{card_id}.md

True upsert semantics: skips write if entity already exists (idempotent).
Follows the same frontmatter+body pattern as upsert_decision/upsert_concept.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import yaml


def _slugify(text: str) -> str:
    """URL-safe slug from arbitrary string."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-") or "entity"


def _entity_path(vault_root: Path, entity: dict) -> Path:
    """Derive filesystem path for a canonical entity."""
    entities_dir = vault_root / "entities"
    id_canonical = entity.get("id_canonical", "")

    if id_canonical.startswith("meeting:"):
        slug = _slugify(id_canonical.replace("meeting:", ""))
        return entities_dir / f"meeting-{slug}.md"

    if id_canonical.startswith("person:"):
        slug = _slugify(id_canonical.replace("person:", ""))
        return entities_dir / f"person-{slug}.md"

    if id_canonical.startswith("card:"):
        # card:{board_id}:{card_id}
        rest = id_canonical.replace("card:", "")
        parts = rest.split(":", 1)
        if len(parts) == 2:
            board_slug = _slugify(parts[0])
            card_slug = _slugify(parts[1])
            return entities_dir / f"card-{board_slug}-{card_slug}.md"
        return entities_dir / f"card-{_slugify(rest)}.md"

    # Fallback: generic
    slug = _slugify(id_canonical.replace(":", "-"))
    return entities_dir / f"entity-{slug}.md"


def _render_sources_yaml_block(sources: list[dict]) -> list[str]:
    """Render sources list as YAML lines suitable for frontmatter."""
    if not sources:
        return ["sources: []"]

    dumped = yaml.safe_dump({"sources": sources}, sort_keys=False).strip()
    return dumped.splitlines()


def upsert_meeting(entity: dict, vault_root: Path | None = None) -> tuple[Path, bool]:
    """Write (or skip) a canonical meeting entity.

    Returns (path, written) where written=True if file was created,
    False if skipped (already exists — idempotent).
    """
    from vault.ingest.meeting_ingest import MAPPER_VERSION

    if vault_root is None:
        vault_root = Path(__file__).resolve().parents[2] / "memory" / "vault"

    path = _entity_path(vault_root, entity)

    if path.exists():
        return path, False

    entities_dir = vault_root / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)

    id_canonical = entity.get("id_canonical", "")
    title = entity.get("title", "")
    meeting_id_source = entity.get("meeting_id_source", "")
    started_at = entity.get("started_at", "")
    ended_at = entity.get("ended_at", "")
    project_ref = entity.get("project_ref")
    confidence = entity.get("confidence", "medium")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now_iso[:10]

    source_keys = entity.get("source_keys", [])
    source_ref = next((k for k in source_keys if k.startswith("tldv:")), "")
    mapper_version = entity.get("lineage", {}).get("mapper_version", MAPPER_VERSION)

    sources = entity.get("sources") or []
    if not sources and source_ref:
        sources = [{
            "source_type": "tldv_api",
            "source_ref": source_ref,
            "retrieved_at": now_iso,
            "mapper_version": mapper_version,
        }]

    # Frontmatter
    lines = [
        "---",
        f"entity: \"{title or id_canonical}\"",
        "type: meeting",
        f"id_canonical: {id_canonical}",
        f"meeting_id_source: {meeting_id_source}",
        f"confidence: {confidence}",
        f"first_seen_at: {now_iso}",
        f"last_seen_at: {now_iso}",
        f"mapper_version: {mapper_version}",
    ]
    if started_at:
        lines.append(f"started_at: {started_at}")
    if ended_at:
        lines.append(f"ended_at: {ended_at}")
    if project_ref:
        lines.append(f"project_ref: {project_ref}")
    lines.append("source_keys:")
    if isinstance(source_keys, list) and source_keys:
        for key in source_keys:
            lines.append(f"  - {key}")
    else:
        lines.append("  - tldv:unknown")
    lines.extend(_render_sources_yaml_block(sources))
    lines.extend([
        "last_verified: " + today,
        "verification_log: []",
        "last_touched_by: livy-agent",
        "draft: false",
        "---",
        "",
        f"# {title or id_canonical}",
        "",
    ])

    if source_ref:
        lines.append(f"**Fonte:** [{source_ref}]({source_ref})")
        lines.append("")

    lines.extend(["## Dados", ""])
    lines.append(f"- **Meeting ID:** `{meeting_id_source}`")
    if started_at:
        lines.append(f"- **Início:** {started_at}")
    if ended_at:
        lines.append(f"- **Término:** {ended_at}")
    if project_ref:
        lines.append(f"- **Projeto:** {project_ref}")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path, True


def upsert_person(entity: dict, vault_root: Path | None = None) -> tuple[Path, bool]:
    """Write (or skip) a canonical person entity.

    Returns (path, written) where written=True if file was created,
    False if skipped (already exists — idempotent).
    """
    if vault_root is None:
        vault_root = Path(__file__).resolve().parents[2] / "memory" / "vault"

    path = _entity_path(vault_root, entity)
    if path.exists():
        return path, False

    entities_dir = vault_root / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)

    id_canonical = entity.get("id_canonical", "")
    title = entity.get("display_name") or entity.get("entity") or id_canonical
    confidence = entity.get("confidence", "medium")
    source_keys = entity.get("source_keys", [])
    sources = entity.get("sources") or []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now_iso[:10]

    if not sources and source_keys:
        sources = [{
            "source_type": "tldv_api",
            "source_ref": source_keys[0],
            "retrieved_at": now_iso,
            "mapper_version": "external-ingest-person-v1",
        }]

    lines = [
        "---",
        f"entity: \"{title}\"",
        "type: person",
        f"id_canonical: {id_canonical}",
        f"confidence: {confidence}",
        f"first_seen_at: {entity.get('first_seen_at', now_iso)}",
        f"last_seen_at: {entity.get('last_seen_at', now_iso)}",
    ]

    if entity.get("github_login"):
        lines.append(f"github_login: {entity.get('github_login')}")
    if entity.get("email"):
        lines.append(f"email: {entity.get('email')}")

    lines.append("source_keys:")
    if isinstance(source_keys, list) and source_keys:
        for key in source_keys:
            lines.append(f"  - {key}")
    else:
        lines.append("  - tldv:participant:unknown")

    lines.extend(_render_sources_yaml_block(sources))
    lines.extend([
        "last_verified: " + today,
        "verification_log: []",
        "last_touched_by: livy-agent",
        "draft: false",
        "---",
        "",
        f"# {title}",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return path, True


def upsert_card(entity: dict, vault_root: Path | None = None) -> tuple[Path, bool]:
    """Write (or skip) a canonical card entity.

    Returns (path, written) where written=True if file was created,
    False if skipped (already exists — idempotent).
    """
    from vault.ingest.card_ingest import MAPPER_VERSION

    if vault_root is None:
        vault_root = Path(__file__).resolve().parents[2] / "memory" / "vault"

    path = _entity_path(vault_root, entity)

    if path.exists():
        return path, False

    entities_dir = vault_root / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)

    id_canonical = entity.get("id_canonical", "")
    title = entity.get("title", "")
    card_id_source = entity.get("card_id_source", "")
    board = entity.get("board", "")
    list_name = entity.get("list")
    project_ref = entity.get("project_ref")
    status = entity.get("status")
    confidence = entity.get("confidence", "medium")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now_iso[:10]

    source_keys = entity.get("source_keys", [])
    source_ref = next((k for k in source_keys if k.startswith("trello:")), "")
    mapper_version = entity.get("lineage", {}).get("mapper_version", MAPPER_VERSION)

    sources = entity.get("sources") or []
    if not sources and source_ref:
        sources = [{
            "source_type": "trello_api",
            "source_ref": source_ref,
            "retrieved_at": now_iso,
            "mapper_version": mapper_version,
        }]

    lines = [
        "---",
        f"entity: \"{title or id_canonical}\"",
        "type: card",
        f"id_canonical: {id_canonical}",
        f"card_id_source: {card_id_source}",
        f"confidence: {confidence}",
        f"first_seen_at: {now_iso}",
        f"last_seen_at: {now_iso}",
        f"mapper_version: {mapper_version}",
    ]
    if board:
        lines.append(f"board: {board}")
    if list_name:
        lines.append(f"list: {list_name}")
    if project_ref:
        lines.append(f"project_ref: {project_ref}")
    if status:
        lines.append(f"status: {status}")
    lines.append("source_keys:")
    if isinstance(source_keys, list) and source_keys:
        for key in source_keys:
            lines.append(f"  - {key}")
    else:
        lines.append("  - trello:unknown")
    lines.extend(_render_sources_yaml_block(sources))
    lines.extend([
        "last_verified: " + today,
        "verification_log: []",
        "last_touched_by: livy-agent",
        "draft: false",
        "---",
        "",
        f"# {title or id_canonical}",
        "",
    ])

    if source_ref:
        lines.append(f"**Fonte:** [{source_ref}]({source_ref})")
        lines.append("")

    lines.extend(["## Dados", ""])
    lines.append(f"- **Card ID:** `{card_id_source}`")
    if board:
        lines.append(f"- **Board:** {board}")
    if list_name:
        lines.append(f"- **Lista:** {list_name}")
    if project_ref:
        lines.append(f"- **Projeto:** {project_ref}")
    if status:
        lines.append(f"- **Status:** {status}")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path, True
