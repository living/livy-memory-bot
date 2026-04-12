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


