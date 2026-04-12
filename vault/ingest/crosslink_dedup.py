"""Crosslink dedup — merge draft persons into canonicals."""
from __future__ import annotations

import logging
import os
import re
import unicodedata
from pathlib import Path

import yaml

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


def _is_fuzzy_match(draft_name: str, canonical_name: str) -> bool:
    """Conservative fuzzy match: require word-level overlap."""
    import unicodedata, re

    def normalize(s):
        return re.sub(
            r'[^a-z0-9]', '',
            unicodedata.normalize('NFKD', s.lower()).encode('ascii', 'ignore').decode()
        )

    dn = normalize(draft_name)
    cn = normalize(canonical_name)

    # Exact substring of normalized name (at least 5 chars to avoid false positives)
    if len(dn) >= 5 and dn in cn:
        return True

    # Check if draft username is a prefix of any canonical name part
    canon_parts = (
        cn.split() if ' ' not in canonical_name
        else [normalize(p) for p in canonical_name.split()]
    )
    for part in canon_parts:
        if len(part) >= 4 and (dn.startswith(part) or part.startswith(dn)):
            if min(len(dn), len(part)) >= 4:
                return True

    return False


def dedup_draft_persons(vault_root: Path) -> int:
    """Merge draft persons into canonicals by conservative fuzzy name matching."""
    persons_dir = vault_root / "entities" / "persons"
    if not persons_dir.exists():
        return 0

    persons = []
    for f in persons_dir.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        end = text.find("---", 3)
        if end == -1:
            continue
        fm = yaml.safe_load(text[3:end]) or {}
        persons.append({
            "file": f,
            "name": fm.get("entity", f.stem),
            "stem": f.stem,
            "source_keys": fm.get("source_keys", []),
            "trello_ids": fm.get("trello_ids", []),
            "trello_usernames": fm.get("trello_usernames", []),
            "github_logins": fm.get("github_logins", []),
        })

    canonicals = [p for p in persons if " " in p["name"] and not p["name"].startswith("person:")]
    drafts = [p for p in persons if p not in canonicals]

    merged = 0
    for draft in drafts:
        best = None
        for canon in canonicals:
            if _is_fuzzy_match(draft["name"], canon["name"]):
                best = canon
                break
            # Also check trello usernames as a matching signal
            for un in draft.get("trello_usernames", []):
                if _is_fuzzy_match(un, canon["name"]):
                    best = canon
                    break
            if best:
                break

        if best:
            text = best["file"].read_text(encoding="utf-8")
            end = text.find("---", 3)
            canon_fm = yaml.safe_load(text[3:end]) or {}

            for key in ("source_keys", "trello_ids", "trello_usernames", "github_logins"):
                existing = set(canon_fm.get(key, []))
                for val in draft.get(key, []):
                    if val not in existing:
                        canon_fm.setdefault(key, []).append(val)

            body = text[end + 3:]
            fm_text = yaml.dump(canon_fm, default_flow_style=False, sort_keys=False)
            _atomic_write(best["file"], f"---\n{fm_text}---{body}")

            # Quarantine draft instead of deleting
            quarantine = persons_dir / ".quarantine"
            quarantine.mkdir(exist_ok=True)
            dest = quarantine / draft["file"].name
            if not dest.exists():
                draft["file"].rename(dest)

            logger.info(
                "Dedup: merged draft '%s' into canonical '%s' (quarantined to %s)",
                draft["name"], best["name"], dest.name,
            )
            merged += 1

    return merged


def dedup_with_identity_map(vault_root: Path) -> int:
    """Merge duplicate persons using IdentityMap as ground truth.

    Falls back to existing fuzzy matching (dedup_draft_persons) for
    persons not in the identity map.
    """
    from vault.domain.identity_map import IdentityMap

    im = IdentityMap.load()
    if not im.all_canonical_names():
        return dedup_draft_persons(vault_root)

    persons_dir = vault_root / "entities" / "persons"
    if not persons_dir.exists():
        return 0

    # Index existing files by canonical name
    canonical_files: dict[str, list[dict]] = {}
    unmapped: list[dict] = []
    for f in persons_dir.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        end = text.find("---", 3)
        if end == -1:
            continue
        fm = yaml.safe_load(text[3:end]) or {}
        entity_name = fm.get("entity", f.stem)
        gh_login = fm.get("github_login")

        canonical = (
            im.resolve(entity_name)
            or im.resolve_by_github(gh_login or "")
            or im.resolve_by_trello_name(entity_name)
        )
        entry = {"file": f, "name": entity_name, "fm": fm}
        if canonical:
            canonical_files.setdefault(canonical, []).append(entry)
        else:
            unmapped.append(entry)

    # Merge duplicates within each canonical group
    merged = 0
    for canonical, entries in canonical_files.items():
        if len(entries) < 2:
            continue
        entries.sort(key=lambda e: len(e["fm"].get("source_keys", [])), reverse=True)
        keep = entries[0]
        for absorb in entries[1:]:
            keep_fm = keep["fm"]
            absorb_fm = absorb["fm"]
            keep_fm["entity"] = canonical
            keep_keys = set(keep_fm.get("source_keys", []) or [])
            absorb_keys = set(absorb_fm.get("source_keys", []) or [])
            keep_fm["source_keys"] = sorted(keep_keys | absorb_keys)
            if not keep_fm.get("github_login") and absorb_fm.get("github_login"):
                keep_fm["github_login"] = absorb_fm["github_login"]
            if not keep_fm.get("email") and absorb_fm.get("email"):
                keep_fm["email"] = absorb_fm["email"]
            keep_fm["draft"] = False

            body = keep["file"].read_text(encoding="utf-8")
            end = body.find("---", 3)
            original_body = body[end + 3:]
            if original_body.lstrip("\n").startswith("# "):
                lines = original_body.lstrip("\n").split("\n")
                lines[0] = f"# {canonical}"
                original_body = "\n".join(lines)
            fm_text = yaml.dump(keep_fm, default_flow_style=False, sort_keys=False)
            _atomic_write(keep["file"], f"---\n{fm_text}---{original_body}")

            quarantine = persons_dir / ".quarantine"
            quarantine.mkdir(exist_ok=True)
            dest = quarantine / absorb["file"].name
            if not dest.exists():
                absorb["file"].rename(dest)
            logger.info("Dedup (identity): merged '%s' into canonical '%s'", absorb["name"], canonical)
            merged += 1

    # Also run fuzzy dedup for any remaining unmapped drafts
    merged += dedup_draft_persons(vault_root)
    return merged


