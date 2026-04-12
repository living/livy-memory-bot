"""Task 14: Integration test — full crosslink pipeline end-to-end."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

import yaml

from vault.ingest.crosslink_builder import run_crosslink
from vault.ingest.index_manager import rebuild_index
from vault.ingest.vault_lint_scanner import run_lint_scans


def _setup_full_vault(tmp_path: Path) -> Path:
    """Create a complete vault with meetings, persons, projects, enrichment."""
    vault = tmp_path / "vault"
    schema = vault.parent / "schema"

    # Directories
    for d in ["entities/meetings", "entities/persons", "entities/projects",
              "entities/cards", "entities/prs", "relationships"]:
        (vault / d).mkdir(parents=True)
    schema.mkdir(parents=True)

    # Mapping configs
    (schema / "trello-member-map.yaml").write_text(yaml.dump({
        "members": {"mem1": "Lincoln Quinan Junior", "mem2": "Robert Urech"}
    }))
    (schema / "repo-project-map.yaml").write_text(yaml.dump({
        "repos": {"living/bat-api": "BAT/Kaba", "living/delphos": "Delphos"}
    }))
    (schema / "board-project-map.yaml").write_text(yaml.dump({
        "boards": {"board-bat": "BAT/Kaba", "board-delphos": "Delphos"}
    }))

    # Persons
    for name in ["Lincoln Quinan Junior", "Robert Urech"]:
        slug = name.replace("/", " - ")  # simplified
        (vault / "entities" / "persons" / f"{slug}.md").write_text(
            f"---\nentity: \"{name}\"\ntype: person\n---\n\n# {name}\n",
            encoding="utf-8",
        )

    # Meeting with enrichment_context
    ec = {
        "trello": {
            "cards": [
                {"id": "card1", "name": "Fix login bug", "url": "https://trello.com/c/card1",
                 "board_id": "board-bat",
                 "members": [{"id": "mem1", "fullName": "Lincoln Quinan Junior", "username": "lincolnq"}]},
                {"id": "card2", "name": "Add report", "url": "https://trello.com/c/card2",
                 "board_id": "board-delphos",
                 "members": [{"id": "mem2", "fullName": "Robert Urech", "username": "robertu"}]},
            ]
        },
        "github": {
            "pull_requests": [
                {"url": "https://github.com/living/bat-api/pull/42", "title": "Fix auth",
                 "repo": "living/bat-api", "number": 42},
                {"url": "https://github.com/living/delphos/pull/7", "title": "Add vistoria",
                 "repo": "living/delphos", "number": 7},
            ]
        }
    }
    meeting_fm = {
        "entity": "Status Kaba/BAT/BOT 2024-04-11",
        "type": "meeting",
        "id_canonical": "meeting:tldv:test-integration",
        "enrichment_context": ec,
    }
    fm_text = yaml.dump(meeting_fm, default_flow_style=False, sort_keys=False)
    (vault / "entities" / "meetings" / "2024-04-11 Status Kaba.md").write_text(
        f"---\n{fm_text}---\n\n# Status Kaba/BAT/BOT\n\n## Contexto\n\n- 📋 [Old card](url)\n",
        encoding="utf-8",
    )

    # Person-meeting relationship
    (vault / "relationships" / "person-meeting.json").write_text(
        json.dumps({"edges": [
            {"from_id": "person:lincoln", "to_id": "meeting:test"},
        ]}),
        encoding="utf-8",
    )

    return vault


class TestCrosslinkIntegration:
    """Full end-to-end crosslink pipeline."""

    def test_full_pipeline(self, tmp_path):
        vault = _setup_full_vault(tmp_path)

        # Run crosslink
        with patch("vault.ingest.crosslink_resolver.resolve_pr_author",
                    side_effect=lambda pr, *a, **kw: "Lincoln Quinan Junior"):
            result = run_crosslink(vault, dry_run=False, github_token="fake")

        # Verify relationship files
        rel_dir = vault / "relationships"
        for name in ["card-person.json", "card-project.json", "pr-person.json", "pr-project.json"]:
            assert (rel_dir / name).exists(), f"{name} not created"

        # Verify edge counts
        cp = json.loads((rel_dir / "card-person.json").read_text())
        assert len(cp["edges"]) >= 2  # 2 cards with members

        cproj = json.loads((rel_dir / "card-project.json").read_text())
        assert len(cproj["edges"]) == 2  # 2 cards mapped to projects

        prp = json.loads((rel_dir / "pr-person.json").read_text())
        assert len(prp["edges"]) >= 1

        prproj = json.loads((rel_dir / "pr-project.json").read_text())
        assert len(prproj["edges"]) == 2  # 2 PRs mapped to projects

        # Verify PR entities created
        prs_dir = vault / "entities" / "prs"
        pr_files = list(prs_dir.glob("*.md"))
        assert len(pr_files) >= 2

        # Verify stats
        assert result["cards"] == 2
        assert result["prs"] == 2
        assert result["edges"]["card_person"] >= 2
        assert result["edges"]["pr_project"] == 2

    def test_index_after_crosslink(self, tmp_path):
        vault = _setup_full_vault(tmp_path)

        with patch("vault.ingest.crosslink_resolver.resolve_pr_author",
                    side_effect=lambda pr, *a, **kw: "Lincoln Quinan Junior"):
            run_crosslink(vault, dry_run=False, github_token="fake")

        rebuild_index(vault)
        text = (vault / "index.md").read_text(encoding="utf-8")
        assert "🔀 PRs" in text or "PRs" in text
        assert "| PRs | 2 |" in text

    def test_lint_after_crosslink(self, tmp_path):
        vault = _setup_full_vault(tmp_path)

        with patch("vault.ingest.crosslink_resolver.resolve_pr_author",
                    side_effect=lambda pr, *a, **kw: "Lincoln Quinan Junior"):
            run_crosslink(vault, dry_run=False, github_token="fake")

        report = run_lint_scans(vault)
        metrics = report["metrics"]
        assert metrics["total_relationships"] >= 6  # person-meeting + 4 crosslink files
        assert "crosslink_edges" in metrics
        assert metrics["crosslink_edges"]["card-project"] == 2
        assert metrics["crosslink_edges"]["pr-project"] == 2

    def test_idempotent(self, tmp_path):
        vault = _setup_full_vault(tmp_path)

        with patch("vault.ingest.crosslink_resolver.resolve_pr_author",
                    side_effect=lambda pr, *a, **kw: "Lincoln Quinan Junior"):
            r1 = run_crosslink(vault, dry_run=False, github_token="fake")
            r2 = run_crosslink(vault, dry_run=False, github_token="fake")

        # Second run should produce same results
        assert r1["cards"] == r2["cards"]
        assert r1["prs"] == r2["prs"]
