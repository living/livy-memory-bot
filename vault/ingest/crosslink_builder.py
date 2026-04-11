"""Cross-link builder — link cards/PRs to persons and projects.

Stage 8 in the external ingest pipeline.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

# Reuse fuzzy matching from meeting_ingest
from vault.ingest.meeting_ingest import _fuzzy_name_key, _is_name_prefix


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
