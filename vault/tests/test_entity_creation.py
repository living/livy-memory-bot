from pathlib import Path
import yaml


REQUIRED_FIELDS = {
    "entity",
    "type",
    "confidence",
    "sources",
    "last_verified",
    "last_touched_by",
}


TYPE_ALLOWED = {"entity", "decision", "concept", "evidence"}
CONF_ALLOWED = {"high", "medium", "low", "unverified"}


def _extract_frontmatter(text: str):
    assert text.startswith("---\n"), "Missing YAML frontmatter start"
    parts = text.split("---", 2)
    assert len(parts) >= 3, "Invalid frontmatter delimiters"
    return yaml.safe_load(parts[1])


def test_entity_pages_have_valid_frontmatter_if_any_exist():
    root = Path(__file__).resolve().parents[2]
    entities_dir = root / "memory" / "vault" / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)

    for page in entities_dir.glob("*.md"):
        data = _extract_frontmatter(page.read_text(encoding="utf-8"))
        missing = REQUIRED_FIELDS - set(data.keys())
        assert not missing, f"{page.name} missing fields: {sorted(missing)}"
        assert data["type"] in TYPE_ALLOWED
        assert data["confidence"] in CONF_ALLOWED
        assert isinstance(data["sources"], list)


def test_schema_frontmatter_example_contains_required_fields():
    root = Path(__file__).resolve().parents[2]
    agents_md = root / "memory" / "vault" / "schema" / "AGENTS.md"
    content = agents_md.read_text(encoding="utf-8")

    for field in REQUIRED_FIELDS:
        assert field in content, f"Field {field} not documented in schema"
