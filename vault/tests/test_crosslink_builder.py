"""Tests for crosslink_builder module."""

import json
import pytest
from pathlib import Path
import yaml

from unittest.mock import patch, MagicMock

from vault.ingest.crosslink_builder import (
    resolve_card_members,
    save_trello_member_map,
    resolve_pr_author,
    fetch_prs_for_repos,
    run_crosslink,
)


# ---------------------------------------------------------------------------
# resolve_card_members
# ---------------------------------------------------------------------------

class TestResolveCardMembersAllMapped:
    def test_all_mapped(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "entities" / "persons").mkdir(parents=True)

        member_map = {"abc123": "Victor Hugo", "def456": "Lincoln Quinan"}
        card = {
            "members": [
                {"id": "abc123", "fullName": "Victor Hugo", "username": "victorhugo"},
                {"id": "def456", "fullName": "Lincoln Quinan Junior", "username": "lincolnq"},
            ]
        }
        result = resolve_card_members(card, member_map, vault)
        assert sorted(result) == ["Lincoln Quinan", "Victor Hugo"]


class TestResolveCardMembersFuzzyMatch:
    def test_fuzzy_match(self, tmp_path):
        vault = tmp_path / "vault"
        persons = vault / "entities" / "persons"
        persons.mkdir(parents=True)
        (persons / "victor-hugo.md").write_text(
            '---\nentity: "Victor Hugo"\ntype: person\n---\n# Victor Hugo\n'
        )
        card = {"members": [{"id": "abc123", "fullName": "Victor Hugo", "username": "victorhugo"}]}
        result = resolve_card_members(card, {}, vault)
        assert result == ["Victor Hugo"]


class TestResolveCardMembersPartial:
    def test_partial(self, tmp_path):
        vault = tmp_path / "vault"
        persons = vault / "entities" / "persons"
        persons.mkdir(parents=True)
        (persons / "victor-hugo.md").write_text(
            '---\nentity: "Victor Hugo"\ntype: person\n---\n# Victor Hugo\n'
        )
        member_map = {"def456": "Lincoln Quinan"}
        card = {
            "members": [
                {"id": "abc123", "fullName": "Victor Hugo", "username": "victorhugo"},
                {"id": "def456", "fullName": "Lincoln Quinan Junior", "username": "lincolnq"},
            ]
        }
        result = resolve_card_members(card, member_map, vault)
        assert sorted(result) == ["Lincoln Quinan", "Victor Hugo"]


class TestResolveCardMembersNoMembers:
    def test_no_members(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = resolve_card_members({"members": []}, {}, vault)
        assert result == []

    def test_missing_members_key(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        result = resolve_card_members({}, {}, vault)
        assert result == []


class TestResolveCardMembersCreatesDraftPerson:
    def test_creates_draft(self, tmp_path):
        vault = tmp_path / "vault"
        persons = vault / "entities" / "persons"
        persons.mkdir(parents=True)
        card = {"members": [{"id": "xyz789", "fullName": "New Person", "username": "newperson"}]}
        result = resolve_card_members(card, {}, vault)
        assert result == ["New Person"]
        drafts = list(persons.glob("*.md"))
        assert len(drafts) == 1
        content = drafts[0].read_text()
        assert "draft: true" in content
        assert "New Person" in content


class TestResolveCardMembersAutoPopulatesMap:
    def test_auto_populate(self, tmp_path):
        vault = tmp_path / "vault"
        persons = vault / "entities" / "persons"
        schema = tmp_path / "schema"
        persons.mkdir(parents=True)
        schema.mkdir()
        card = {"members": [{"id": "abc123", "fullName": "Victor Hugo", "username": "victorhugo"}]}
        member_map = {}
        result = resolve_card_members(card, member_map, vault, schema_dir=schema)
        assert result == ["Victor Hugo"]
        assert member_map == {"abc123": "Victor Hugo"}
        map_file = schema / "trello-member-map.yaml"
        assert map_file.exists()
        data = yaml.safe_load(map_file.read_text())
        assert data["members"]["abc123"] == "Victor Hugo"


class TestSaveTrelloMemberMap:
    def test_roundtrip(self, tmp_path):
        m = {"z1": "Alice", "a2": "Bob"}
        save_trello_member_map(tmp_path, m)
        data = yaml.safe_load((tmp_path / "trello-member-map.yaml").read_text())
        assert data["members"] == m


# ---------------------------------------------------------------------------
# resolve_pr_author
# ---------------------------------------------------------------------------

class TestResolvePRAuthorByGithubLogin:
    def test_match_by_github_login(self, tmp_path):
        vault = tmp_path / "vault"
        persons = vault / "entities" / "persons"
        persons.mkdir(parents=True)
        (persons / "lincoln.md").write_text(
            '---\nentity: "Lincoln Quinan"\ntype: person\ngithub_login: lincolnq\n---\n# Lincoln Quinan\n'
        )
        pr_data = {"url": "https://github.com/living/repo/pull/7", "number": 7}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"user": {"login": "lincolnq"}}
        with patch("vault.ingest.crosslink_builder.requests.get", return_value=mock_resp):
            result = resolve_pr_author(pr_data, vault, github_token="fake")
        assert result == "Lincoln Quinan"


class TestResolvePRAuthorFuzzyMatch:
    def test_fuzzy_name_match(self, tmp_path):
        vault = tmp_path / "vault"
        persons = vault / "entities" / "persons"
        persons.mkdir(parents=True)
        (persons / "victor.md").write_text(
            '---\nentity: "Victor"\ntype: person\n---\n# Victor\n'
        )
        pr_data = {"url": "https://github.com/living/repo/pull/5", "number": 5}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"user": {"login": "Victor"}}
        with patch("vault.ingest.crosslink_builder.requests.get", return_value=mock_resp):
            result = resolve_pr_author(pr_data, vault, github_token="fake")
        assert result == "Victor"


