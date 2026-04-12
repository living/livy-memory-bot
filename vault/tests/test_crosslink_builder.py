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
        "entity": "Status Kaba/BAT/BOT",
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


# ---------------------------------------------------------------------------
# Task 8: Project enrichment — Cards/PRs/Persons
# ---------------------------------------------------------------------------

def _make_project_file(vault: Path, project_name: str, extra_body: str = "") -> Path:
    from vault.ingest.entity_writer import _slugify as ew_slugify
    projects_dir = vault / "entities" / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    slug = ew_slugify(project_name)
    path = projects_dir / f"{slug}.md"
    content = (
        f"---\nentity: \"{project_name}\"\ntype: project\n---\n\n"
        f"# {project_name}\n\n{extra_body}"
    )
    path.write_text(content, encoding="utf-8")
    return path


class TestEnrichProjectAddsCards:
    def test_enrich_project_adds_cards(self, tmp_path):
        from vault.ingest.crosslink_builder import _enrich_project_files
        vault = _setup_vault_with_enrichment(tmp_path)
        # Run crosslink to create relationship files first
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            run_crosslink(vault, dry_run=False, github_token="fake")
        # Create a project file
        _make_project_file(vault, "BAT/Kaba")
        # Enrich
        _enrich_project_files(vault)
        from vault.ingest.entity_writer import _slugify as _ew_s
        slug = _ew_s("BAT/Kaba")
        content = (vault / "entities" / "projects" / f"{slug}.md").read_text()
        assert "## Cards" in content


class TestEnrichProjectAddsPRs:
    def test_enrich_project_adds_prs(self, tmp_path):
        from vault.ingest.crosslink_builder import _enrich_project_files
        vault = _setup_vault_with_enrichment(tmp_path)
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            run_crosslink(vault, dry_run=False, github_token="fake")
        _make_project_file(vault, "BAT/Kaba")
        _enrich_project_files(vault)
        from vault.ingest.entity_writer import _slugify as _ew_s
        slug = _ew_s("BAT/Kaba")
        content = (vault / "entities" / "projects" / f"{slug}.md").read_text()
        assert "## PRs" in content


class TestEnrichProjectAddsPersons:
    def test_enrich_project_adds_persons(self, tmp_path):
        from vault.ingest.crosslink_builder import _enrich_project_files
        vault = _setup_vault_with_enrichment(tmp_path)
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            run_crosslink(vault, dry_run=False, github_token="fake")
        _make_project_file(vault, "BAT/Kaba")
        _enrich_project_files(vault)
        from vault.ingest.entity_writer import _slugify as _ew_s
        slug = _ew_s("BAT/Kaba")
        content = (vault / "entities" / "projects" / f"{slug}.md").read_text()
        assert "## Pessoas" in content


# ---------------------------------------------------------------------------
# Task 9: Person enrichment — Cards/PRs
# ---------------------------------------------------------------------------

def _make_person_file(vault: Path, name: str, extra_body: str = "") -> Path:
    persons_dir = vault / "entities" / "persons"
    persons_dir.mkdir(parents=True, exist_ok=True)
    from vault.ingest.entity_writer import _slugify
    slug = _slugify(name)
    path = persons_dir / f"{slug}.md"
    content = (
        f"---\nentity: \"{name}\"\ntype: person\n---\n\n"
        f"# {name}\n\n{extra_body}"
    )
    path.write_text(content, encoding="utf-8")
    return path


class TestEnrichPersonAddsCards:
    def test_enrich_person_adds_cards(self, tmp_path):
        from vault.ingest.crosslink_builder import _enrich_person_files_with_crosslinks
        vault = _setup_vault_with_enrichment(tmp_path)
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            run_crosslink(vault, dry_run=False, github_token="fake")
        _make_person_file(vault, "Lincoln Quinan")
        _enrich_person_files_with_crosslinks(vault)
        from vault.ingest.entity_writer import _slugify
        slug = _slugify("Lincoln Quinan")
        content = (vault / "entities" / "persons" / f"{slug}.md").read_text()
        assert "## Cards" in content


class TestEnrichPersonAddsPRs:
    def test_enrich_person_adds_prs(self, tmp_path):
        from vault.ingest.crosslink_builder import _enrich_person_files_with_crosslinks
        vault = _setup_vault_with_enrichment(tmp_path)
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            run_crosslink(vault, dry_run=False, github_token="fake")
        _make_person_file(vault, "Lincoln Quinan")
        _enrich_person_files_with_crosslinks(vault)
        from vault.ingest.entity_writer import _slugify
        slug = _slugify("Lincoln Quinan")
        content = (vault / "entities" / "persons" / f"{slug}.md").read_text()
        assert "## PRs" in content


