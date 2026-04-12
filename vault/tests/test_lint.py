import pytest
from pathlib import Path


def test_auto_fix_removes_orphan_wikilinks(tmp_path):
    """Auto-fix should remove [[wiki-links]] pointing to non-existent files."""
    from vault.lint.auto_fix import auto_fix_orphan_links

    vault = tmp_path / "vault"
    entities = vault / "entities" / "meetings"
    entities.mkdir(parents=True)

    # Meeting file referencing a non-existent person
    meeting = entities / "test-meeting.md"
    meeting.write_text(
        "---\ntype: meeting\n---\n\n"
        "# Test\n\n"
        "## Participantes\n\n"
        "- [[Nonexistent Person]]\n"
        "- [[Existing Person]]\n"
    )

    # Create the existing person
    persons = vault / "entities" / "persons"
    persons.mkdir(parents=True)
    (persons / "Existing Person.md").write_text("---\ntype: person\n---\n\n# Existing Person\n")

    fixes = auto_fix_orphan_links(vault)
    assert fixes["orphan_links_removed"] >= 1
    text = meeting.read_text()
    assert "[[Nonexistent Person]]" not in text
    assert "[[Existing Person]]" in text


def test_auto_fix_no_orphans(tmp_path):
    """No changes when all links are valid."""
    from vault.lint.auto_fix import auto_fix_orphan_links

    vault = tmp_path / "vault"
    entities = vault / "entities" / "meetings"
    entities.mkdir(parents=True)
    persons = vault / "entities" / "persons"
    persons.mkdir(parents=True)

    (persons / "Alice.md").write_text("---\ntype: person\n---\n\n# Alice\n")
    meeting = entities / "test.md"
    meeting.write_text("# Test\n\n- [[Alice]]\n")

    fixes = auto_fix_orphan_links(vault)
    assert fixes["orphan_links_removed"] == 0
    assert fixes["files_modified"] == 0
