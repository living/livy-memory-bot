"""Crosslink enrichment — update project/person/meeting entity files with crosslink data."""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from vault.ingest.entity_writer import _slugify, _split_frontmatter, _join_frontmatter

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

def enrich_project_files(vault_root: Path) -> None:
    """Task 8: Add Cards/PRs/Pessoas sections to project entity files."""
    from vault.ingest.entity_writer import _slugify, _split_frontmatter, _join_frontmatter

    rel_dir = vault_root / "relationships"
    if not rel_dir.exists():
        return

    # Load relationship data
    def _load_edges(filename: str) -> list[dict]:
        p = rel_dir / filename
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")).get("edges", [])
        return []

    card_project = _load_edges("card-project.json")
    pr_project = _load_edges("pr-project.json")
    card_person = _load_edges("card-person.json")
    pr_person = _load_edges("pr-person.json")

    # Load card/PR details from meeting enrichment_context
    card_details: dict[str, dict] = {}
    pr_details: dict[str, dict] = {}
    meetings_dir = vault_root / "entities" / "meetings"
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
                    card_details[card.get("id", "")] = card
                for pr in ec.get("github", {}).get("pull_requests", []):
                    pr_details.get(pr.get("url", ""), pr)
                    # Also key by repo+number
                    pr_details[pr.get("url", "")] = pr
            except Exception as exc:
                logger.warning("Failed to parse meeting %s: %s", mf.name, exc)
                continue

    # Build per-project data
    project_cards: dict[str, list[str]] = {}   # project → ["[[card-id|Title]]"]
    project_prs: dict[str, list[str]] = {}     # project → ["[[pr-repo-num|Title]]"]
    project_persons: dict[str, set] = {}        # project → {person_name}

    for edge in card_project:
        proj = edge.get("to_id", "").replace("project:", "")
        cid = edge.get("from_id", "").replace("card:trello:", "")
        card = card_details.get(cid, {})
        title = card.get("name", cid)
        slug = _slugify(proj)
        project_cards.setdefault(slug, []).append(f"- [[{cid}|{title}]]")

    for edge in pr_project:
        proj = edge.get("to_id", "").replace("project:", "")
        pr_id = edge.get("from_id", "")
        # Find PR by matching from_id pattern pr:repo:number
        title = ""
        for purl, pdata in pr_details.items():
            if pr_id == f"pr:{pdata.get('repo', '')}:{pdata.get('number', '')}":
                title = pdata.get("title", pr_id)
                break
        if not title:
            title = pr_id
        slug = _slugify(proj)
        project_prs.setdefault(slug, []).append(f"- [[{pr_id}|{title}]]")

    # Collect persons per project from card-person and pr-person edges
    card_person_by_card: dict[str, list[str]] = {}
    for edge in card_person:
        cid = edge.get("from_id", "").replace("card:trello:", "")
        pname = edge.get("to_id", "").replace("person:", "")
        card_person_by_card.setdefault(cid, []).append(pname)

    for edge in card_project:
        proj = edge.get("to_id", "").replace("project:", "")
        cid = edge.get("from_id", "").replace("card:trello:", "")
        slug = _slugify(proj)
        for pname in card_person_by_card.get(cid, []):
            project_persons.setdefault(slug, set()).add(pname)

    for edge in pr_person:
        pname = edge.get("to_id", "").replace("person:", "")
        pr_id = edge.get("from_id", "")
        # Find project for this PR
        for pe in pr_project:
            if pe.get("from_id") == pr_id:
                proj = pe.get("to_id", "").replace("project:", "")
                slug = _slugify(proj)
                project_persons.setdefault(slug, set()).add(pname)

    # Update project files
    projects_dir = vault_root / "entities" / "projects"
    if not projects_dir.exists():
        return
    for pf in projects_dir.glob("*.md"):
        slug = pf.stem
        text = pf.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)

        # Remove existing sections
        for section in ["## Cards", "## PRs", "## Pessoas"]:
            if section in body:
                idx = body.index(section)
                next_s = body.find("\n## ", idx + 1)
                if next_s == -1:
                    body = body[:idx]
                else:
                    body = body[:idx] + body[next_s + 1:]

        sections = []
        if slug in project_cards:
            sections.append("## Cards\n")
            sections.extend(project_cards[slug])
            sections.append("")
        if slug in project_prs:
            sections.append("## PRs\n")
            sections.extend(project_prs[slug])
            sections.append("")
        if slug in project_persons:
            sections.append("## Pessoas\n")
            for pname in sorted(project_persons[slug]):
                sections.append(f"- [[{_slugify(pname)}|{pname}]]")
            sections.append("")

        if sections:
            body = body.rstrip() + "\n\n" + "\n".join(sections)

        pf.write_text(_join_frontmatter(fm, body), encoding="utf-8")


