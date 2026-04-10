#!/usr/bin/env python3
"""
scripts/migrate_source_schema.py — Migrate vault source records to canonical schema.

Converts legacy frontmatter source fields to canonical format:
  type      → source_type
  ref       → source_ref
  retrieved → retrieved_at
  + adds    mapper_version

Scope: decisions/, entities/ and concepts/ under memory/vault/
Safe: backed-up in memory/vault/.migration-backup/ before changes.

Usage:
  python3 scripts/migrate_source_schema.py [--dry-run] [--verbose]
"""
from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = ROOT / "memory" / "vault"
BACKUP_DIR = VAULT_ROOT / ".migration-backup"
MAPPER_VERSION = "signal-ingest-v1"


def _backup_file(src: Path) -> Path:
    """Copy src to .migration-backup/ preserving structure."""
    dst = BACKUP_DIR / src.relative_to(VAULT_ROOT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def _normalize_iso(value: str) -> str:
    """Normalise a date or datetime string to UTC ISO timestamp YYYY-MM-DDTHH:MM:SSZ."""
    value = value.strip().rstrip("Z")
    try:
        # Try full ISO datetime
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        pass
    try:
        # Date only → midnight UTC
        dt = datetime.strptime(value[:10], "%Y-%m-%d")
        return dt.strftime("%Y-%m-%dT00:00:00Z")
    except ValueError:
        pass
    return f"{value[:10]}T00:00:00Z"


def _parse_sources_legacy(text: str) -> list[dict]:
    """Parse legacy source records from YAML text block."""
    sources: list[dict] = []
    in_sources = False
    current: dict = {}

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "sources:":
            in_sources = True
            current = {}
            continue
        if in_sources:
            if stripped == "sources: []" or stripped == "[]":
                return [{"source_type": "_empty_placeholder_"}]
            if stripped.startswith("- type:") or stripped.startswith("- source_type:"):
                if current:
                    sources.append(current)
                key = "source_type"
                val = stripped.split(":", 1)[1].strip()
                current = {key: val}
            elif stripped.startswith("ref:") or stripped.startswith("source_ref:"):
                current["source_ref"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("retrieved:") or stripped.startswith("retrieved_at:"):
                current["retrieved_at"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("mapper_version:"):
                current["mapper_version"] = stripped.split(":", 1)[1].strip().strip('"')
            elif stripped.startswith("note:"):
                current["note"] = stripped.split(":", 1)[1].strip()
            elif stripped in ("---", "") or stripped.startswith("#"):
                if current:
                    sources.append(current)
                    current = {}
                in_sources = False
            elif stripped.startswith("- "):
                # Next source starting with dash but not type/source_type
                if current:
                    sources.append(current)
                    current = {}
    if current:
        sources.append(current)
    return sources


def _build_sources_canonical(sources: list[dict], file_path: Path) -> str:
    """Build canonical YAML sources block from parsed source records."""
    lines: list[str] = ["sources:"]
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for src in sources:
        if src.get("source_type") == "_empty_placeholder_":
            # repair stub: add canonical signal_event source
            lines.append(f"  - source_type: signal_event")
            lines.append(f"    source_ref: repair-stub:{file_path.name}")
            lines.append(f"    retrieved_at: {now_utc}")
            lines.append(f'    mapper_version: "{MAPPER_VERSION}"')
            continue

        stype = src.get("source_type", "signal_event")

        # Normalize source_ref
        sref = src.get("source_ref", "").strip()
        if not sref and stype == "signal_event":
            sref = f"migration-derived:{file_path.name}"

        # Normalize retrieved_at
        rat = src.get("retrieved_at", "").strip()
        if rat:
            rat = _normalize_iso(rat)
        else:
            rat = now_utc

        # Get mapper_version or use default
        mv = src.get("mapper_version", "").strip().strip('"')
        if not mv:
            mv = MAPPER_VERSION

        note = src.get("note", "").strip()

        lines.append(f"  - source_type: {stype}")
        lines.append(f"    source_ref: {sref}")
        lines.append(f"    retrieved_at: {rat}")
        lines.append(f'    mapper_version: "{mv}"')
        if note:
            lines.append(f"    note: {note}")

    return "\n".join(lines)


def _migrate_file(path: Path, dry_run: bool = False, verbose: bool = False) -> dict:
    """Migrate a single vault file to canonical source schema."""
    text = path.read_text(encoding="utf-8")

    if not text.startswith("---"):
        return {"path": str(path), "status": "skip", "reason": "no frontmatter"}

    # Split frontmatter / body
    fm_end = text.index("\n---", 4)
    fm_block = text[4:fm_end].strip()
    body = text[fm_end + 4:]

    # Parse sources and detect whether migration is needed
    sources = _parse_sources_legacy(fm_block)

    has_legacy_markers = bool(
        re.search(r"(?m)^\s*-\s+type:\s*", fm_block)
        or re.search(r"(?m)^\s+ref:\s*", fm_block)
        or re.search(r"(?m)^\s+retrieved:\s*", fm_block)
    )

    # Also migrate canonical blocks that are missing mapper_version
    non_empty_sources = [s for s in sources if s.get("source_type") != "_empty_placeholder_"]
    has_missing_mapper = any("mapper_version" not in s for s in non_empty_sources)

    # Files with neither legacy markers nor missing mapper are already canonical or intentionally empty.
    if not has_legacy_markers and not has_missing_mapper:
        return {"path": str(path), "status": "skip", "reason": "no_legacy_markers"}

    # If there are no sources at all (e.g., sources: []), do not force migration.
    if not non_empty_sources:
        return {"path": str(path), "status": "skip", "reason": "empty_sources"}

    
    # Check if already canonical (all sources have full canonical fields, including mapper_version)
    already_canonical = bool(non_empty_sources) and all(
        "source_type" in s and "source_ref" in s and "retrieved_at" in s and "mapper_version" in s
        for s in non_empty_sources
    )
    if already_canonical:
        return {"path": str(path), "status": "skip", "reason": "already_canonical"}

    # Build new frontmatter
    sources_yaml = _build_sources_canonical(sources, path)

    # Rebuild frontmatter without old sources block
    fm_lines: list[str] = []
    in_sources = False
    inserted_sources = False
    for line in fm_block.splitlines():
        stripped = line.strip()
        if stripped == "sources:":
            in_sources = True
            if not inserted_sources:
                fm_lines.append(sources_yaml)
                inserted_sources = True
            continue
        if in_sources:
            # Continue skipping old source lines while they are indented/list-like fields
            if line.startswith("  ") or stripped.startswith("-"):
                continue
            # End of sources block once we hit next top-level key
            in_sources = False
        fm_lines.append(line)

    # If sources key wasn't present, append canonical sources block
    if not inserted_sources:
        fm_lines.append(sources_yaml)

    new_fm = "\n".join(fm_lines).strip()
    new_text = f"---\n{new_fm}\n---\n{body}"

    if not dry_run:
        _backup_file(path)
        path.write_text(new_text, encoding="utf-8")

    if verbose:
        print(f"  {'[DRY] ' if dry_run else ''}migrated: {path.name} ({len(sources)} sources)")

    return {
        "path": str(path),
        "status": "migrated" if not dry_run else "would_migrate",
        "sources": len(sources),
    }


def migrate_vault(dry_run: bool = False, verbose: bool = False) -> dict:
    """Migrate all vault decision/entity/concept files."""
    if not dry_run:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    migrated = 0
    skipped = 0

    for subdir in ("decisions", "entities", "concepts"):
        dir_path = VAULT_ROOT / subdir
        if not dir_path.exists():
            continue
        for md_file in sorted(dir_path.glob("*.md")):
            r = _migrate_file(md_file, dry_run=dry_run, verbose=verbose)
            results.append(r)
            if r["status"] in {"migrated", "would_migrate"}:
                migrated += 1
            else:
                skipped += 1

    return {
        "migrated": migrated,
        "skipped": skipped,
        "total": migrated + skipped,
        "backup_dir": str(BACKUP_DIR) if not dry_run else "(dry-run, no backup)",
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate vault source records to canonical schema")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print each file migrated")
    args = parser.parse_args()

    print(f"Memory Vault Source Schema Migration")
    print(f"  dry-run: {args.dry_run}")
    print(f"  vault:   {VAULT_ROOT}")
    print()

    result = migrate_vault(dry_run=args.dry_run, verbose=args.verbose)

    print(f"\nResults:")
    print(f"  migrated: {result['migrated']}")
    print(f"  skipped:  {result['skipped']}")
    print(f"  total:    {result['total']}")
    if not args.dry_run:
        print(f"  backup:   {result['backup_dir']}")
    else:
        print(f"  backup:   (dry-run — no files written)")

    if result["migrated"] > 0 and not args.dry_run:
        print(f"\n⚠️  Backups saved to {BACKUP_DIR}")
        print("   Run with --dry-run to preview before applying.")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
