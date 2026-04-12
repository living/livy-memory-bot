"""Cross-link builder — link cards/PRs to persons and projects.

Stage 8 in the external ingest pipeline.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

# Reuse fuzzy matching from meeting_ingest
from vault.ingest.meeting_ingest import _fuzzy_name_key, _is_name_prefix
from vault.ingest.mapping_loader import (
    load_trello_member_map,
    load_repo_project_map,
    load_board_project_map,
)
from vault.ingest.entity_writer import upsert_card, upsert_pr, _split_frontmatter


def _strip_accents(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")


def _slugify(name: str) -> str:
    s = _strip_accents(name).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _load_person_names(vault_root: Path) -> list[str]:
    """Scan person entity files and return list of entity names."""
    persons_dir = vault_root / "entities" / "persons"
    if not persons_dir.is_dir():
        return []
    names: list[str] = []
    for f in persons_dir.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        m = re.search(r'^entity:\s*"([^"]+)"', text, re.MULTILINE)
        if not m:
            m = re.search(r"^entity:\s*(.+)$", text, re.MULTILINE)
        if m:
            names.append(m.group(1).strip().strip('"'))
    return names


def _fuzzy_find(name: str, candidates: list[str]) -> str | None:
    """Try to fuzzy-match name against candidates. Returns matched name or None."""
    norm = _fuzzy_name_key(name)
    for cand in candidates:
        if _fuzzy_name_key(cand) == norm:
            return cand
    # Try prefix matching
    for cand in candidates:
        if _is_name_prefix(norm, _fuzzy_name_key(cand)) or _is_name_prefix(_fuzzy_name_key(cand), norm):
            return cand
    return None


def _create_draft_person(vault_root: Path, member: dict) -> None:
    """Create a minimal draft person entity file."""
    persons_dir = vault_root / "entities" / "persons"
    persons_dir.mkdir(parents=True, exist_ok=True)
    name = member["fullName"]
    mid = member["id"]
    slug = _slugify(name)
    content = (
        f"---\n"
        f'entity: "{name}"\n'
        f"type: person\n"
        f'id_canonical: "person:trello:{mid}"\n'
        f"confidence: low\n"
        f"draft: true\n"
        f"---\n"
        f"\n"
        f"# {name}\n"
        f"\n"
        f"*Auto-created from Trello card membership. Needs manual review.*\n"
    )
    (persons_dir / f"{slug}.md").write_text(content, encoding="utf-8")


def _load_github_login_map(vault_root: Path) -> dict[str, str]:
    """Return {github_login_lower: person_name} from person frontmatter."""
    persons_dir = vault_root / "entities" / "persons"
    if not persons_dir.is_dir():
        return {}
    result: dict[str, str] = {}
    for f in persons_dir.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        # Extract entity name
        em = re.search(r'^entity:\s*"([^"]+)"', text, re.MULTILINE)
        if not em:
            em = re.search(r"^entity:\s*(.+)$", text, re.MULTILINE)
        if not em:
            continue
        name = em.group(1).strip().strip('"')
        # Extract github_login
        gm = re.search(r'^github_login:\s*(.+)$', text, re.MULTILINE)
        if gm:
            result[gm.group(1).strip().lower()] = name
    return result


def _create_draft_person_from_login(vault_root: Path, login: str) -> None:
    """Create a draft person from a GitHub login."""
    persons_dir = vault_root / "entities" / "persons"
    persons_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(login)
    content = (
        f"---\n"
        f'entity: "{login}"\n'
        f"type: person\n"
        f'github_login: "{login}"\n'
        f"confidence: low\n"
        f"draft: true\n"
        f"---\n"
        f"\n"
        f"# {login}\n"
        f"\n"
        f"*Auto-created from GitHub PR author. Needs manual review.*\n"
    )
    (persons_dir / f"{slug}.md").write_text(content, encoding="utf-8")


def resolve_pr_author(
    pr_data: dict,
    vault_root: Path,
    github_token: str | None = None,
) -> str | None:
    """Resolve a PR's author to a person name.

    Resolution chain:
      1. Fetch PR from GitHub API → get user.login
      2. Match against person files via github_login frontmatter
      3. Fuzzy name match against existing person names
      4. Create draft person if no match
    """
    if not github_token:
        return None

    pr_url = pr_data.get("url", "")
    m = re.match(r'https://github\.com/([^/]+/[^/]+)/pull/(\d+)', pr_url)
    if not m:
        return None

    owner_repo, number = m.group(1), int(m.group(2))
    api_url = f"https://api.github.com/repos/{owner_repo}/pulls/{number}"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }

    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        login = resp.json().get("user", {}).get("login")
    except Exception:
        return None

    if not login:
        return None

    # 2. Match by github_login
    login_map = _load_github_login_map(vault_root)
    if login.lower() in login_map:
        return login_map[login.lower()]

    # 3. Fuzzy match by login as name
    person_names = _load_person_names(vault_root)
    match = _fuzzy_find(login, person_names)
    if match:
        return match

    # 4. Create draft
    _create_draft_person_from_login(vault_root, login)
    return login


def fetch_prs_for_repos(
    repos: list[str],
    github_token: str | None = None,
    days: int = 30,
) -> list[dict]:
    """Fetch recent PRs from GitHub API for configured repos.

    Returns list of dicts with: repo, title, html_url, merged_at, user_login.
    """
    if not repos:
        return []

    headers = {
        "Accept": "application/vnd.github+json",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    all_prs: list[dict] = []

    for repo in repos:
        url = f"https://api.github.com/repos/{repo}/pulls?state=all&per_page=100&sort=updated&direction=desc"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue
            for pr in resp.json():
                merged = pr.get("merged_at")
                if merged:
                    try:
                        merged_dt = datetime.fromisoformat(merged.replace("Z", "+00:00"))
                        if merged_dt < cutoff:
                            continue
                    except (ValueError, TypeError):
                        pass
                all_prs.append({
                    "repo": repo,
                    "title": pr.get("title", ""),
                    "html_url": pr.get("html_url", ""),
                    "merged_at": merged,
                    "user_login": pr.get("user", {}).get("login"),
                })
        except Exception:
            continue

    return all_prs


def save_trello_member_map(schema_dir: Path, member_map: dict[str, str]) -> None:
    """Write member map back to trello-member-map.yaml."""
    path = schema_dir / "trello-member-map.yaml"
    lines = [
        "# Trello member ID → person name (for cross-linking)\n",
        "# Auto-populated by member resolution, manually curated\n",
        "members:\n",
    ]
    for mid, name in sorted(member_map.items()):
        lines.append(f'  "{mid}": "{name}"\n')
    path.write_text("".join(lines), encoding="utf-8")


def resolve_card_members(
    card_entity: dict,
    member_map: dict[str, str],
    vault_root: Path,
    schema_dir: Path | None = None,
) -> list[str]:
    """Resolve Trello card members to person names.

    Strategy per member:
      1. Check member_map (Trello ID → name)
      2. Fuzzy match against existing person entity files
      3. Create draft person entity if no match

    Auto-populates member_map with new entries and optionally saves to YAML.
    """
    members = card_entity.get("members", [])
    if not members:
        return []

    person_names = _load_person_names(vault_root)
    resolved: list[str] = []
    dirty = False

    for member in members:
        mid = member["id"]
        full_name = member["fullName"]

        # 1. Check map
        if mid in member_map:
            resolved.append(member_map[mid])
            continue

        # 2. Fuzzy match
        match = _fuzzy_find(full_name, person_names)
        if match:
            resolved.append(match)
            member_map[mid] = match
            dirty = True
            continue

        # 3. Create draft
        _create_draft_person(vault_root, member)
        resolved.append(full_name)
        member_map[mid] = full_name
        dirty = True

    # Auto-populate YAML if schema_dir provided and map changed
    if dirty and schema_dir is not None:
        save_trello_member_map(schema_dir, member_map)

    return resolved


def _enrich_project_files(vault_root: Path) -> None:
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
            except Exception:
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


def _enrich_person_files_with_crosslinks(vault_root: Path) -> None:
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
            except Exception:
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


def _update_meeting_context(vault_root: Path) -> None:
    """Task 10: Replace date-proximity ## Contexto with project-scoped links."""
    from vault.ingest.entity_writer import _slugify, _split_frontmatter, _join_frontmatter
    from vault.ingest.external_ingest import _detect_project

    rel_dir = vault_root / "relationships"
    if not rel_dir.exists():
        return

    def _load_edges(filename: str) -> list[dict]:
        p = rel_dir / filename
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")).get("edges", [])
        return []

    card_project = _load_edges("card-project.json")
    pr_project = _load_edges("pr-project.json")

    # Load card/PR details
    card_details: dict[str, dict] = {}
    pr_details: dict[str, dict] = {}
    meetings_dir = vault_root / "entities" / "meetings"
    if not meetings_dir.exists():
        return

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

    # Build project → cards/PRs
    proj_cards: dict[str, list[str]] = {}
    proj_prs: dict[str, list[str]] = {}
    for edge in card_project:
        proj = edge.get("to_id", "").replace("project:", "")
        cid = edge.get("from_id", "").replace("card:trello:", "")
        card = card_details.get(cid, {})
        title = card.get("name", cid)
        proj_cards.setdefault(proj, []).append(f"📋 {cid}: {title}")
    for edge in pr_project:
        proj = edge.get("to_id", "").replace("project:", "")
        pr_id = edge.get("from_id", "")
        pr = None
        for purl, pdata in pr_details.items():
            if pr_id == f"pr:{pdata.get('repo', '')}:{pdata.get('number', '')}":
                pr = pdata
                break
        title = pr.get("title", pr_id) if pr else pr_id
        proj_prs.setdefault(proj, []).append(f"🔀 {pr_id}: {title}")

    # Update each meeting file
    for mf in meetings_dir.glob("*.md"):
        text = mf.read_text(encoding="utf-8")
        # Parse with yaml.safe_load to preserve nested structures
        if not text.startswith("---"):
            continue
        end = text.find("---", 3)
        if end == -1:
            continue
        fm = yaml.safe_load(text[3:end]) or {}
        body = text[end + 3:].lstrip("\n")
        title = fm.get("entity", "")
        project = _detect_project(title)
        if not project:
            continue

        # Build new context
        lines = ["## Contexto", ""]
        lines.append(f"### Projeto: [[{project}]]")
        for item in proj_cards.get(project, []):
            lines.append(f"- {item}")
        for item in proj_prs.get(project, []):
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
            except Exception:
                continue

    stats = {"cards": len(all_cards), "prs": len(all_prs), "dry_run": dry_run}

    if dry_run:
        return stats

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
        except Exception:
            pass

    # Write relationship files
    rel_dir.mkdir(parents=True, exist_ok=True)
    for name, edges in [
        ("card-person.json", card_person_edges),
        ("card-project.json", card_project_edges),
        ("pr-person.json", pr_person_edges),
        ("pr-project.json", pr_project_edges),
    ]:
        target = rel_dir / name
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"edges": edges}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(str(tmp), str(target))

    stats["edges"] = {
        "card_person": len(card_person_edges),
        "card_project": len(card_project_edges),
        "pr_person": len(pr_person_edges),
        "pr_project": len(pr_project_edges),
    }

    # Enrich project/person/meeting files (Tasks 8-10)
    try:
        _enrich_project_files(vault_root)
    except Exception:
        pass
    try:
        _enrich_person_files_with_crosslinks(vault_root)
    except Exception:
        pass
    try:
        _update_meeting_context(vault_root)
    except Exception:
        pass

    return stats
