"""Tests for crosslink_builder module."""

import pytest
from pathlib import Path
import yaml

from unittest.mock import patch, MagicMock

from vault.ingest.crosslink_builder import (
    resolve_card_members,
    save_trello_member_map,
    resolve_pr_author,
    fetch_prs_for_repos,
)


# ---------------------------------------------------------------------------
# resolve_card_members
# ---------------------------------------------------------------------------

class TestResolveCardMembersAllMapped:
    """All member IDs already in the map → returns names directly."""

    def test_all_mapped(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "entities" / "persons").mkdir(parents=True)

        member_map = {
            "abc123": "Victor Hugo",
            "def456": "Lincoln Quinan",
        }
        card = {
            "members": [
                {"id": "abc123", "fullName": "Victor Hugo", "username": "victorhugo"},
                {"id": "def456", "fullName": "Lincoln Quinan Junior", "username": "lincolnq"},
            ]
        }
        result = resolve_card_members(card, member_map, vault)
        assert sorted(result) == ["Lincoln Quinan", "Victor Hugo"]


class TestResolveCardMembersFuzzyMatch:
    """Member not in map but fuzzy matches an existing person file."""

    def test_fuzzy_match(self, tmp_path):
        vault = tmp_path / "vault"
        persons = vault / "entities" / "persons"
        persons.mkdir(parents=True)

        # Create a person file
        (persons / "victor-hugo.md").write_text(
            '---\nentity: "Victor Hugo"\ntype: person\n---\n# Victor Hugo\n'
        )

        card = {
            "members": [
                {"id": "abc123", "fullName": "Victor Hugo", "username": "victorhugo"},
            ]
        }
        result = resolve_card_members(card, {}, vault)
        assert result == ["Victor Hugo"]


class TestResolveCardMembersPartial:
    """Some mapped, some fuzzy matched."""

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
    """Empty members list → returns []."""

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
    """Unmapped member with no fuzzy match creates a draft person file."""

    def test_creates_draft(self, tmp_path):
        vault = tmp_path / "vault"
        persons = vault / "entities" / "persons"
        persons.mkdir(parents=True)

        card = {
            "members": [
                {"id": "xyz789", "fullName": "New Person", "username": "newperson"},
            ]
        }
        result = resolve_card_members(card, {}, vault)
        assert result == ["New Person"]

        # Check draft file created
        drafts = list(persons.glob("*.md"))
        assert len(drafts) == 1
        content = drafts[0].read_text()
        assert "draft: true" in content
        assert "New Person" in content
        assert "person:trello:xyz789" in content


class TestResolveCardMembersAutoPopulatesMap:
    """New mappings are written back to YAML via schema_dir."""

    def test_auto_populate(self, tmp_path):
        vault = tmp_path / "vault"
        persons = vault / "entities" / "persons"
        schema = tmp_path / "schema"
        persons.mkdir(parents=True)
        schema.mkdir()

        card = {
            "members": [
                {"id": "abc123", "fullName": "Victor Hugo", "username": "victorhugo"},
            ]
        }
        member_map = {}
        result = resolve_card_members(card, member_map, vault, schema_dir=schema)
        assert result == ["Victor Hugo"]
        assert member_map == {"abc123": "Victor Hugo"}

        # Check YAML file was written
        map_file = schema / "trello-member-map.yaml"
        assert map_file.exists()
        data = yaml.safe_load(map_file.read_text())
        assert data["members"]["abc123"] == "Victor Hugo"


# ---------------------------------------------------------------------------
# save_trello_member_map helper
# ---------------------------------------------------------------------------

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
    """Person with matching github_login found in vault."""

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
    """Login doesn't match github_login but name fuzzy matches."""

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
    """No match, creates draft person."""

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
    """Returns None when can't resolve (no token, no API call)."""

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
    """Mocked API returns PR list."""

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
    """No repos returns []."""

    def test_empty(self):
        result = fetch_prs_for_repos([], github_token="fake")
        assert result == []


class TestFetchPRsForReposAPIError:
    """Handles API errors gracefully."""

    def test_api_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "rate limited"
        with patch("vault.ingest.crosslink_builder.requests.get", return_value=mock_resp):
            result = fetch_prs_for_repos(["living/repo"], github_token="fake")
        assert result == []
