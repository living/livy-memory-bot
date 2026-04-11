"""Incremental index.md manager for vault entities."""
from __future__ import annotations

import re
from pathlib import Path


INDEX_FILENAME = "index.md"
_INDEX_HEADER = """# Vault Index

| Path | Title | Type |
| --- | --- | --- |
"""
_ROW_RE = re.compile(
    r"^\|\s*\[(?P<label>[^\]]+)\]\((?P<path>[^)]+)\)\s*\|\s*(?P<title>.*?)\s*\|\s*(?P<type>.*?)\s*\|\s*$"
)


def _index_path(vault_root: Path) -> Path:
    return Path(vault_root) / INDEX_FILENAME


def init_index(vault_root: Path) -> None:
    """Create index.md if it does not exist."""
    root = Path(vault_root)
    root.mkdir(parents=True, exist_ok=True)
    index_path = _index_path(root)
    if not index_path.exists():
        index_path.write_text(_INDEX_HEADER, encoding="utf-8")


def read_index(vault_root: Path) -> dict[str, dict[str, str]]:
    """Parse index.md table rows into {path: {title, type}}."""
    init_index(vault_root)
    rows: dict[str, dict[str, str]] = {}
    text = _index_path(Path(vault_root)).read_text(encoding="utf-8")
    for line in text.splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        path = m.group("path")
        rows[path] = {
            "title": m.group("title"),
            "type": m.group("type"),
        }
    return rows


def add_entry(vault_root: Path, path: str, title: str, entry_type: str) -> None:
    """Append a new index row if path is not already indexed."""
    init_index(vault_root)
    if path in read_index(vault_root):
        return

    index_path = _index_path(Path(vault_root))
    with index_path.open("a", encoding="utf-8") as fh:
        fh.write(f"| [{path}]({path}) | {title} | {entry_type} |\n")


def update_entry(vault_root: Path, path: str, title: str) -> None:
    """Update title for an existing row in index.md."""
    init_index(vault_root)
    index_path = _index_path(Path(vault_root))
    lines = index_path.read_text(encoding="utf-8").splitlines()

    updated_lines: list[str] = []
    changed = False

    for line in lines:
        m = _ROW_RE.match(line)
        if not m:
            updated_lines.append(line)
            continue

        row_path = m.group("path")
        row_type = m.group("type")
        if row_path == path:
            updated_lines.append(f"| [{path}]({path}) | {title} | {row_type} |")
            changed = True
        else:
            updated_lines.append(line)

    if changed:
        index_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