def enrich_person_files_with_crosslinks(vault_root: Path) -> None:
    """Task 9: Add Cards/PRs sections to person entity files."""
    from vault.ingest.entity_writer import _slugify, _split_frontmatter, _join_frontmatter

    rel_dir = vault_root / "relationships"
    if not rel_dir.exists():
        return

    def _load_edges(filename: str) -> list[dict]:
        p = rel_dir / filename
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")).get("edges", [])
        return []

    card_person = _load_edges("card-person.json")
    pr_person = _load_edges("pr-person.json")

    # Load card/PR details
    card_details: dict[str, dict] = {}
    pr_details: dict[str, dict] = {}
    meetings_dir = vault_root / "entities" / "meetings"
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
                    card_details[card.get("id", "")] = card
                for pr in ec.get("github", {}).get("pull_requests", []):
                    pr_details[pr.get("url", "")] = pr
            except Exception as exc:
                logger.warning("Failed to parse meeting %s: %s", mf.name, exc)
                continue

    # Build person → cards/PRs
    person_cards: dict[str, list[str]] = {}  # slug → ["[[card-id|Title]]"]
    person_prs: dict[str, list[str]] = {}    # slug → ["[[pr-id|Title]]"]

    for edge in card_person:
        pname = edge.get("to_id", "").replace("person:", "")
        cid = edge.get("from_id", "").replace("card:trello:", "")
        card = card_details.get(cid, {})
        title = card.get("name", cid)
        slug = _slugify(pname)
        person_cards.setdefault(slug, []).append(f"- [[{cid}|{title}]]")

    for edge in pr_person:
        pname = edge.get("to_id", "").replace("person:", "")
        pr_id = edge.get("from_id", "")
        # Find title
        title = pr_id
        for purl, pdata in pr_details.items():
            if pr_id == f"pr:{pdata.get('repo', '')}:{pdata.get('number', '')}":
                title = pdata.get("title", pr_id)
                break
        slug = _slugify(pname)
        person_prs.setdefault(slug, []).append(f"- [[{pr_id}|{title}]]")

    # Update person files
    persons_dir = vault_root / "entities" / "persons"
    if not persons_dir.exists():
        return
    for pf in persons_dir.glob("*.md"):
        slug = pf.stem
        if slug not in person_cards and slug not in person_prs:
            continue
        text = pf.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)

        # Remove existing Cards/PRs sections
        for section in ["## Cards", "## PRs"]:
            if section in body:
                idx = body.index(section)
                next_s = body.find("\n## ", idx + 1)
                if next_s == -1:
                    body = body[:idx]
                else:
                    body = body[:idx] + body[next_s + 1:]

        # Build new sections
        sections = []
        if slug in person_cards:
            sections.append("## Cards\n")
            sections.extend(person_cards[slug])
            sections.append("")
        if slug in person_prs:
            sections.append("## PRs\n")
            sections.extend(person_prs[slug])
            sections.append("")

        if not sections:
            continue

        new_text = "\n".join(sections)
        # Insert before ## Reuniões if present, else append
        if "## Reuniões" in body:
            idx = body.index("## Reuniões")
            body = body[:idx] + new_text + "\n" + body[idx:]
        else:
            body = body.rstrip() + "\n\n" + new_text

        pf.write_text(_join_frontmatter(fm, body), encoding="utf-8")


