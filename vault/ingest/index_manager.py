"""Vault index.md generator — rebuilds a structured dashboard from entity files."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INDEX_FILENAME = "index.md"


def _index_path(vault_root: Path) -> Path:
    return vault_root / INDEX_FILENAME


def init_index(vault_root: Path) -> None:
    """Create index.md if it does not exist."""
    vault_root.mkdir(parents=True, exist_ok=True)
    ip = _index_path(vault_root)
    if not ip.exists():
        rebuild_index(vault_root)


def read_index(vault_root: Path) -> dict[str, dict[str, str]]:
    """Parse index.md for backward compat — returns {path: {title, type}}."""
    ip = _index_path(vault_root)
    if not ip.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    text = ip.read_text(encoding="utf-8")
    for line in text.splitlines():
        # Match wiki-links: [[path|label]] or [[path]]
        m = re.match(r"^- \[\[([^|\]]+)(?:\|([^\]]+))?\]\]", line)
        if m:
            path = m.group(1)
            label = m.group(2) or path
            rows[path] = {"title": label, "type": "unknown"}
        # Match md links: [label](path)
        m2 = re.match(r"^- \[([^\]]+)\]\(([^)]+)\)", line)
        if m2:
            rows[m2.group(2)] = {"title": m2.group(1), "type": "unknown"}
    return rows


def add_entry(vault_root: Path, path: str, title: str, entry_type: str) -> None:
    """Append entry — backward compat. Rebuild will clean it up."""
    # No-op for incremental; rebuild_index handles everything
    pass


def update_entry(vault_root: Path, path: str, title: str) -> None:
    """Update entry — backward compat."""
    pass


def rebuild_index(vault_root: Path) -> None:
    """Scan entity files and rebuild index.md as a structured dashboard."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    lines: list[str] = [
        "# 🧠 Living Memory Vault",
        "",
        f"_Atualizado: {today}_",
        "",
    ]

    # ── People Section ──
    persons_dir = vault_root / "entities" / "persons"
    persons: list[tuple[str, str]] = []  # (name, relative_path)
    if persons_dir.exists():
        for f in sorted(persons_dir.glob("*.md")):
            rel = f.relative_to(vault_root)
            name = f.stem
            persons.append((name, str(rel)))

    lines.append(f"## 👥 Pessoas ({len(persons)})")
    lines.append("")
    for name, rel in persons:
        lines.append(f"- [[{name}]]")
    lines.append("")

    # ── Meetings Calendar ──
    meetings_dir = vault_root / "entities" / "meetings"
    meetings: list[tuple[str, str, str]] = []  # (date, title, relative_path)
    if meetings_dir.exists():
        for f in sorted(meetings_dir.glob("*.md")):
            rel = f.relative_to(vault_root)
            stem = f.stem
            # Parse date from filename (YYYY-MM-DD ...)
            date_part = stem[:10] if len(stem) >= 10 and stem[4] == "-" else ""
            title = stem[11:] if date_part and len(stem) > 11 else stem
            meetings.append((date_part, title, str(rel)))

    # Group by month
    meetings_by_month: dict[str, list[tuple[str, str, str]]] = {}
    for date, title, rel in meetings:
        month_key = date[:7] if date else "sem-data"
        meetings_by_month.setdefault(month_key, []).append((date, title, rel))

    lines.append(f"## 📅 Reuniões ({len(meetings)})")
    lines.append("")
    for month_key in sorted(meetings_by_month.keys(), reverse=True):
        month_meetings = meetings_by_month[month_key]
        # Format month header
        if month_key != "sem-data":
            try:
                dt = datetime.strptime(month_key, "%Y-%m")
                month_label = dt.strftime("%B %Y")
                # Capitalize Portuguese month names
                month_map = {
                    "January": "Janeiro", "February": "Fevereiro", "March": "Março",
                    "April": "Abril", "May": "Maio", "June": "Junho",
                    "July": "Julho", "August": "Agosto", "September": "Setembro",
                    "October": "Outubro", "November": "Novembro", "December": "Dezembro",
                }
                month_label = month_map.get(month_label.split()[0], month_label.split()[0]) + " " + month_label.split()[1]
            except ValueError:
                month_label = month_key
        else:
            month_label = "Sem data"
        lines.append(f"### {month_label} ({len(month_meetings)})")
        lines.append("")
        for date, title, rel in sorted(month_meetings, key=lambda x: x[0], reverse=True):
            day = date[8:10] if len(date) >= 10 else "?"
            lines.append(f"- **{day}** · [[{date} {title}]]" if date else f"- [[{title}]]")
        lines.append("")

    # ── Stats ──
    lines.append("## 📊 Stats")
    lines.append("")
    lines.append(f"| Métrica | Valor |")
    lines.append(f"| --- | --- |")
    lines.append(f"| Pessoas | {len(persons)} |")
    lines.append(f"| Reuniões | {len(meetings)} |")

    # Count relationships
    rel_file = vault_root / "relationships" / "person-meeting.json"
    if rel_file.exists():
        import json
        try:
            data = json.loads(rel_file.read_text(encoding="utf-8"))
            n_rels = len(data.get("edges", []))
            lines.append(f"| Relacionamentos | {n_rels} |")
        except Exception:
            pass
    lines.append("")

    _index_path(vault_root).write_text("\n".join(lines), encoding="utf-8")
