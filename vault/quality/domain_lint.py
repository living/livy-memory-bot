"""
vault/quality/domain_lint.py — domain-specific quality validation for Memory Vault.

Validates domain model integrity:
- Relationship edges use allowed roles
- Entity IDs use correct prefixes
- Source records have required fields
- Confidence values are within enum
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from vault.domain.canonical_types import (
    RELATIONSHIP_ROLES,
    SOURCE_FIELDS,
    SOURCE_TYPES,
    ID_PREFIXES,
    CONFIDENCE_LEVELS,
    is_valid_id_prefix,
)


def _all_markdown_files(vault_root: Path) -> list[Path]:
    """Recursively find all .md files under vault_root."""
    if not vault_root.exists():
        return []
    return list(vault_root.rglob("*.md"))


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse YAML frontmatter from markdown text.

    Returns empty dict if no frontmatter found.
    """
    if not text.startswith("---"):
        return {}
    parts = text[3:].split("---", 1)
    if len(parts) < 2:
        return {}
    fm_text = parts[0]
    # Simple key: value parser for our frontmatter format
    result: dict[str, Any] = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # Handle list values (sources:)
        if value == "":
            # This might be a list start, handle inline
            continue
        result[key] = value
    return result


def _parse_sources_from_text(text: str) -> list[dict]:
    """Parse source records from markdown text.

    Supports both canonical and legacy source key names:
    - canonical: source_type/source_ref/retrieved_at/mapper_version
    - legacy:    type/ref/retrieved
    """
    sources: list[dict] = []
    in_sources = False
    current_source: dict[str, str] = {}

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "sources:":
            in_sources = True
            current_source = {}
            continue
        if in_sources:
            if stripped.startswith("- source_type:"):
                if current_source:
                    sources.append(current_source)
                current_source = {"source_type": stripped.split(":", 1)[1].strip()}
            elif stripped.startswith("- type:"):
                if current_source:
                    sources.append(current_source)
                current_source = {"source_type": stripped.split(":", 1)[1].strip()}
            elif stripped.startswith("source_ref:"):
                current_source["source_ref"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("ref:"):
                current_source["source_ref"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("retrieved_at:"):
                current_source["retrieved_at"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("retrieved:"):
                current_source["retrieved_at"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("mapper_version:"):
                current_source["mapper_version"] = stripped.split(":", 1)[1].strip().strip('"')
            elif stripped == "---" or stripped.startswith("## ") or stripped.startswith("# "):
                # End of sources/frontmatter block
                if current_source:
                    sources.append(current_source)
                    current_source = {}
                in_sources = False

    if current_source:
        sources.append(current_source)

    return sources


def _validate_id_canonical(entity_id: str) -> list[str]:
    """Validate id_canonical format (prefix:slug)."""
    errors = []
    if not entity_id:
        errors.append("missing_id_canonical")
        return errors

    has_valid_prefix = any(entity_id.startswith(p) for p in ID_PREFIXES)
    if not has_valid_prefix:
        errors.append(f"invalid_id_prefix:{entity_id}")

    if ":" not in entity_id:
        errors.append(f"missing_colon_separator:{entity_id}")

    return errors


def _validate_source_record(source: dict, idx: int) -> list[str]:
    """Validate a single source record."""
    errors = []
    prefix = f"sources[{idx}]"

    if "source_type" not in source:
        errors.append(f"{prefix}.missing_source_type")
    elif source["source_type"] not in SOURCE_TYPES:
        errors.append(f"{prefix}.invalid_source_type:{source['source_type']}")

    if "source_ref" not in source:
        errors.append(f"{prefix}.missing_source_ref")

    if "retrieved_at" not in source:
        errors.append(f"{prefix}.missing_retrieved_at")

    if "mapper_version" not in source:
        errors.append(f"{prefix}.missing_mapper_version")

    return errors


def _validate_confidence(confidence: str | None) -> list[str]:
    """Validate confidence value is in enum."""
    errors = []
    if confidence and confidence not in CONFIDENCE_LEVELS:
        errors.append(f"invalid_confidence:{confidence}")
    return errors


def _validate_relationship_edge(edge: dict) -> list[str]:
    """Validate a relationship edge dict."""
    errors = []

    if "from_id" not in edge:
        errors.append("relationship.missing_from_id")
    elif not is_valid_id_prefix(edge["from_id"]):
        errors.append(f"relationship.invalid_from_id:{edge['from_id']}")

    if "to_id" not in edge:
        errors.append("relationship.missing_to_id")
    elif not is_valid_id_prefix(edge["to_id"]):
        errors.append(f"relationship.invalid_to_id:{edge['to_id']}")

    if "role" not in edge:
        errors.append("relationship.missing_role")
    elif edge["role"] not in RELATIONSHIP_ROLES:
        errors.append(f"relationship.invalid_role:{edge['role']}")

    if "confidence" in edge and edge["confidence"] not in CONFIDENCE_LEVELS:
        errors.append(f"relationship.invalid_confidence:{edge['confidence']}")

    return errors


def validate_vault_file(path: Path) -> list[str]:
    """Validate a single vault file for domain compliance.

    Returns list of error strings (empty if valid).
    """
    errors: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"read_error:{path.name}:{str(e)}"]

    fm = _parse_frontmatter(text)

    # Validate entity type
    entity_type = fm.get("type", "")
    if not entity_type:
        errors.append("missing_type_field")

    # Validate canonical id
    id_canonical = fm.get("id_canonical", "")
    if not id_canonical:
        errors.append("missing_id_canonical")
    else:
        errors.extend(_validate_id_canonical(id_canonical))

    # Validate confidence
    confidence = fm.get("confidence")
    errors.extend(_validate_confidence(confidence))

    # Validate sources
    sources = _parse_sources_from_text(text)
    for idx, source in enumerate(sources):
        errors.extend(_validate_source_record(source, idx))

    return errors


def validate_relationships_in_vault(vault_root: Path) -> dict[str, Any]:
    """Scan vault for relationship data and validate.

    Returns dict with validation results.
    """
    results: dict[str, Any] = {
        "relationships_valid": True,
        "relationship_errors": [],
        "edges_checked": 0,
    }

    # Look for relationship data files
    rel_dir = vault_root / "relationships"
    if not rel_dir.exists():
        # No relationships yet - this is valid
        return results

    for rel_file in rel_dir.glob("*.json"):
        try:
            import json
            data = json.loads(rel_file.read_text(encoding="utf-8"))
            edges = data if isinstance(data, list) else data.get("edges", [])
            for edge in edges:
                results["edges_checked"] += 1
                edge_errors = _validate_relationship_edge(edge)
                if edge_errors:
                    results["relationships_valid"] = False
                    results["relationship_errors"].extend(edge_errors)
        except Exception as e:
            results["relationship_errors"].append(f"file_error:{rel_file.name}:{str(e)}")

    return results


def run_domain_lint(vault_root: Path) -> dict[str, Any]:
    """Run full domain lint on vault root.

    Returns dict with:
    - errors: list of domain quality errors
    - files_checked: count of files validated
    - relationships_valid: bool
    - relationship_errors: list of relationship validation errors
    - summary: human-readable summary dict
    """
    errors: list[str] = []
    files_checked = 0
    entity_errors = 0
    source_errors = 0

    # Find all decision and entity files
    for subdir in ("decisions", "entities", "concepts"):
        dir_path = vault_root / subdir
        if not dir_path.exists():
            continue

        for md_file in dir_path.glob("*.md"):
            files_checked += 1
            file_errors = validate_vault_file(md_file)
            if file_errors:
                errors.extend([f"{md_file.name}:{e}" for e in file_errors])
                entity_errors += 1
                source_errors += sum(1 for e in file_errors if "source" in e)

    # Validate relationships
    rel_results = validate_relationships_in_vault(vault_root)
    errors.extend(rel_results.get("relationship_errors", []))

    return {
        "errors": errors,
        "files_checked": files_checked,
        "entity_errors": entity_errors,
        "source_errors": source_errors,
        "relationships_valid": rel_results.get("relationships_valid", True),
        "relationship_errors": rel_results.get("relationship_errors", []),
        "edges_checked": rel_results.get("edges_checked", 0),
        "summary": {
            "total_errors": len(errors),
            "valid": len(errors) == 0 and rel_results.get("relationships_valid", True),
        },
    }