class TestResolvePRAuthorCreatesDraft:
    def test_creates_draft(self, tmp_path):
        vault = tmp_path / "vault"
        persons = vault / "entities" / "persons"
        persons.mkdir(parents=True)
        pr_data = {"url": "https://github.com/living/repo/pull/3", "number": 3}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"user": {"login": "newcontributor"}}
        with patch("vault.ingest.crosslink_builder.requests.get", return_value=mock_resp):
            result = resolve_pr_author(pr_data, vault, github_token="fake")
        assert result == "newcontributor"
        drafts = list(persons.glob("*.md"))
        assert len(drafts) == 1
        assert "draft: true" in drafts[0].read_text()


class TestResolvePRAuthorNoMatchNoDraft:
    def test_no_token(self, tmp_path):
        vault = tmp_path / "vault"
        persons = vault / "entities" / "persons"
        persons.mkdir(parents=True)
        pr_data = {"url": "https://github.com/living/repo/pull/1", "number": 1}
        result = resolve_pr_author(pr_data, vault, github_token=None)
        assert result is None


# ---------------------------------------------------------------------------
# fetch_prs_for_repos
# ---------------------------------------------------------------------------

class TestFetchPRsForReposSuccess:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"title": "feat: add X", "html_url": "https://github.com/living/repo/pull/1",
             "merged_at": "2026-04-10T00:00:00Z", "user": {"login": "dev1"}},
        ]
        with patch("vault.ingest.crosslink_builder.requests.get", return_value=mock_resp):
            result = fetch_prs_for_repos(["living/repo"], github_token="fake")
        assert len(result) == 1
        assert result[0]["repo"] == "living/repo"
        assert result[0]["user_login"] == "dev1"


class TestFetchPRsForReposEmpty:
    def test_empty(self):
        result = fetch_prs_for_repos([], github_token="fake")
        assert result == []


class TestFetchPRsForReposAPIError:
    def test_api_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "rate limited"
        with patch("vault.ingest.crosslink_builder.requests.get", return_value=mock_resp):
            result = fetch_prs_for_repos(["living/repo"], github_token="fake")
        assert result == []


# ---------------------------------------------------------------------------
# run_crosslink — Task 7 orchestration tests
# ---------------------------------------------------------------------------

