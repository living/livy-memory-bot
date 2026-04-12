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

import yaml


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown text into a dict."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    yaml_block = text[3:end].strip()
    body = text[end + 3:].lstrip("\n")
    try:
        fm = yaml.safe_load(yaml_block) or {}
    except Exception:
        fm = {}
    return fm, body


def _join_frontmatter(fm: dict, body: str) -> str:
    """Serialize frontmatter dict + body back to markdown."""
    fm_text = yaml.dump(fm, default_flow_style=False, sort_keys=False)
    return f"---\n{fm_text}---\n\n{body}"



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

    Person → persons/"Lincoln Quinan Junior.md"
    Meeting → meetings/"2026-02-20 Daily Operações B3.md"
    Card → cards/"card-{board}-{title}.md"
    """
    id_canonical = entity.get("id_canonical", "")

    if id_canonical.startswith("meeting:"):
        entities_dir = vault_root / "entities" / "meetings"
        started = entity.get("started_at", "")
        date_part = started[:10] if started else ""
        title = entity.get("title") or entity.get("entity") or id_canonical.replace("meeting:", "")
        slug = _slugify(title)
        if date_part:
            return entities_dir / f"{date_part} {slug}.md"
        return entities_dir / f"{slug}.md"

    if id_canonical.startswith("person:"):
        entities_dir = vault_root / "entities" / "persons"
        name = entity.get("display_name") or entity.get("entity") or id_canonical.replace("person:", "")
        return entities_dir / f"{_slugify(name)}.md"

    if id_canonical.startswith("pr:"):
        entities_dir = vault_root / "entities" / "prs"
        rest = id_canonical.replace("pr:", "")
        slug = _slugify(rest)
        return entities_dir / f"{slug}.md"

    if id_canonical.startswith("card:"):
        entities_dir = vault_root / "entities" / "cards"
        rest = id_canonical.replace("card:", "")
        parts = rest.split(":", 1)
        if len(parts) == 2:
            return entities_dir / f"card-{_slugify(parts[0])}-{_slugify(parts[1])}.md"
        return entities_dir / f"card-{_slugify(rest)}.md"

    # Fallback
    entities_dir = vault_root / "entities"
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

    path.parent.mkdir(parents=True, exist_ok=True)

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

    # Obsidian callout with date, duration, video link
    duration_min = entity.get("duration_min")
    participants = entity.get("_participants", [])
    n_part = len(participants)
    date_display = started_at[:10] if started_at else "?"
    duration_str = f"{duration_min} min" if duration_min else "? min"
    lines.append(f"> [!info] {date_display} · {duration_str} · {n_part} participantes")

    # Video link (Azure blob preferred, fallback to TLDV)
    video_url = entity.get("video_url")
    if video_url:
        lines.append(f"> 🎥 [Assistir gravação]({video_url})")
    elif meeting_id_source:
        lines.append(f"> 🎥 [Assistir no TLDV](https://tldv.io/app/meetings/{meeting_id_source})")
    # Transcript link
    transcript_blob = entity.get("transcript_blob_path")
    if transcript_blob:
        # Construct Azure blob URL
        import os as _os
        storage_base = "https://livingnetopenclawstorage.blob.core.windows.net/living-meeting-hub"
        lines.append(f"> 📝 [Transcrição]({storage_base}/{transcript_blob})")
    lines.append("")

    # Participants section with wiki-links
    if participants:
        lines.append("## Participantes")
        lines.append("")
        for p in participants:
            pname = p.get("name", "")
            if not pname or not pname.strip():
                continue
            lines.append(f"- [[{_slugify(pname)}]]")
        lines.append("")

    # Structured sections for enrichment (TLDV fills these)
    lines.append("## Resumo")
    lines.append("")
    lines.append("<!-- Enriquecimento TLDV: tópicos e pontos-chave -->")
    lines.append("")
    lines.append("## Decisões")
    lines.append("")
    lines.append("<!-- Decisões da reunião -->")
    lines.append("")

    # Contexto — Trello cards and GitHub PRs
    enrichment = entity.get("enrichment_context", {})
    trello_cards = enrichment.get("trello", {}).get("cards", [])
    github_prs = enrichment.get("github", {}).get("pull_requests", [])
    if trello_cards or github_prs:
        lines.append("## Contexto")
        lines.append("")
        for card in trello_cards:
            card_name = card.get("name", "?")
            card_url = card.get("url", "")
            if card_url:
                lines.append(f"- 📋 [{card_name}]({card_url})")
            else:
                lines.append(f"- 📋 {card_name}")
        for pr in github_prs:
            pr_title = pr.get("title", "?")
            pr_url = pr.get("url", "")
            pr_repo = pr.get("repo", "")
            merged = pr.get("merged_at")
            state = "merged" if merged else "open"
            repo_short = pr_repo.split("/")[-1] if pr_repo else ""
            if pr_url:
                lines.append(f"- 🔀 [{pr_title}]({pr_url}) — {repo_short} ({state})")
            else:
                lines.append(f"- 🔀 {pr_title} — {repo_short} ({state})")
        lines.append("")

    lines.extend(["## Metadados", ""])
    lines.append(f"- **ID:** `{meeting_id_source}`")
    if started_at:
        lines.append(f"- **Início:** {started_at}")
    if ended_at:
        lines.append(f"- **Término:** {ended_at}")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path, True


def _find_existing_person_fuzzy(entities_dir: Path, name: str) -> Path | None:
    """Search existing person files for a fuzzy name match.

    Searches in entities/persons/ subdirectory.
    Returns the path of the best matching existing person, or None.
    """
    from vault.ingest.meeting_ingest import _is_name_prefix, _fuzzy_name_key, _pick_richer_name
    target_key = _fuzzy_name_key(name)
    best_match = None
    best_match_words = 0

    # Search in persons/ subdirectory
    persons_dir = entities_dir / "persons" if (entities_dir / "persons").exists() else entities_dir
    for f in persons_dir.glob("*.md"):
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

    new_name = entity.get("display_name") or entity.get("entity") or ""
    new_email = entity.get("email")
    new_source_keys = entity.get("source_keys", [])

    # --- Identity map lookup ---
    from vault.domain.identity_map import IdentityMap
    _identity_map = IdentityMap.load()
    _canonical = (
        _identity_map.resolve(new_name)
        or _identity_map.resolve_by_github(entity.get("github_login", ""))
    )
    if _canonical and _canonical != new_name:
        entity["display_name"] = _canonical
        entity["entity"] = _canonical
        entity["id_canonical"] = f"person:canonical:{_slugify(_canonical).lower().replace(' ', '-')}"
        new_name = _canonical

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

    path.parent.mkdir(parents=True, exist_ok=True)

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

    path.parent.mkdir(parents=True, exist_ok=True)

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

    # Pessoas section (from crosslink enrichment)
    persons = entity.get("_persons", [])
    if persons:
        lines.append("## Pessoas")
        lines.append("")
        for pname in persons:
            lines.append(f"- [[{pname}]]")
        lines.append("")

    # Projeto section (from crosslink enrichment)
    project = entity.get("_project")
    if project:
        lines.append("## Projeto")
        lines.append("")
        lines.append(f"- [[{project}]]")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path, True


def upsert_pr(entity: dict, vault_root: Path | None = None) -> tuple[Path, bool]:
    """Write (or skip) a PR entity. Idempotent."""
    if vault_root is None:
        vault_root = Path(__file__).resolve().parents[2] / "memory" / "vault"

    path = _entity_path(vault_root, entity)

    if path.exists():
        return path, False

    path.parent.mkdir(parents=True, exist_ok=True)

    id_canonical = entity.get("id_canonical", "")
    title = entity.get("title") or entity.get("entity") or id_canonical
    pr_id_source = entity.get("pr_id_source", "")
    repo = entity.get("repo", "")
    project_ref = entity.get("project_ref")
    author = entity.get("author")
    confidence = entity.get("confidence", "medium")
    merged_at = entity.get("merged_at")
    created_at = entity.get("created_at")
    updated_at = entity.get("updated_at")
    state = entity.get("state", "")
    draft = entity.get("draft", False)
    body = entity.get("body", "")
    labels = entity.get("labels", [])
    additions = entity.get("additions")
    deletions = entity.get("deletions")
    changed_files = entity.get("changed_files")
    base_branch = entity.get("base_branch", "")
    head_branch = entity.get("head_branch", "")
    reviewers = entity.get("reviewers", [])
    comments = entity.get("comments", [])
    source_keys = entity.get("source_keys", [])
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now_iso[:10]

    lines = [
        "---",
        f'entity: "{title}"',
        "type: pr",
        f"id_canonical: {id_canonical}",
        f"pr_id_source: {pr_id_source}",
        f"repo: {repo}",
    ]
    if project_ref:
        lines.append(f"project_ref: {project_ref}")
    lines.extend([
        f"state: {state}",
        f"draft: {str(draft).lower()}",
        f"confidence: {confidence}",
        "source_keys:",
    ])
    if isinstance(source_keys, list) and source_keys:
        for key in source_keys:
            lines.append(f"  - {key}")
    else:
        lines.append("  - github:unknown")
    lines.extend([
        f"first_seen_at: {now_iso}",
        f"last_seen_at: {now_iso}",
        f"last_verified: {today}",
        f"draft: {str(draft).lower()}",
        "---",
        "",
        f"# {title}",
        "",
    ])

    # Callout with key info
    repo_short = repo.split("/")[-1] if repo else "?"
    state_icon = "✅" if state == "closed" and merged_at else ("🔴" if state == "closed" else "🟡")
    lines.append(f"> [!info] {state_icon} {repo_short} · PR #{pr_id_source} · {state}")
    if base_branch and head_branch:
        lines.append(f"> `{head_branch}` → `{base_branch}`")
    if additions is not None and deletions is not None:
        lines.append(f"> +{additions} / -{deletions} · {changed_files or '?'} files")
    lines.append("")

    # Dados section
    lines.extend(["## Dados", ""])
    lines.append(f"- **Repo:** [{repo}](https://github.com/{repo}/pull/{pr_id_source})")
    if author:
        lines.append(f"- **Autor:** [[{author}]]")
    if project_ref:
        lines.append(f"- **Projeto:** [[{project_ref}]]")
    if created_at:
        lines.append(f"- **Criado:** {created_at[:10]}")
    if merged_at:
        lines.append(f"- **Merged:** {merged_at[:10]}")
    elif updated_at:
        lines.append(f"- **Atualizado:** {updated_at[:10]}")
    if labels:
        lines.append(f"- **Labels:** {', '.join(labels)}")
    if reviewers:
        reviewer_names = ", ".join(f"[[{r}]]" for r in reviewers)
        lines.append(f"- **Reviewers:** {reviewer_names}")
    lines.append("")

    # Descrição section
    if body and body.strip():
        lines.extend(["## Descrição", ""])
        clean_body = body.strip()[:3000]
        lines.append(clean_body)
        lines.append("")

    # Comentários section
    if comments:
        lines.extend(["## Comentários", ""])
        for c in comments[:20]:
            c_author = c.get("author", "?")
            c_body = (c.get("body") or "").strip()[:500]
            c_date = (c.get("created_at") or "")[:10]
            if c_body:
                lines.append(f"**{c_author}** ({c_date}):")
                lines.append(f"> {c_body}")
                lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path, True
