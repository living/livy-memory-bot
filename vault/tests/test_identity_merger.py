import pytest
from pathlib import Path
import yaml


def test_dedup_with_identity_map_merges(tmp_path):
    """dedup_with_identity_map merges duplicates using identity map."""
    from vault.ingest.crosslink_dedup import dedup_with_identity_map

    # Setup vault structure
    persons = tmp_path / "entities" / "persons"
    persons.mkdir(parents=True)

    # "Lincoln" (from Trello) — matches identity map canonical "Lincoln Quinan Junior"
    (persons / "Lincoln.md").write_text(
        "---\n"
        'entity: "Lincoln"\n'
        "type: person\n"
        "source_keys:\n"
        "  - trello-member:Lincoln\n"
        "---\n\n"
        "# Lincoln\n\n"
        "## Cards\n\n"
        "- [[card-1]]\n"
    )

    # "lincolnqjunior" (from GitHub) — also matches "Lincoln Quinan Junior"
    (persons / "lincolnqjunior.md").write_text(
        "---\n"
        'entity: "lincolnqjunior"\n'
        "type: person\n"
        "github_login: lincolnqjunior\n"
        "source_keys:\n"
        "  - github:lincolnqjunior\n"
        "draft: true\n"
        "---\n\n"
        "# lincolnqjunior\n\n"
        "## PRs\n\n"
        "- [[pr-1]]\n"
    )

    merged = dedup_with_identity_map(tmp_path)

    assert merged >= 1
    # One file should remain, one in quarantine
    remaining = list(persons.glob("*.md"))
    quarantine = list((persons / ".quarantine").glob("*.md"))
    assert len(remaining) == 1
    assert len(quarantine) == 1
    # Remaining file should have merged content
    text = remaining[0].read_text()
    assert "Lincoln Quinan Junior" in text


def test_dedup_identity_map_no_duplicates(tmp_path):
    """No merges needed when no duplicates exist."""
    from vault.ingest.crosslink_dedup import dedup_with_identity_map

    persons = tmp_path / "entities" / "persons"
    persons.mkdir(parents=True)

    # Single person that doesn't match identity map
    (persons / "unknown-person.md").write_text(
        "---\n"
        'entity: "unknown-person"\n'
        "type: person\n"
        "---\n\n"
        "# unknown-person\n"
    )

    merged = dedup_with_identity_map(tmp_path)
    assert merged == 0
    assert len(list(persons.glob("*.md"))) == 1
