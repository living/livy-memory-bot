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

from vault.ingest.entity_writer import _split_frontmatter, upsert_card
from vault.ingest.meeting_ingest import _fuzzy_name_key, _is_name_prefix

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
    from vault.ingest.mapping_loader import (
        load_trello_member_map,
        load_repo_project_map,
        load_board_project_map,
        get_schema_dir,
    )
    from vault.ingest.crosslink_resolver import (
        resolve_card_members,
        resolve_pr_author,
        fetch_prs_for_repos,
        save_trello_member_map,
    )
    from vault.ingest.crosslink_enrichment import (
        enrich_project_files,
        enrich_person_files_with_crosslinks,
        update_meeting_context,
    )
    from vault.ingest.crosslink_dedup import dedup_draft_persons
    from vault.ingest.entity_writer import upsert_pr

    schema_dir = get_schema_dir(vault_root)
    rel_dir = vault_root / "relationships"
    meetings_dir = vault_root / "entities" / "meetings"

    # Load mappings
    member_map = load_trello_member_map(schema_dir)
    repo_map = load_repo_project_map(schema_dir)
    board_map = load_board_project_map(schema_dir)

    # Collect all cards and PRs from meeting entities
    all_cards: dict[str, dict] = {}  # card_id → card
    all_prs: dict[str, dict] = {}    # pr_url → pr

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
            except Exception as exc:
                logger.warning("Failed to process PR file %s: %s", pf.name, exc)

    # Build PR author cache via batch fetch (one API call per repo)
    pr_author_cache: dict[tuple[str, str], str] = {}  # (repo, number) → login
    if all_prs and github_token:
        unique_repos = list({pr.get("repo", "") for pr in all_prs.values() if pr.get("repo")})
        try:
            batch_prs = fetch_prs_for_repos(unique_repos, github_token=github_token, days=365)
            for bpr in batch_prs:
                if bpr.get("user_login"):
                    pr_author_cache[(bpr["repo"], str(bpr.get("number", "")))] = bpr["user_login"]
            logger.info("Batch PR cache: %d authors from %d repos", len(pr_author_cache), len(unique_repos))
        except Exception as exc:
            logger.warning("Batch PR fetch failed, falling back to individual: %s", exc)

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
        author = resolve_pr_author(
            pr, vault_root, github_token,
            schema_dir=schema_dir,
            pr_author_cache=pr_author_cache,
        )
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
    except Exception as exc:
        logger.warning("enrich_project_files failed: %s", exc)
    try:
        enrich_person_files_with_crosslinks(vault_root)
    except Exception as exc:
        logger.warning("enrich_person_files_with_crosslinks failed: %s", exc)
    try:
        update_meeting_context(vault_root, card_project_edges, pr_project_edges)
    except Exception as exc:
        logger.warning("update_meeting_context failed: %s", exc)

    # Dedup draft persons into canonicals
    try:
        deduped = dedup_draft_persons(vault_root)
        if deduped:
            stats["persons_deduped"] = deduped
    except Exception as exc:
        logger.warning("dedup_draft_persons failed: %s", exc)

    return stats