class TestEnrichPersonPreservesMeetings:
    def test_preserves_meetings(self, tmp_path):
        from vault.ingest.crosslink_builder import _enrich_person_files_with_crosslinks
        vault = _setup_vault_with_enrichment(tmp_path)
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            run_crosslink(vault, dry_run=False, github_token="fake")
        _make_person_file(vault, "Lincoln Quinan", "## Reuniões\n\n- [[test-meeting]]\n")
        _enrich_person_files_with_crosslinks(vault)
        from vault.ingest.entity_writer import _slugify
        slug = _slugify("Lincoln Quinan")
        content = (vault / "entities" / "persons" / f"{slug}.md").read_text()
        assert "## Reuniões" in content
        assert "[[test-meeting]]" in content


# ---------------------------------------------------------------------------
# Task 10: Meeting context — project-scoped links
# ---------------------------------------------------------------------------

class TestUpdateMeetingContextReplaces:
    def test_replaces_with_project_scoped(self, tmp_path):
        from vault.ingest.crosslink_builder import _update_meeting_context
        vault = _setup_vault_with_enrichment(tmp_path)
        with patch("vault.ingest.crosslink_builder.resolve_pr_author", return_value="Lincoln Quinan"):
            run_crosslink(vault, dry_run=False, github_token="fake")
        meetings_dir = vault / "entities" / "meetings"
        meeting_path = meetings_dir / "test-meeting.md"
        import yaml as _y
        old = meeting_path.read_text(encoding="utf-8")
        # Parse frontmatter to get enrichment_context with card IDs
        end = old.find("---", 3)
        fm = _y.safe_load(old[3:end]) or {}
        # Add old context section that should be replaced
        body = old[end + 3:].lstrip("\n")
        body = body.rstrip() + "\n\n## Contexto\n\n- 📋 [Old card](url)\n"
        new_fm = _y.dump(fm, default_flow_style=False, sort_keys=False)
        meeting_path.write_text(f"---\n{new_fm}---\n\n{body}", encoding="utf-8")
        # Build card-project edges from the enrichment_context cards
        ec = fm.get("enrichment_context", {})
        card_ids = [c.get("id", "") for c in ec.get("trello", {}).get("cards", [])]
        # Pick a project that the cards belong to (use board mapping from setup)
        proj_name = "bat"
        card_proj_edges = [
            {"from_id": f"card:trello:{cid}", "to_id": f"project:{proj_name}", "role": "belongs_to", "confidence": "high"}
            for cid in card_ids if cid
        ]
        pr_proj_edges: list[dict] = []
        _update_meeting_context(vault, card_proj_edges, pr_proj_edges)
        new = meeting_path.read_text(encoding="utf-8")
        assert "### Projeto:" in new
        assert "[Old card](url)" not in new


# ---------------------------------------------------------------------------
# Task 11: Pipeline integration
# ---------------------------------------------------------------------------

class TestPipelineIncludesCrosslink:
    def test_pipeline_includes_crosslink(self, tmp_path):
        """external_ingest should call run_crosslink after Stage 7."""
        import importlib
        import vault.ingest.external_ingest as mod
        source = open(mod.__file__).read()
        assert "run_crosslink" in source
        assert "Stage 8" in source


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


# ---------------------------------------------------------------------------
# Fix 1: _split_frontmatter nested YAML roundtrip
# ---------------------------------------------------------------------------

class TestSplitFrontmatterNestedYaml:
    def test_nested_dicts_survive_roundtrip(self):
        from vault.ingest.entity_writer import _split_frontmatter, _join_frontmatter

        fm = {
            "entity": "Test Meeting",
            "enrichment_context": {
                "trello": {"cards": [{"name": "Card 1", "url": "http://x"}]},
                "github": {"pull_requests": [{"title": "PR 1", "repo": "foo/bar"}]},
            },
            "source_keys": ["tldv:abc", "trello:def"],
        }
        body = "# Test Meeting\n\nSome content."
        text = _join_frontmatter(fm, body)
        parsed_fm, parsed_body = _split_frontmatter(text)
        assert parsed_fm["enrichment_context"]["trello"]["cards"] == [{"name": "Card 1", "url": "http://x"}]
        assert parsed_fm["enrichment_context"]["github"]["pull_requests"] == [{"title": "PR 1", "repo": "foo/bar"}]
        assert parsed_body.strip() == body.strip()

    def test_no_frontmatter(self):
        from vault.ingest.entity_writer import _split_frontmatter
        fm, body = _split_frontmatter("Just plain text")
        assert fm == {}
        assert body == "Just plain text"


# ---------------------------------------------------------------------------
# Fix 2: Atomic relationship writes
# ---------------------------------------------------------------------------

