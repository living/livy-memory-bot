"""Wave C entity writer — persist canonical meeting/card entities to vault.

Provides idempotent upsert for meeting and card entities:
- Meeting:  memory/vault/entities/meeting-{slug}.md
- Card:     memory/vault/entities/card-{board_id}-{card_id}.md

True upsert semantics: skips write if entity already exists (idempotent).
Follows the same frontmatter+body pattern as upsert_decision/upsert_concept.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown text into a dict."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    yaml_block = text[3:end].strip()
    body = text[end + 3:].lstrip("\n")
    fm = {}
    current_key = None
    current_list: list[str] | None = None
    for line in yaml_block.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- ") and current_list is not None:
            current_list.append(stripped[2:].strip('"').strip("'"))
            continue
        if ":" in stripped and not stripped.startswith("-"):
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val == "":
                current_list = []
                fm[key] = current_list
            else:
                current_list = None
                fm[key] = val
            current_key = key
        else:
            current_list = None
    return fm, body


def _join_frontmatter(fm: dict, body: str) -> str:
    """Serialize frontmatter dict + body back to markdown."""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f'{k}: "{v}"' if isinstance(v, str) and (" " in str(v) or ":" in str(v)) else f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)

import yaml


def _slugify(text: str) -> str:
    """Human-readable, filesystem-safe slug. Keeps accented chars, spaces, dots."""
    text = text.strip()
    # Replace slashes with dashes FIRST (before regex removes them)
    text = text.replace('/', ' - ')
    # Remove characters unsafe for filenames, but keep spaces, accents, dots, parentheses, dashes
    text = re.sub(r'[<>:"\\|?*\x00-\x1f]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text or "entity"


def _entity_path(vault_root: Path, entity: dict) -> Path:
    """Derive human-readable filesystem path for a canonical entity.

    Person → "Lincoln Quinan Junior.md"
    Meeting → "2026-02-20 Daily Operações B3.md"
    Card → "card-{board}-{title}.md"
    """
    entities_dir = vault_root / "entities"
    id_canonical = entity.get("id_canonical", "")

    if id_canonical.startswith("meeting:"):
        # Use date + title for human-readable filename
        started = entity.get("started_at", "")
        date_part = started[:10] if started else ""
        title = entity.get("title") or entity.get("entity") or id_canonical.replace("meeting:", "")
        slug = _slugify(title)
        if date_part:
            return entities_dir / f"{date_part} {slug}.md"
        return entities_dir / f"{slug}.md"

    if id_canonical.startswith("person:"):
        # Use the person's name directly
        name = entity.get("display_name") or entity.get("entity") or id_canonical.replace("person:", "")
        return entities_dir / f"{_slugify(name)}.md"

    if id_canonical.startswith("card:"):
        rest = id_canonical.replace("card:", "")
        parts = rest.split(":", 1)
        if len(parts) == 2:
            return entities_dir / f"card-{_slugify(parts[0])}-{_slugify(parts[1])}.md"
        return entities_dir / f"card-{_slugify(rest)}.md"

    # Fallback
    return entities_dir / f"{_slugify(id_canonical)}.md"


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

    # Participants section with wiki-links
    participants = entity.get("_participants", [])
    if participants:
        lines.append("## Participantes")
        lines.append("")
        for p in participants:
            pname = p.get("name", "?")
            lines.append(f"- [[{_slugify(pname)}]]")
        lines.append("")

    lines.extend(["## Metadados", ""])
    lines.append(f"- **ID:** `{meeting_id_source}`")
    if started_at:
        lines.append(f"- **Início:** {started_at}")
    if ended_at:
        lines.append(f"- **Término:** {ended_at}")
    if project_ref:
        lines.append(f"- **Projeto:** {project_ref}")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path, True


def _find_existing_person_fuzzy(entities_dir: Path, name: str) -> Path | None:
    """Search existing person files for a fuzzy name match.

    Returns the path of the best matching existing person, or None.
    """
    from vault.ingest.meeting_ingest import _is_name_prefix, _fuzzy_name_key, _pick_richer_name
    target_key = _fuzzy_name_key(name)
    target_words = target_key.split()
    best_match = None
    best_match_words = 0

    for f in entities_dir.glob("person-*.md"):
        # Read just the first line with entity: to get the name
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.split("\n"):
            if line.startswith("entity:"):
                existing_name = line.split(":", 1)[1].strip().strip('"')
                existing_key = _fuzzy_name_key(existing_name)
                if existing_key == target_key or _is_name_prefix(target_key, existing_key) or _is_name_prefix(existing_key, target_key):
                    ew = len(existing_key.split())
                    if best_match is None or ew > best_match_words:
                        best_match = f
                        best_match_words = ew
                break
    return best_match


def upsert_person(entity: dict, vault_root: Path | None = None) -> tuple[Path, bool]:
    """Write (or skip) a canonical person entity.

    Includes fuzzy cross-entity dedup: if an existing person file has a name
    that is a prefix match (word-level) of the new name (or vice versa),
    the richer name wins and source_keys are merged.

    Returns (path, written) where written=True if file was created/updated,
    False if skipped (already exists — idempotent).
    """
    if vault_root is None:
        vault_root = Path(__file__).resolve().parents[2] / "memory" / "vault"

    entities_dir = vault_root / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)

    new_name = entity.get("display_name") or entity.get("entity") or ""
    new_email = entity.get("email")
    new_source_keys = entity.get("source_keys", [])

    # --- Fuzzy cross-entity dedup ---
    existing_path = _find_existing_person_fuzzy(entities_dir, new_name)
    if existing_path is not None and existing_path != _entity_path(vault_root, entity):
        # Merge into existing file
        text = existing_path.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)
        if fm:
            from vault.ingest.meeting_ingest import _pick_richer_name
            existing_name = fm.get("entity", "")
            merged_name = _pick_richer_name(existing_name, new_name)

            # Merge source_keys
            existing_keys = fm.get("source_keys", [])
            merged_keys = list(set(existing_keys + new_source_keys))

            # Merge email
            merged_email = fm.get("email") or new_email

            # Update frontmatter
            fm["entity"] = merged_name
            fm["source_keys"] = merged_keys
            if merged_email:
                fm["email"] = merged_email
            fm["last_seen_at"] = entity.get("last_seen_at", fm.get("last_seen_at"))

            # Update title in body
            if body.startswith("# "):
                first_line_end = body.index("\n") if "\n" in body else len(body)
                body = f"# {merged_name}" + body[first_line_end:]

            existing_path.write_text(_join_frontmatter(fm, body), encoding="utf-8")
            return existing_path, True

    path = _entity_path(vault_root, entity)
    if path.exists():
        return path, False

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

    if entity.get("email"):
        lines.append(f"**Email:** {entity['email']}")
        lines.append("")

    # Meetings section (passed via entity._meetings)
    meetings = entity.get("_meetings", [])
    if meetings:
        lines.append("## Reuniões")
        lines.append("")
        for m in meetings:
            mtitle = m.get("title", "?")
            mdate = (m.get("started_at") or "")[:10]
            mslug = _slugify(mtitle)
            link = f"{mdate} {mslug}" if mdate else mslug
            lines.append(f"- [[{link}]]")
        lines.append("")

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
