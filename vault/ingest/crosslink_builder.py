"""Cross-link builder — orchestrate Stage 8: cards/PRs → persons/projects.

Main entry point: run_crosslink()
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

from vault.ingest.mapping_loader import (
    load_trello_member_map,
    load_repo_project_map,
    load_board_project_map,
    get_schema_dir,
)
from vault.ingest.entity_writer import upsert_pr, upsert_card
from vault.ingest.crosslink_resolver import (
    resolve_card_members,
    resolve_pr_author,
    save_trello_member_map,
)
from vault.ingest.crosslink_enrichment import (
    enrich_project_files,
    enrich_person_files_with_crosslinks,
    update_meeting_context,
)
from vault.ingest.crosslink_dedup import dedup_draft_persons

logger = logging.getLogger(__name__)

def _atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to file atomically using tmp + rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding=encoding)
        os.replace(str(tmp), str(path))
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


# Reuse fuzzy matching from meeting_ingest
from vault.ingest.meeting_ingest import _fuzzy_name_key, _is_name_prefix
from vault.ingest.mapping_loader import (
    load_trello_member_map,
    load_repo_project_map,
    load_board_project_map,
)
from vault.ingest.entity_writer import upsert_card, upsert_pr, _split_frontmatter


def run_crosslink(
    vault_root: Path,
    dry_run: bool = False,
    trello_api_key: str | None = None,
    trello_token: str | None = None,
    github_token: str | None = None,
) -> dict[str, Any]:
    """Stage 8: Cross-link cards and PRs to persons and projects.

    Reads enrichment_context from meeting entities, resolves cards/PRs to
    persons and projects via mapping configs, and writes relationship files.
    """
    import json
    from vault.ingest.mapping_loader import (
        load_trello_member_map,
        load_repo_project_map,
        load_board_project_map,
        get_schema_dir,
    )
    from vault.ingest.entity_writer import upsert_pr, _split_frontmatter

    schema_dir = get_schema_dir(vault_root)
    rel_dir = vault_root / "relationships"
    meetings_dir = vault_root / "entities" / "meetings"

    # Load mappings
    member_map = load_trello_member_map(schema_dir)
    repo_map = load_repo_project_map(schema_dir)
    board_map = load_board_project_map(schema_dir)

    # Collect all cards and PRs — primary source: entity files on disk
    all_cards: dict[str, dict] = {}  # card_id → card
    all_prs: dict[str, dict] = {}    # pr_key → pr

    # ── Primary: read card entity files ────────────────────────────────────
    cards_dir = vault_root / "entities" / "cards"
    if cards_dir.exists():
        for cf in cards_dir.glob("*.md"):
            try:
                text = cf.read_text(encoding="utf-8")
                if not text.startswith("---"):
                    continue
                end = text.find("---", 3)
                if end == -1:
                    continue
                fm = yaml.safe_load(text[3:end]) or {}
                # card_id_source is the Trello card ID; fall back to id_canonical
                cid = fm.get("card_id_source") or fm.get("card_id") or ""
                # Also extract short card ID from id_canonical if needed
                if not cid:
                    idc = fm.get("id_canonical", "")
                    # card:BOARD:SHORTID format
                    parts = idc.split(":")
                    if len(parts) >= 3:
                        cid = parts[-1]
                if cid:
                    all_cards[str(cid)] = {
                        "id": str(cid),
                        "name": fm.get("title", fm.get("entity", "")),
                        "board_id": fm.get("board", fm.get("board_id", "")),
                        "members": fm.get("members", []),
                    }
            except Exception as exc:
                logger.warning("Failed to parse card entity %s: %s", cf.name, exc)

    # ── Primary: read PR entity files ─────────────────────────────────────
    prs_dir = vault_root / "entities" / "prs"
    if prs_dir.exists():
        for pf in prs_dir.glob("*.md"):
            try:
                text = pf.read_text(encoding="utf-8")
                if not text.startswith("---"):
                    continue
                end = text.find("---", 3)
                if end == -1:
                    continue
                fm = yaml.safe_load(text[3:end]) or {}
                repo = fm.get("repo", "")
                number = fm.get("pr_id_source", fm.get("number", ""))
                purl = fm.get("url", f"https://github.com/{repo}/pull/{number}") if repo else ""
                pr_key = purl or f"{repo}#{number}"
                if pr_key and pr_key not in all_prs:
                    all_prs[pr_key] = {
                        "url": purl,
                        "repo": repo,
                        "number": number,
                        "title": fm.get("title", fm.get("entity", "")),
                        "author": fm.get("author", ""),
                        "project_ref": fm.get("project_ref", ""),
                    }
            except Exception as exc:
                logger.warning("Failed to parse PR entity %s: %s", pf.name, exc)

    # ── Secondary: meeting enrichment_context (merge, don't overwrite) ────
    if meetings_dir.exists():
        for mf in meetings_dir.glob("*.md"):
            try:
                text = mf.read_text(encoding="utf-8")
                if not text.startswith("---"):
                    continue
                end = text.find("---", 3)
                if end == -1:
                    continue
                fm = yaml.safe_load(text[3:end]) or {}
                ec = fm.get("enrichment_context")
                if not isinstance(ec, dict):
                    continue
                for card in ec.get("trello", {}).get("cards", []):
                    cid = card.get("id", "")
                    if cid and cid not in all_cards:
                        all_cards[cid] = card
                for pr in ec.get("github", {}).get("pull_requests", []):
                    purl = pr.get("url", "")
                    if purl and purl not in all_prs:
                        all_prs[purl] = pr
            except Exception as exc:
                logger.warning("Failed to parse meeting %s: %s", mf.name, exc)
                continue

    stats = {"cards": len(all_cards), "prs": len(all_prs), "dry_run": dry_run}

    if dry_run:
        return stats

    # Clean stale auto-generated PR entities (quarantine, don't delete)
    prs_dir = vault_root / "entities" / "prs"
    if prs_dir.exists():
        quarantine = prs_dir / ".quarantine"
        for pf in prs_dir.glob("*.md"):
            try:
                text = pf.read_text(encoding="utf-8")
                end = text.find("---", 3)
                if end == -1:
                    continue
                fm = yaml.safe_load(text[3:end]) or {}
                # Only clean auto-generated PR entities
                if fm.get("type") != "pr" or fm.get("last_touched_by") != "livy-agent":
                    continue
                # Only if missing critical field
                if not fm.get("repo") or fm.get("id_canonical", "").endswith(":"):
                    quarantine.mkdir(exist_ok=True)
                    dest = quarantine / pf.name
                    if not dest.exists():
                        pf.rename(dest)
                    logger.info("Quarantined stale PR entity: %s", pf.name)
            except Exception:
                pass  # Don't delete broken files

    # ── Enrich cards with member info from Trello API if missing ──────────
    if trello_api_key and trello_token:
        import requests as _requests
        for cid, card in all_cards.items():
            if card.get("members"):
                continue
            # Fetch members from Trello API
            board_id = card.get("board_id", card.get("board", ""))
            card_trello_id = cid
            if not board_id or not card_trello_id:
                continue
            try:
                url = f"https://api.trello.com/1/cards/{card_trello_id}/members"
                resp = _requests.get(url, params={"key": trello_api_key, "token": trello_token}, timeout=10)
                if resp.status_code == 200:
                    api_members = resp.json()
                    if api_members:
                        card["members"] = [{"id": m["id"], "fullName": m.get("fullName", m.get("username", ""))} for m in api_members]
            except Exception as exc:
                logger.warning("Failed to fetch members for card %s: %s", cid, exc)

    # Resolve and build edges
    card_person_edges: list[dict] = []
    card_project_edges: list[dict] = []
    pr_person_edges: list[dict] = []
    pr_project_edges: list[dict] = []

    # Cards → Persons + Projects
    for cid, card in all_cards.items():
        persons = resolve_card_members(card, member_map, vault_root, schema_dir)
        for pname in persons:
            card_person_edges.append({
                "from_id": f"card:trello:{cid}",
                "to_id": f"person:{pname}",
                "role": "assignee",
                "confidence": "high",
            })

        board_id = card.get("board_id", card.get("board", ""))
        project = board_map.get(board_id) if board_id else None
        if project:
            card_project_edges.append({
                "from_id": f"card:trello:{cid}",
                "to_id": f"project:{project}",
                "role": "belongs_to",
                "confidence": "high",
            })

    # PRs → Persons + Projects
    for purl, pr in all_prs.items():
        author = resolve_pr_author(pr, vault_root, github_token)
        if author:
            pr_person_edges.append({
                "from_id": f"pr:{pr.get('repo', '')}:{pr.get('number', '')}",
                "to_id": f"person:{author}",
                "role": "author",
                "confidence": "high",
            })

        repo = pr.get("repo", "")
        project = repo_map.get(repo) if repo else None
        if project:
            pr_project_edges.append({
                "from_id": f"pr:{repo}:{pr.get('number', '')}",
                "to_id": f"project:{project}",
                "role": "belongs_to",
                "confidence": "high",
            })

        # Upsert PR entity
        try:
            pr_entity = {
                "id_canonical": f"pr:{repo}:{pr.get('number', '')}",
                "entity": pr.get("title", "?"),
                "title": pr.get("title", "?"),
                "pr_id_source": pr.get("number", ""),
                "repo": repo,
                "project_ref": project,
                "author": author,
                "confidence": "medium",
                "source_keys": [f"github:{repo}:{pr.get('number', '')}"],
            }
            merged = pr.get("merged_at")
            if merged:
                pr_entity["merged_at"] = merged
            upsert_pr(pr_entity, vault_root)
        except Exception as exc:
            logger.warning("Failed to upsert PR entity: %s", exc)

    # Write relationship files
    rel_dir.mkdir(parents=True, exist_ok=True)
    for name, edges in [
        ("card-person.json", card_person_edges),
        ("card-project.json", card_project_edges),
        ("pr-person.json", pr_person_edges),
        ("pr-project.json", pr_project_edges),
    ]:
        target = rel_dir / name
        _atomic_write(
            target,
            json.dumps({"edges": edges}, indent=2, ensure_ascii=False),
        )

    stats["edges"] = {
        "card_person": len(card_person_edges),
        "card_project": len(card_project_edges),
        "pr_person": len(pr_person_edges),
        "pr_project": len(pr_project_edges),
    }

    # Enrich project/person/meeting files (Tasks 8-10)
    try:
        enrich_project_files(vault_root)
    except Exception:
        pass
    try:
        enrich_person_files_with_crosslinks(vault_root)
    except Exception:
        pass
    try:
        update_meeting_context(vault_root, card_project_edges, pr_project_edges)
    except Exception:
        pass

    # Dedup draft persons into canonicals
    try:
        deduped = dedup_draft_persons(vault_root)
        if deduped:
            stats["persons_deduped"] = deduped
    except Exception:
        pass

    return stats