def _setup_vault(tmp_path: Path, meeting_data: dict | None = None) -> Path:
    """Create a minimal vault with a meeting entity containing enrichment_context."""
    vault = tmp_path / "vault"
    schema = vault.parent / "schema"  # vault_root.parent / "schema"
    schema.mkdir(parents=True)

    # Write mapping configs
    (schema / "trello-member-map.yaml").write_text(yaml.dump({
        "members": {"member1": "Lincoln Quinan"}
    }))
    (schema / "repo-project-map.yaml").write_text(yaml.dump({
        "repos": {"living/repo": "BAT/Kaba"}
    }))
    (schema / "board-project-map.yaml").write_text(yaml.dump({
        "boards": {"board1": "BAT/Kaba"}
    }))

    if meeting_data is None:
        meeting_data = {
            "id_canonical": "meeting:tldv:abc",
            "enrichment_context": {
                "trello": {
                    "cards": [
                        {"id": "card1", "name": "Fix login", "url": "https://trello.com/c/card1",
                         "board_id": "board1", "members": [{"id": "member1", "fullName": "Lincoln Quinan", "username": "lincolnq"}]},
                    ]
                },
                "github": {
                    "pull_requests": [
                        {"url": "https://github.com/living/repo/pull/7", "title": "Fix bug", "repo": "living/repo"},
                    ]
                }
            }
        }

    # Write meeting entity
    meetings_dir = vault / "entities" / "meetings"
    meetings_dir.mkdir(parents=True)
    (vault / "entities" / "persons").mkdir(parents=True)
    (vault / "entities" / "cards").mkdir(parents=True)
    (vault / "entities" / "prs").mkdir(parents=True)
    (vault / "relationships").mkdir(parents=True)

    # Build meeting frontmatter
    ec = meeting_data.get("enrichment_context", {})
    import json as _json
    ec_yaml = yaml.dump(ec, default_flow_style=False) if ec else "{}\n"

    meeting_md = (
        "---\n"
        f"entity: \"Test Meeting\"\n"
        f"type: meeting\n"
        f"id_canonical: {meeting_data.get('id_canonical', 'meeting:tldv:test')}\n"
        f"enrichment_context:\n"
    )
    # Write enrichment_context as YAML properly
    meeting_content = f"---\nentity: \"Test Meeting\"\ntype: meeting\nid_canonical: {meeting_data.get('id_canonical', 'meeting:tldv:test')}\n---\n\n# Test Meeting\n"
    (meetings_dir / "test-meeting.md").write_text(meeting_content, encoding="utf-8")

    return vault


def _setup_vault_with_enrichment(tmp_path: Path) -> Path:
    """Create vault with meeting enrichment_context stored in a sidecar JSON."""
    vault = tmp_path / "vault"
    schema = vault.parent / "schema"
    schema.mkdir(parents=True)

    (schema / "trello-member-map.yaml").write_text(yaml.dump({"members": {"member1": "Lincoln Quinan"}}))
    (schema / "repo-project-map.yaml").write_text(yaml.dump({"repos": {"living/repo": "BAT/Kaba"}}))
    (schema / "board-project-map.yaml").write_text(yaml.dump({"boards": {"board1": "BAT/Kaba"}}))

    meetings_dir = vault / "entities" / "meetings"
    meetings_dir.mkdir(parents=True)
    (vault / "entities" / "persons").mkdir(parents=True)
    (vault / "entities" / "cards").mkdir(parents=True)
    (vault / "entities" / "prs").mkdir(parents=True)
    (vault / "relationships").mkdir(parents=True)

    # Write meeting with enrichment_context in frontmatter
    ec = {
        "trello": {
            "cards": [
                {"id": "card1", "name": "Fix login", "url": "https://trello.com/c/card1",
                 "board_id": "board1", "members": [{"id": "member1", "fullName": "Lincoln Quinan", "username": "lincolnq"}]},
            ]
        },
        "github": {
            "pull_requests": [
                {"url": "https://github.com/living/repo/pull/7", "title": "Fix bug", "repo": "living/repo"},
            ]
        }
    }
    meeting_fm = {
        "entity": "Test Meeting",
        "type": "meeting",
        "id_canonical": "meeting:tldv:test123",
        "enrichment_context": ec,
    }
    import io
    fm_text = yaml.dump(meeting_fm, default_flow_style=False, sort_keys=False)
    meeting_md = f"---\n{fm_text}---\n\n# Test Meeting\n"
    (meetings_dir / "test-meeting.md").write_text(meeting_md, encoding="utf-8")

    return vault


class TestRunCrosslinkDryRun:
    """Dry run returns summary but writes nothing."""

    def test_dry_run(self, tmp_path):
        vault = _setup_vault_with_enrichment(tmp_path)
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            result = run_crosslink(vault, dry_run=True, github_token="fake")
        assert isinstance(result, dict)
        assert "cards" in result or "prs" in result or "edges" in result or "dry_run" in result
        # No relationship files written
        rel_dir = vault / "relationships"
        # In dry run, no new files should be created (only the dirs we made)
        assert not any(rel_dir.glob("*.json"))


class TestRunCrosslinkCreatesRelationships:
    """All 4 relationship files written."""

    def test_creates_all_files(self, tmp_path):
        vault = _setup_vault_with_enrichment(tmp_path)
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            result = run_crosslink(vault, dry_run=False, github_token="fake")
        rel_dir = vault / "relationships"
        files = {f.name for f in rel_dir.glob("*.json")}
        assert "card-person.json" in files
        assert "card-project.json" in files
        assert "pr-person.json" in files
        assert "pr-project.json" in files


