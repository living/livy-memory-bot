#!/usr/bin/env python3
"""
topic_rewriter.py — Section-aware parser and renderer for topic files.
"""
import re
from dataclasses import dataclass
from decision_ledger import DecisionRecord


@dataclass
class ParsedTopic:
    frontmatter: str
    title: str
    sections: dict[str, str]


def parse_topic_file(content: str) -> ParsedTopic:
    fm_match = re.match(r"(?s)(---\n.*?\n---\n)", content)
    frontmatter = fm_match.group(1) if fm_match else ""
    body = content[len(frontmatter):]
    title_match = re.search(r"^# .+$", body, re.MULTILINE)
    title = title_match.group(0) if title_match else "# Untitled"
    
    parts = re.split(r"(?m)^## ", body)
    sections = {}
    for part in parts[1:]:
        header, _, rest = part.partition("\n")
        sections[header.strip()] = rest.strip()
    return ParsedTopic(frontmatter=frontmatter, title=title, sections=sections)


def render_topic_file(parsed: ParsedTopic, decisions: list[DecisionRecord]) -> str:
    open_section = parsed.sections.get("Issues Abertas", "")
    resolved_section = parsed.sections.get("Issues Resolvidas / Superadas", "(nenhuma)")
    
    for decision in decisions:
        if decision.result == "accepted" and decision.new_status == "resolved":
            # Look up the original title from the open section to preserve exact casing
            slug = decision.entity_key.split(':', 1)[1] if ':' in decision.entity_key else decision.entity_key
            title = slug.replace('-', ' ').title()
            matched_line = None
            for line in open_section.split("\n"):
                if title.lower() in line.lower():
                    matched_line = line.strip().lstrip('-').strip()
                    break
            if matched_line is None:
                matched_line = title  # fallback

            # Remove from open section if present (basic textual remove for now)
            lines = open_section.split("\n")
            lines = [line for line in lines if title.lower() not in line.lower()]
            open_section = "\n".join(lines)

            # Append to resolved section
            if resolved_section == "(nenhuma)":
                resolved_section = ""
            resolved_section += f"\n- {matched_line} — {decision.why} (regra: {decision.rule_id})"
            
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
