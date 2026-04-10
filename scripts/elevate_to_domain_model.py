#!/usr/bin/env python3
"""Elevate vault markdown frontmatter to the Wave A domain model.

Usage:
  python3 scripts/elevate_to_domain_model.py [--dry-run] [--verbose] [--scope all|poc]
"""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = ROOT / "memory" / "vault"
BACKUP_DIRNAME = ".migration-backup"

POC_FILES = {
    "entities/tldv-pipeline.md",
    "decisions/decision-1.md",
    "decisions/decision-2.md",
    "concepts/concept-1.md",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sorted_unique(values: Iterable[str]) -> list[str]:
    return sorted({v for v in values if isinstance(v, str) and v.strip()})


def scan_files(vault_root: Path, scope: str = "all") -> list[Path]:
    """Scan candidate markdown files for migration."""
    files: list[Path] = []
    for sub in ("entities", "decisions", "concepts"):
        d = vault_root / sub
        if d.exists():
            files.extend(sorted(d.glob("*.md")))

    if scope == "poc":
        selected: list[Path] = []
        for p in files:
            rel = p.relative_to(vault_root).as_posix()
            if rel in POC_FILES:
                selected.append(p)
        return selected

    return files


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse markdown frontmatter and return (frontmatter, body)."""
    stripped = text.lstrip()
    if not stripped.startswith("---\n"):
        return {}, text

    try:
        end = stripped.index("\n---", 4)
    except ValueError:
        return {}, text

    fm_text = stripped[4:end]
    body = stripped[end + 4 :]
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data, body.lstrip("\n")


def _entity_prefix(frontmatter: dict) -> str:
    t = str(frontmatter.get("type", "")).strip().lower()
    mapping = {
        "person": "person",
        "project": "project",
        "repo": "repo",
        "meeting": "meeting",
        "card": "card",
    }
    return mapping.get(t, "project")


def elevate_frontmatter(frontmatter: dict, path: Path) -> tuple[dict, bool]:
    """Return elevated frontmatter plus a changed flag."""
    changed = False
    out = dict(frontmatter)
    now = _now_iso()

    sources = out.get("sources")
    source_refs: list[str] = []
    retrieved_values: list[str] = []
    if isinstance(sources, list):
        for src in sources:
            if isinstance(src, dict):
                ref = src.get("source_ref")
                ret = src.get("retrieved_at")
                if isinstance(ref, str) and ref.strip():
                    source_refs.append(ref.strip())
                if isinstance(ret, str) and ret.strip():
                    retrieved_values.append(ret.strip())

    source_keys = _sorted_unique(source_refs)
    first_seen = min(retrieved_values) if retrieved_values else now
    last_seen = max(retrieved_values) if retrieved_values else now

    ftype = str(out.get("type", "")).strip().lower()

    if "id_canonical" not in out:
        if ftype == "decision":
            out["id_canonical"] = f"decision:{path.stem}"
        else:
            out["id_canonical"] = f"{_entity_prefix(out)}:{path.stem}"
        changed = True

    if "source_keys" not in out:
        out["source_keys"] = source_keys
        changed = True

    if "first_seen_at" not in out:
        out["first_seen_at"] = first_seen
        changed = True

    if "last_seen_at" not in out:
        out["last_seen_at"] = last_seen
        changed = True

    if ftype == "decision":
        lineage = out.get("lineage")
        if not isinstance(lineage, dict):
            lineage = {}

        required_lineage = {
            "run_id": lineage.get("run_id") or "domain-elevation-wave-a",
            "source_keys": lineage.get("source_keys") if isinstance(lineage.get("source_keys"), list) else source_keys,
            "transformed_at": lineage.get("transformed_at") or now,
            "mapper_version": lineage.get("mapper_version") or "domain-elevation-v1",
            "actor": lineage.get("actor") or "elevate_to_domain_model",
        }

        if lineage != required_lineage:
            out["lineage"] = required_lineage
            changed = True

    return out, changed


def apply_with_backup(path: Path, new_text: str, vault_root: Path, dry_run: bool = False) -> Path | None:
    """Backup original file and apply migrated text."""
    backup_path = vault_root / BACKUP_DIRNAME / path.relative_to(vault_root)
    if dry_run:
        return backup_path

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    path.write_text(new_text, encoding="utf-8")
    return backup_path


def _dump_markdown(frontmatter: dict, body: str) -> str:
    fm = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{fm}\n---\n\n{body}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Elevate vault frontmatter to domain model")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-file details")
    parser.add_argument("--scope", choices=("all", "poc"), default="all", help="Migration scope")
    parser.add_argument("--vault-root", default=str(VAULT_ROOT), help="Vault root path (for tests)")
    args = parser.parse_args(argv)

    vault_root = Path(args.vault_root)
    files = scan_files(vault_root, scope=args.scope)

    migrated = 0
    would_migrate = 0
    skipped = 0

    for md in files:
        original = md.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(original)
        if not frontmatter:
            skipped += 1
            continue

        elevated, changed = elevate_frontmatter(frontmatter, md)
        if not changed:
            skipped += 1
            continue

        new_text = _dump_markdown(elevated, body)
        if args.dry_run:
            would_migrate += 1
        else:
            apply_with_backup(md, new_text, vault_root=vault_root, dry_run=False)
            migrated += 1

        if args.verbose:
            rel = md.relative_to(vault_root)
            print(f"{'would_migrate' if args.dry_run else 'migrated'}: {rel}")

    print(f"scope: {args.scope}")
    print(f"total_files: {len(files)}")
    print(f"would_migrate: {would_migrate}")
    print(f"migrated: {migrated}")
    print(f"skipped: {skipped}")
    if not args.dry_run:
        print(f"backup_dir: {vault_root / BACKUP_DIRNAME}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
