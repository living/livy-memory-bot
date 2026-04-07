#!/usr/bin/env python3
"""
topic_rewriter.py — Section-aware parser and renderer for topic files.
"""
import re
from dataclasses import dataclass, field
from decision_ledger import DecisionRecord


@dataclass
class ParsedTopic:
    frontmatter: str
    title: str
    sections: dict[str, str]
    # Track which entity_keys appear in each section so we can remove by key
    # instead of by fragile title string match.
    # Key: section_name → list of (line_index, entity_key, original_line)
    _entity_key_map: dict[str, list[tuple[int, str, str]]] = field(default_factory=dict)

    def register_entity_in_section(self, section: str, entity_key: str, line_index: int, line: str) -> None:
        if section not in self._entity_key_map:
            self._entity_key_map[section] = []
        self._entity_key_map[section].append((line_index, entity_key, line))


def _slug_from_title(title: str) -> str:
    return title.lower().replace(" ", "-").replace(":", "")[:40]


def parse_topic_file(content: str) -> ParsedTopic:
    fm_match = re.match(r"(?s)(---\n.*?\n---\n)", content)
    frontmatter = fm_match.group(1) if fm_match else ""
    body = content[len(frontmatter):]
    title_match = re.search(r"^# .+$", body, re.MULTILINE)
    title = title_match.group(0) if title_match else "# Untitled"

    parts = re.split(r"(?m)^## ", body)
    sections: dict[str, str] = {}
    entity_key_map: dict[str, list[tuple[int, str, str]]] = {}

    for part in parts[1:]:
        header, _, rest = part.partition("\n")
        name = header.strip()
        sections[name] = rest.strip()

        # Register entity keys found in this section's lines
        if name in ("Issues Abertas", "Issues Resolvidas / Superadas"):
            entity_key_map[name] = []
            for i, line in enumerate(rest.strip().split("\n")):
                line = line.strip()
                if line.startswith("-"):
                    # Extract title from line (before "—")
                    title_text = line.lstrip("-").strip().split("—")[0].strip()
                    slug = _slug_from_title(title_text)
                    entity_key_map[name].append((i, f"issue:{slug}", line))

    return ParsedTopic(
        frontmatter=frontmatter,
        title=title,
        sections=sections,
        _entity_key_map=entity_key_map,
    )


def render_topic_file(parsed: ParsedTopic, decisions: list[DecisionRecord]) -> str:
    open_section = parsed.sections.get("Issues Abertas", "")
    resolved_section = parsed.sections.get("Issues Resolvidas / Superadas", "(nenhuma)")

    for decision in decisions:
        if decision.result != "accepted" or decision.new_status != "resolved":
            continue

        entity_key = decision.entity_key
        slug = entity_key.split(":", 1)[1] if ":" in entity_key else entity_key
        title = slug.replace("-", " ").title()

        # ── 1. Find the original line to preserve exact wording ───────────
        matched_line: str | None = None

        # Try to find by entity_key map first (stable)
        open_map = parsed._entity_key_map.get("Issues Abertas", [])
        for _idx, key, line in open_map:
            if key == entity_key:
                matched_line = line
                break

        # Fallback: fuzzy title word-overlap if no exact key match
        if matched_line is None:
            sig_words = {w.strip(".,;:()[]{}") for w in title.lower().split() if len(w) > 2}
            if sig_words:
                for _idx, key, line in open_map:
                    issue_slug = key.split(":", 1)[1] if ":" in key else key
                    issue_words = {w.strip(".,;:()[]{}") for w in issue_slug.replace("-", " ").split() if len(w) > 2}
                    if len(sig_words & issue_words) >= 2:
                        matched_line = line
                        break

        # Last resort: exact title word in line (original fragile behavior, kept as safety net)
        if matched_line is None:
            for line in open_section.split("\n"):
                if title.lower() in line.lower():
                    matched_line = line.strip().lstrip("-").strip()
                    break

        if matched_line is None:
            matched_line = title  # fallback

        # ── 2. Remove from open section by entity_key or line ─────────────
        lines = open_section.split("\n")
        removed = False
        # First pass: remove by entity_key match
        if open_map:
            keys_to_remove = {k for _, k, _ in open_map if k == entity_key}
            if keys_to_remove:
                lines = [
                    line for line in lines
                    if not any(
                        line.strip().startswith("-") and
                        _slug_from_title(line.lstrip("-").strip().split("—")[0].strip()) + ":issue" == entity_key
                        for _ in [None]
                        if entity_key.startswith("issue:")
                    )
                ]
                # Simpler: check line index from map
                idxs_to_remove = {idx for idx, k, _ in open_map if k == entity_key}
                lines = [l for i, l in enumerate(lines) if i not in idxs_to_remove]
                removed = bool(idxs_to_remove)

        # Second pass: if key-based remove didn't work, use title overlap
        if not removed:
            title_word = title.lower().split()[0] if title.split() else ""
            if title_word:
                lines = [l for l in lines if title_word not in l.lower()]
        open_section = "\n".join(lines).strip()

        # ── 3. Append to resolved section ───────────────────────────────
        if resolved_section == "(nenhuma)":
            resolved_section = ""
        evidence_refs_str = " | ".join(decision.evidence_refs) if decision.evidence_refs else ""
        resolved_section += f"\n- {matched_line} — {decision.why} (regra: {decision.rule_id})"
        if evidence_refs_str:
            resolved_section += f" | evidência: {evidence_refs_str}"

    parsed.sections["Issues Abertas"] = open_section.strip() or "(nenhuma)"
    parsed.sections["Issues Resolvidas / Superadas"] = resolved_section.strip()

    SECTION_ORDER = [
        "Status Atual",
        "Estado Operacional",
        "Issues Abertas",
        "Issues Resolvidas / Superadas",
        "Decisões Históricas",
        "Conflitos / Aguardando Confirmação",
    ]

    ordered = [
        parsed.frontmatter.strip(),
        parsed.title,
        "",
    ]
    for name in SECTION_ORDER:
        if name in parsed.sections:
            ordered.extend([f"## {name}", parsed.sections[name], ""])
    # Append any sections not in SECTION_ORDER (future-proofing)
    for name, value in parsed.sections.items():
        if name not in SECTION_ORDER:
            ordered.extend([f"## {name}", value, ""])

    return "\n".join(part for part in ordered if part is not None).strip() + "\n"