class TestAtomicRelationshipWrites:
    def test_no_tmp_file_left_after_run(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "entities" / "meetings").mkdir(parents=True)

        # Schema with empty maps so crosslink runs
        schema = vault / "schema"
        schema.mkdir()
        (schema / "trello-member-map.yaml").write_text("members: {}\n", encoding="utf-8")
        (schema / "repo-project-map.yaml").write_text("repos: {}\n", encoding="utf-8")
        (schema / "board-project-map.yaml").write_text("boards: {}\n", encoding="utf-8")

        result = run_crosslink(vault, dry_run=False, github_token=None)
        assert isinstance(result, dict)
        # No .tmp files should remain
        rel_dir = vault / "relationships"
        if rel_dir.exists():
            tmp_files = list(rel_dir.glob("*.tmp"))
            assert tmp_files == [], f"Leftover .tmp files: {tmp_files}"


# ---------------------------------------------------------------------------
# Fix 3: get_schema_dir fallback
# ---------------------------------------------------------------------------

class TestGetSchemaDirFallback:
    def test_primary_when_file_exists(self, tmp_path):
        from vault.ingest.mapping_loader import get_schema_dir
        primary = tmp_path / "schema"
        primary.mkdir()
        (primary / "trello-member-map.yaml").write_text("members: {}\n")
        assert get_schema_dir(tmp_path) == primary

    def test_fallback_when_primary_missing(self, tmp_path):
        from vault.ingest.mapping_loader import get_schema_dir
        parent = tmp_path / "parent"
        vault = parent / "vault"
        vault.mkdir(parents=True)
        fallback = parent / "schema"
        fallback.mkdir()
        (fallback / "trello-member-map.yaml").write_text("members: {}\n")
        assert get_schema_dir(vault) == fallback

    def test_fallback_when_primary_empty(self, tmp_path):
        from vault.ingest.mapping_loader import get_schema_dir
        parent = tmp_path / "parent"
        vault = parent / "vault"
        vault.mkdir(parents=True)
        # No schema dir at all
        assert get_schema_dir(vault) == parent / "schema"


# ---------------------------------------------------------------------------
# Person dedup — merge draft persons into canonicals
# ---------------------------------------------------------------------------

class TestPersonDedup:
    def test_draft_merged_into_canonical(self, tmp_path):
        from vault.ingest.crosslink_builder import _dedup_draft_persons
        persons = tmp_path / "entities" / "persons"
        persons.mkdir(parents=True)

        # Canonical
        canon = persons / "Esteves Marques.md"
        canon.write_text(
            "---\nentity: Esteves Marques\nsource_keys:\n  - trello/abc\n---\nBio text.\n",
            encoding="utf-8",
        )

        # Draft
        draft = persons / "estevesm.md"
        draft.write_text(
            "---\nentity: estevesm\nsource_keys:\n  - github/123\ngithub_logins:\n  - estevesm\n---\n",
            encoding="utf-8",
        )

        merged = _dedup_draft_persons(tmp_path)
        assert merged == 1
        assert not draft.exists()
        text = canon.read_text(encoding="utf-8")
        assert "github/123" in text
        assert "trello/abc" in text
        assert "estevesm" in text

    def test_no_canonical_match_keeps_draft(self, tmp_path):
        from vault.ingest.crosslink_builder import _dedup_draft_persons
        persons = tmp_path / "entities" / "persons"
        persons.mkdir(parents=True)

        draft = persons / "unknownuser.md"
        draft.write_text(
            "---\nentity: unknownuser\nsource_keys:\n  - github/999\n---\n",
            encoding="utf-8",
        )

        merged = _dedup_draft_persons(tmp_path)
        assert merged == 0
        assert draft.exists()

    def test_merge_preserves_existing_keys(self, tmp_path):
        from vault.ingest.crosslink_builder import _dedup_draft_persons
        persons = tmp_path / "entities" / "persons"
        persons.mkdir(parents=True)

        canon = persons / "Lincoln Quinan Junior.md"
        canon.write_text(
            "---\nentity: Lincoln Quinan Junior\nsource_keys:\n  - trello/t1\ntrello_ids:\n  - id123\n---\nBody.\n",
            encoding="utf-8",
        )

        draft = persons / "lincolnqjunior.md"
        draft.write_text(
            "---\nentity: lincolnqjunior\nsource_keys:\n  - github/g1\ngithub_logins:\n  - lincolnqj\ntrello_usernames:\n  - lincolnqjunior\n---\n",
            encoding="utf-8",
        )

        merged = _dedup_draft_persons(tmp_path)
        assert merged == 1
        text = canon.read_text(encoding="utf-8")
        assert "trello/t1" in text
        assert "github/g1" in text
        assert "id123" in text
        assert "lincolnqj" in text
        assert "lincolnqjunior" in text