def update_meeting_context(vault_root: Path, card_project_edges: list[dict], pr_project_edges: list[dict]) -> None:
    """Task 10: Replace date-proximity ## Contexto with project-scoped links.

    Derives projects from relationship edges (card-project and pr-project)
    instead of regex-based title detection.
    """
    from vault.ingest.entity_writer import _slugify, _split_frontmatter, _join_frontmatter

    meetings_dir = vault_root / "entities" / "meetings"
    if not meetings_dir.exists():
        return

    # Build card_id → project and pr_id → project lookups
    card_to_proj: dict[str, str] = {}
    for edge in card_project_edges:
        cid = edge.get("from_id", "").replace("card:trello:", "")
        proj = edge.get("to_id", "").replace("project:", "")
        if cid and proj:
            card_to_proj[cid] = proj

    pr_to_proj: dict[str, str] = {}
    for edge in pr_project_edges:
        pr_id = edge.get("from_id", "")
        proj = edge.get("to_id", "").replace("project:", "")
        if pr_id and proj:
            pr_to_proj[pr_id] = proj

    # Load card/PR details from enrichment contexts
    card_details: dict[str, dict] = {}
    pr_details: dict[str, dict] = {}
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
            if isinstance(ec, dict):
                for card in ec.get("trello", {}).get("cards", []):
                    card_details[card.get("id", "")] = card
                for pr in ec.get("github", {}).get("pull_requests", []):
                    pr_details[pr.get("url", "")] = pr
        except Exception:
            continue

    # Build project → cards/PRs display strings
    proj_cards: dict[str, list[str]] = {}
    proj_prs: dict[str, list[str]] = {}
    for edge in card_project_edges:
        proj = edge.get("to_id", "").replace("project:", "")
        cid = edge.get("from_id", "").replace("card:trello:", "")
        card = card_details.get(cid, {})
        title = card.get("name", cid)
        proj_cards.setdefault(proj, []).append(f"📋 {cid}: {title}")
    for edge in pr_project_edges:
        proj = edge.get("to_id", "").replace("project:", "")
        pr_id = edge.get("from_id", "")
        pr = None
        for purl, pdata in pr_details.items():
            if pr_id == f"pr:{pdata.get('repo', '')}:{pdata.get('number', '')}":
                pr = pdata
                break
        title = pr.get("title", pr_id) if pr else pr_id
        proj_prs.setdefault(proj, []).append(f"🔀 {pr_id}: {title}")

    # Update each meeting file — derive projects from edges, not title
    for mf in meetings_dir.glob("*.md"):
        raw = mf.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            continue
        end = raw.find("---", 3)
        if end == -1:
            continue
        fm = yaml.safe_load(raw[3:end]) or {}
        body = raw[end + 3:].lstrip("\n")
        ec = fm.get("enrichment_context", {})
        if not isinstance(ec, dict):
            continue

        # Find projects from this meeting's cards/PRs via edges
        projects_found: set[str] = set()
        for card in ec.get("trello", {}).get("cards", []):
            proj = card_to_proj.get(card.get("id", ""))
            if proj:
                projects_found.add(proj)
        for pr in ec.get("github", {}).get("pull_requests", []):
            pr_id = f"pr:{pr.get('repo', '')}:{pr.get('number', '')}"
            proj = pr_to_proj.get(pr_id)
            if proj:
                projects_found.add(proj)

        if not projects_found:
            continue

        # Build new context grouped by project
        lines = ["## Contexto", ""]
        for proj in sorted(projects_found):
            lines.append(f"### Projeto: [[{proj}]]")
            for item in proj_cards.get(proj, []):
                lines.append(f"- {item}")
            for item in proj_prs.get(proj, []):
                lines.append(f"- {item}")
            lines.append("")
        new_context = "\n".join(lines)

        # Remove ALL existing ## Contexto sections
        while "## Contexto" in body:
            idx = body.index("## Contexto")
            next_s = body.find("\n## ", idx + 1)
            if next_s == -1:
                body = body[:idx]
            else:
                body = body[:idx] + body[next_s + 1:]

        # Append new context
        body = body.rstrip() + "\n\n" + new_context

        # Write with yaml.dump to preserve nested frontmatter
        fm_text = yaml.dump(fm, default_flow_style=False, sort_keys=False)
        mf.write_text(f"---\n{fm_text}---\n\n{body}", encoding="utf-8")



