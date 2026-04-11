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


TYPE_ALLOWED = {"entity", "decision", "concept", "evidence", "meeting", "card", "person"}
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


# --- PR Entity Writer Tests ---
from vault.ingest.entity_writer import upsert_pr, _entity_path


class TestUpsertPr:
    """Tests for upsert_pr() writer."""

    def _sample_pr(self, **overrides):
        base = {
            "entity": "Fix login redirect",
            "type": "pr",
            "id_canonical": "pr:living/AbsRio-ApiCRM:42",
            "pr_id_source": 42,
            "repo": "living/AbsRio-ApiCRM",
            "title": "Fix login redirect",
            "author": "Lincoln Quinan Junior",
            "project_ref": "BAT/Kaba",
            "confidence": "medium",
            "source_keys": ["github:living/AbsRio-ApiCRM:42"],
            "merged_at": "2026-04-10",
            "draft": False,
        }
        base.update(overrides)
        return base

    def test_upsert_pr_creates_file(self, tmp_path):
        entity = self._sample_pr()
        path, written = upsert_pr(entity, vault_root=tmp_path)
        assert written is True
        assert path.exists()
        assert path.parent == tmp_path / "entities" / "prs"
        text = path.read_text(encoding="utf-8")
        assert "Fix login redirect" in text
        assert "type: pr" in text

    def test_upsert_pr_idempotent(self, tmp_path):
        entity = self._sample_pr()
        path1, w1 = upsert_pr(entity, vault_root=tmp_path)
        path2, w2 = upsert_pr(entity, vault_root=tmp_path)
        assert w1 is True
        assert w2 is False
        assert path1 == path2

    def test_upsert_pr_includes_author_wikilink(self, tmp_path):
        entity = self._sample_pr(author="Lincoln Quinan Junior")
        path, _ = upsert_pr(entity, vault_root=tmp_path)
        text = path.read_text(encoding="utf-8")
        assert "[[Lincoln Quinan Junior]]" in text

    def test_upsert_pr_includes_project_wikilink(self, tmp_path):
        entity = self._sample_pr(project_ref="BAT/Kaba")
        path, _ = upsert_pr(entity, vault_root=tmp_path)
        text = path.read_text(encoding="utf-8")
        assert "[[BAT/Kaba]]" in text

    def test_upsert_pr_no_author(self, tmp_path):
        entity = self._sample_pr(author=None)
        del entity["author"]
        path, written = upsert_pr(entity, vault_root=tmp_path)
        assert written is True
        text = path.read_text(encoding="utf-8")
        assert "Autor" not in text

    def test_upsert_pr_no_project(self, tmp_path):
        entity = self._sample_pr(project_ref=None)
        path, written = upsert_pr(entity, vault_root=tmp_path)
        assert written is True
        text = path.read_text(encoding="utf-8")
        # Should not crash, no project wikilink
        assert "[[BAT/Kaba]]" not in text

    def test_entity_path_pr(self, tmp_path):
        entity = {"id_canonical": "pr:living/AbsRio-ApiCRM:42"}
        path = _entity_path(tmp_path, entity)
        assert path.parent == tmp_path / "entities" / "prs"
        assert path.suffix == ".md"


def test_schema_frontmatter_example_contains_required_fields():
    root = Path(__file__).resolve().parents[2]
    agents_md = root / "memory" / "vault" / "schema" / "AGENTS.md"
    content = agents_md.read_text(encoding="utf-8")

    for field in REQUIRED_FIELDS:
        assert field in content, f"Field {field} not documented in schema"
