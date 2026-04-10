"""vault/quality/quality_review.py — weekly quality review artifact generator."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vault.domain.canonical_types import (
    CONFIDENCE_LEVELS,
    RELATIONSHIP_ROLES,
    SOURCE_TYPES,
    is_valid_id_prefix,
)

OFFICIAL_SOURCE_TYPES = {
    "github_api",
    "tldv_api",
    "trello_api",
    "supabase_rest",
    "exec",
    "openclaw_config",
}


def _markdown_files(vault_root: Path) -> list[Path]:
    files: list[Path] = []
    for sub in ("decisions", "entities", "concepts"):
        d = vault_root / sub
        if d.exists():
            files.extend(sorted(d.glob("*.md")))
    return files


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text[3:].split("---", 1)
    if len(parts) < 2:
        return {}
    out: dict[str, str] = {}
    for line in parts[0].splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip()
    return out


def _parse_sources(text: str) -> list[dict[str, str]]:
    """Parse source records from markdown YAML frontmatter.

    Supports both canonical and legacy field names:
    - canonical:  source_type / source_ref / retrieved_at / mapper_version
    - legacy:     type     / ref     / retrieved   (pre-2026-04-10)

    The parser detects which format is in use by checking for "source_type" or "type"
    in the first source block found.
    """
    sources: list[dict[str, str]] = []
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        # Support both "- source_type:" (canonical) and "- type:" (legacy)
        is_source_block = line.startswith("- source_type:") or line.startswith("- type:")
        if is_source_block:
            if line.startswith("- source_type:"):
                source_type = line.split(":", 1)[1].strip()
            else:
                source_type = line.split(":", 1)[1].strip()
            source_ref = ""
            retrieved_at = ""
            mapper_version = ""
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                # Detect start of next source block or end of frontmatter
                if nxt.startswith("- source_type:") or nxt.startswith("- type:"):
                    break
                if nxt == "---" or nxt.startswith("## ") or nxt.startswith("# "):
                    break
                # Support canonical and legacy field names
                if nxt.startswith("source_ref:"):
                    source_ref = nxt.split(":", 1)[1].strip()
                elif nxt.startswith("ref:"):
                    source_ref = nxt.split(":", 1)[1].strip()
                elif nxt.startswith("retrieved_at:"):
                    retrieved_at = nxt.split(":", 1)[1].strip()
                elif nxt.startswith("retrieved:"):
                    retrieved_at = nxt.split(":", 1)[1].strip()
                elif nxt.startswith("mapper_version:"):
                    mapper_version = nxt.split(":", 1)[1].strip().strip('"')
                j += 1
            record: dict[str, str] = {"source_type": source_type}
            if source_ref:
                record["source_ref"] = source_ref
            if retrieved_at:
                record["retrieved_at"] = retrieved_at
            if mapper_version:
                record["mapper_version"] = mapper_version
            sources.append(record)
        i += 1
    return sources


def collect_source_coverage(vault_root: Path) -> dict[str, Any]:
    source_types_found: set[str] = set()
    official_count = 0
    unofficial_count = 0
    missing_sources: list[str] = []

    for path in _markdown_files(vault_root):
        text = path.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        entity_id = fm.get("entity", path.name)
        sources = _parse_sources(text)

        if not sources:
            missing_sources.append(entity_id)
            continue

        for source in sources:
            source_type = source.get("source_type", "")
            if not source_type:
                continue
            source_types_found.add(source_type)
            if source_type in OFFICIAL_SOURCE_TYPES:
                official_count += 1
            else:
                unofficial_count += 1

    total = official_count + unofficial_count
    pct_official = round((official_count / total * 100.0), 2) if total else 100.0

    return {
        "source_types_found": sorted(source_types_found),
        "official_count": official_count,
        "unofficial_count": unofficial_count,
        "missing_sources": missing_sources,
        "pct_official": pct_official,
    }


def check_relation_completeness(vault_root: Path) -> dict[str, Any]:
    """Validate relationship edges against domain minimum + lineage completeness."""
    errors: list[str] = []
    valid_edges = 0
    invalid_edges = 0
    edges_checked = 0

    rel_dir = vault_root / "relationships"
    if rel_dir.exists():
        for rel_file in sorted(rel_dir.glob("*.json")):
            data = json.loads(rel_file.read_text(encoding="utf-8"))
            edges = data if isinstance(data, list) else data.get("edges", [])
            for idx, edge in enumerate(edges):
                edges_checked += 1
                edge_errors: list[str] = []

                from_id = edge.get("from_id")
                to_id = edge.get("to_id")
                role = edge.get("role")
                confidence = edge.get("confidence")
                lineage_run_id = edge.get("lineage_run_id")
                sources = edge.get("sources")

                if not from_id or not is_valid_id_prefix(from_id):
                    edge_errors.append(f"{rel_file.name}[{idx}].from_id")
                if not to_id or not is_valid_id_prefix(to_id):
                    edge_errors.append(f"{rel_file.name}[{idx}].to_id")
                if not role or role not in RELATIONSHIP_ROLES:
                    edge_errors.append(f"{rel_file.name}[{idx}].role")
                if confidence is not None and confidence not in CONFIDENCE_LEVELS:
                    edge_errors.append(f"{rel_file.name}[{idx}].confidence")

                if not isinstance(lineage_run_id, str) or not lineage_run_id.strip():
                    edge_errors.append(f"{rel_file.name}[{idx}].lineage_run_id")

                if not isinstance(sources, list) or len(sources) == 0:
                    edge_errors.append(f"{rel_file.name}[{idx}].sources")

                if edge_errors:
                    invalid_edges += 1
                    errors.extend(edge_errors)
                else:
                    valid_edges += 1

    return {
        "valid_edges": valid_edges,
        "invalid_edges": invalid_edges,
        "edges_checked": edges_checked,
        "errors": errors,
    }


def detect_identity_ambiguity(vault_root: Path) -> dict[str, Any]:
    login_to_entities: dict[str, set[str]] = {}

    entity_dir = vault_root / "entities"
    if entity_dir.exists():
        for path in sorted(entity_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            fm = _parse_frontmatter(text)
            if fm.get("type") != "person":
                continue
            entity_id = fm.get("entity", path.stem)

            for src in _parse_sources(text):
                source_type = src.get("source_type", "")
                source_ref = src.get("source_ref", "")
                if source_type == "github_api" and "github.com/" in source_ref:
                    m = re.search(r"github\.com/([^/#?\s]+)", source_ref)
                    if not m:
                        continue
                    login = m.group(1).lower()
                    login_to_entities.setdefault(login, set()).add(entity_id)

    ambiguities: list[dict[str, Any]] = []
    for login, entities in sorted(login_to_entities.items()):
        if len(entities) > 1:
            ambiguities.append({"login": login, "entity_ids": sorted(entities)})

    return {
        "ambiguity_count": len(ambiguities),
        "ambiguities": ambiguities,
    }


def detect_mismatches(vault_root: Path) -> dict[str, Any]:
    mismatches: list[str] = []

    for path in _markdown_files(vault_root):
        text = path.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)

        file_type = fm.get("type")
        if not file_type:
            mismatches.append(f"{path.name}:missing_type")

        id_canonical = fm.get("id_canonical")
        if not id_canonical:
            mismatches.append(f"{path.name}:missing_id_canonical")
        elif not is_valid_id_prefix(id_canonical):
            mismatches.append(f"{path.name}:invalid_id_canonical")

        if path.parent.name == "decisions":
            confidence = fm.get("confidence")
            if not confidence:
                mismatches.append(f"{path.name}:missing_confidence")
            elif confidence not in CONFIDENCE_LEVELS:
                mismatches.append(f"{path.name}:invalid_confidence")

        for idx, source in enumerate(_parse_sources(text)):
            source_type = source.get("source_type", "")
            source_ref = source.get("source_ref", "")

            if not source_type:
                mismatches.append(f"{path.name}:sources[{idx}].missing_type")
            elif source_type not in SOURCE_TYPES:
                mismatches.append(f"{path.name}:sources[{idx}].invalid_type")

            if not source_ref:
                mismatches.append(f"{path.name}:sources[{idx}].missing_ref")

    return {
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def generate_quality_report(vault_root: Path) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "generated_at": generated_at,
        "vault_path": str(vault_root),
        "source_coverage": collect_source_coverage(vault_root),
        "relation_completeness": check_relation_completeness(vault_root),
        "identity_ambiguity_queue": detect_identity_ambiguity(vault_root),
        "mismatches": detect_mismatches(vault_root),
    }


def _to_markdown(report: dict[str, Any]) -> str:
    sc = report["source_coverage"]
    rc = report["relation_completeness"]
    ia = report["identity_ambiguity_queue"]
    mm = report["mismatches"]

    lines = [
        "# Weekly Quality Review",
        "",
        f"Generated at: {report['generated_at']}",
        f"Vault path: {report['vault_path']}",
        "",
        "## Summary",
        f"- Source coverage official %: {sc['pct_official']}",
        f"- Relation invalid edges: {rc['invalid_edges']}",
        f"- Identity ambiguities: {ia['ambiguity_count']}",
        f"- Mismatches: {mm['mismatch_count']}",
        "",
        "## Source Coverage",
        f"- Source types found: {', '.join(sc['source_types_found']) if sc['source_types_found'] else '(none)'}",
        f"- Official sources: {sc['official_count']}",
        f"- Unofficial sources: {sc['unofficial_count']}",
        f"- Missing source records: {len(sc['missing_sources'])}",
        "",
        "## Relation Completeness",
        f"- Edges checked: {rc['edges_checked']}",
        f"- Valid edges: {rc['valid_edges']}",
        f"- Invalid edges: {rc['invalid_edges']}",
        "",
        "## Identity Ambiguity Queue",
        f"- Ambiguity count: {ia['ambiguity_count']}",
        "",
        "## Mismatches",
        f"- Mismatch count: {mm['mismatch_count']}",
        "",
    ]

    if rc["errors"]:
        lines.extend(["### Relation errors"] + [f"- {e}" for e in rc["errors"]] + [""])
    if ia["ambiguities"]:
        lines.extend(["### Ambiguities"] + [f"- {a}" for a in ia["ambiguities"]] + [""])
    if mm["mismatches"]:
        lines.extend(["### Mismatch details"] + [f"- {m}" for m in mm["mismatches"]] + [""])

    return "\n".join(lines)


def write_report(vault_root: Path, output_dir: Path | None = None) -> Path:
    report = generate_quality_report(vault_root)
    if output_dir is None:
        output_dir = Path("memory") / "vault" / "quality-review"
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = output_dir / f"{date_str}.md"
    out_path.write_text(_to_markdown(report), encoding="utf-8")
    return out_path