class TestRunCrosslinkCardToPerson:
    """card-person edge created."""

    def test_card_person_edge(self, tmp_path):
        vault = _setup_vault_with_enrichment(tmp_path)
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            run_crosslink(vault, dry_run=False, github_token="fake")
        data = json.loads((vault / "relationships" / "card-person.json").read_text())
        edges = data.get("edges", [])
        assert len(edges) >= 1
        assert any("card1" in e.get("from_id", "") for e in edges)
        assert any("member1" in e.get("to_id", "") or "Lincoln" in e.get("to_id", "") for e in edges)


class TestRunCrosslinkPRToPerson:
    """pr-person edge created."""

    def test_pr_person_edge(self, tmp_path):
        vault = _setup_vault_with_enrichment(tmp_path)
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            run_crosslink(vault, dry_run=False, github_token="fake")
        data = json.loads((vault / "relationships" / "pr-person.json").read_text())
        edges = data.get("edges", [])
        assert len(edges) >= 1


class TestRunCrosslinkCardToProject:
    """card-project edge created via board-project-map."""

    def test_card_project_edge(self, tmp_path):
        vault = _setup_vault_with_enrichment(tmp_path)
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            run_crosslink(vault, dry_run=False, github_token="fake")
        data = json.loads((vault / "relationships" / "card-project.json").read_text())
        edges = data.get("edges", [])
        assert len(edges) >= 1
        assert any("card1" in e.get("from_id", "") for e in edges)


class TestRunCrosslinkPRToProject:
    """pr-project edge created via repo-project-map."""

    def test_pr_project_edge(self, tmp_path):
        vault = _setup_vault_with_enrichment(tmp_path)
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            run_crosslink(vault, dry_run=False, github_token="fake")
        data = json.loads((vault / "relationships" / "pr-project.json").read_text())
        edges = data.get("edges", [])
        assert len(edges) >= 1


class TestRunCrosslinkNoEnrichment:
    """Handles empty vault gracefully."""

    def test_empty_vault(self, tmp_path):
        vault = tmp_path / "vault"
        schema = vault.parent / "schema"
        schema.mkdir(parents=True)
        (schema / "trello-member-map.yaml").write_text("members: {}\n")
        (schema / "repo-project-map.yaml").write_text("repos: {}\n")
        (schema / "board-project-map.yaml").write_text("boards: {}\n")
        vault.mkdir(parents=True)
        (vault / "entities" / "meetings").mkdir(parents=True)
        (vault / "relationships").mkdir(parents=True)
        result = run_crosslink(vault, dry_run=False, github_token="fake")
        assert isinstance(result, dict)


class TestRunCrosslinkUnmappedEntities:
    """Skips unmapped without error."""

    def test_unmapped(self, tmp_path):
        vault = tmp_path / "vault"
        schema = vault.parent / "schema"
        schema.mkdir(parents=True)
        # Empty maps — nothing resolves
        (schema / "trello-member-map.yaml").write_text("members: {}\n")
        (schema / "repo-project-map.yaml").write_text("repos: {}\n")
        (schema / "board-project-map.yaml").write_text("boards: {}\n")

        meetings_dir = vault / "entities" / "meetings"
        meetings_dir.mkdir(parents=True)
        (vault / "entities" / "persons").mkdir(parents=True)
        (vault / "entities" / "cards").mkdir(parents=True)
        (vault / "entities" / "prs").mkdir(parents=True)
        (vault / "relationships").mkdir(parents=True)

        # Meeting with card/PR but no mappings
        ec = {
            "trello": {
                "cards": [
                    {"id": "cardX", "name": "Unknown card", "board_id": "unknown_board",
                     "members": [{"id": "unknown_member", "fullName": "Nobody", "username": "nobody"}]},
                ]
            },
            "github": {
                "pull_requests": [
                    {"url": "https://github.com/unknown/repo/pull/1", "title": "Unknown PR", "repo": "unknown/repo"},
                ]
            }
        }
        meeting_fm = {
            "entity": "Unmapped Meeting",
            "type": "meeting",
            "id_canonical": "meeting:tldv:unmapped",
            "enrichment_context": ec,
        }
        fm_text = yaml.dump(meeting_fm, default_flow_style=False, sort_keys=False)
        (meetings_dir / "unmapped.md").write_text(f"---\n{fm_text}---\n\n# Unmapped\n", encoding="utf-8")

        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value=None):
            result = run_crosslink(vault, dry_run=False, github_token=None)
        assert isinstance(result, dict)
        # Should not crash — edges may be empty
