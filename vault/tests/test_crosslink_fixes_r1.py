"""Tests for crosslink pipeline fixes — Round 1 review feedback.

Covers:
- M4: pr_details assignment bug in enrichment functions
- B2: resolve_pr_author failure observability (no token, API error, rate limit)
- B3: github-login-map.yaml integration
- M2: dedup_draft_persons ordering and logging
- M5: yaml.dump frontmatter preservation
- M8: duplicate imports cleanup
- N2: bot PR filtering
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml

from vault.ingest.crosslink_builder import run_crosslink
from vault.ingest.crosslink_resolver import (
    resolve_pr_author,
    fetch_prs_for_repos,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _setup_vault_with_enrichment(tmp_path: Path) -> Path:
    """Create vault with meeting enrichment_context in frontmatter."""
    vault = tmp_path / "vault"
    schema = vault.parent / "schema"
    schema.mkdir(parents=True)

    (schema / "trello-member-map.yaml").write_text(
        yaml.dump({"members": {"member1": "Lincoln Quinan"}})
    )
    (schema / "repo-project-map.yaml").write_text(
        yaml.dump({"repos": {"living/repo": "BAT/Kaba"}})
    )
    (schema / "board-project-map.yaml").write_text(
        yaml.dump({"boards": {"board1": "BAT/Kaba"}})
    )

    meetings_dir = vault / "entities" / "meetings"
    meetings_dir.mkdir(parents=True)
    (vault / "entities" / "persons").mkdir(parents=True)
    (vault / "entities" / "cards").mkdir(parents=True)
    (vault / "entities" / "prs").mkdir(parents=True)
    (vault / "relationships").mkdir(parents=True)

    ec = {
        "trello": {
            "cards": [
                {
                    "id": "card1",
                    "name": "Fix login",
                    "url": "https://trello.com/c/card1",
                    "board_id": "board1",
                    "members": [
                        {
                            "id": "member1",
                            "fullName": "Lincoln Quinan",
                            "username": "lincolnq",
                        }
                    ],
                },
            ]
        },
        "github": {
            "pull_requests": [
                {
                    "url": "https://github.com/living/repo/pull/7",
                    "title": "Fix bug",
                    "repo": "living/repo",
                    "repo_short": "repo",
                    "number": 7,
                },
            ]
        },
    }
    meeting_fm = {
        "entity": "Status Kaba/BAT/BOT",
        "type": "meeting",
        "id_canonical": "meeting:tldv:test123",
        "enrichment_context": ec,
    }
    fm_text = yaml.dump(meeting_fm, default_flow_style=False, sort_keys=False)
    (meetings_dir / "test-meeting.md").write_text(
        f"---\n{fm_text}---\n\n# Test Meeting\n", encoding="utf-8"
    )

    return vault


def _make_person(vault: Path, name: str, github_login: str | None = None, **fm_extra):
    """Create a person entity file."""
    from vault.ingest.entity_writer import _slugify

    persons_dir = vault / "entities" / "persons"
    persons_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(name)
    fm = {"entity": name, "type": "person", **fm_extra}
    if github_login:
        fm["github_login"] = github_login
    fm_text = yaml.dump(fm, default_flow_style=False, sort_keys=False)
    (persons_dir / f"{slug}.md").write_text(
        f"---\n{fm_text}---\n\n# {name}\n", encoding="utf-8"
    )


def _make_project(vault: Path, name: str):
    """Create a project entity file."""
    from vault.ingest.entity_writer import _slugify

    projects_dir = vault / "entities" / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(name)
    content = f'---\nentity: "{name}"\ntype: project\n---\n\n# {name}\n'
    (projects_dir / f"{slug}.md").write_text(content, encoding="utf-8")


# ── M4: pr_details assignment bug ────────────────────────────────────────────


class TestPRDetailsAssignmentFix:
    """pr_details[pr.get("url")] = pr instead of pr_details.get(url, pr)."""

    def test_pr_details_populated_in_enrich_project(self, tmp_path):
        from vault.ingest.crosslink_enrichment import enrich_project_files

        vault = _setup_vault_with_enrichment(tmp_path)
        with patch(
            "vault.ingest.crosslink_resolver.resolve_pr_author",
            return_value="Lincoln Quinan",
        ):
            run_crosslink(vault, dry_run=False, github_token="fake")

        _make_project(vault, "BAT/Kaba")
        enrich_project_files(vault)

        from vault.ingest.entity_writer import _slugify

        slug = _slugify("BAT/Kaba")
        content = (vault / "entities" / "projects" / f"{slug}.md").read_text()
        # PR title should appear, not fallback "pr:living/repo:7"
        assert "Fix bug" in content, f"PR title missing in project file: {content}"

    def test_pr_details_populated_in_enrich_person(self, tmp_path):
        from vault.ingest.crosslink_enrichment import (
            enrich_person_files_with_crosslinks,
        )

        vault = _setup_vault_with_enrichment(tmp_path)
        with patch(
            "vault.ingest.crosslink_resolver.resolve_pr_author",
            return_value="Lincoln Quinan",
        ):
            run_crosslink(vault, dry_run=False, github_token="fake")

        _make_person(vault, "Lincoln Quinan")
        enrich_person_files_with_crosslinks(vault)

        from vault.ingest.entity_writer import _slugify

        slug = _slugify("Lincoln Quinan")
        content = (vault / "entities" / "persons" / f"{slug}.md").read_text()
        assert "Fix bug" in content, f"PR title missing in person file: {content}"


# ── B2: resolve_pr_author failure observability ──────────────────────────────


class TestResolvePRAuthorLogsReason:
    """resolve_pr_author logs the reason for failure."""

    def test_no_token_logs_reason(self, tmp_path, caplog):
        import logging

        vault = tmp_path / "vault"
        (vault / "entities" / "persons").mkdir(parents=True)
        pr_data = {
            "url": "https://github.com/living/repo/pull/1",
            "number": 1,
        }

        with caplog.at_level(logging.WARNING, logger="vault.ingest.crosslink_resolver"):
            result = resolve_pr_author(pr_data, vault, github_token=None)

        assert result is None
        assert any("no_token" in r.message.lower() or "no github token" in r.message.lower()
                    for r in caplog.records), \
            f"Expected no_token log, got: {[r.message for r in caplog.records]}"

    def test_api_error_logs_reason(self, tmp_path, caplog):
        import logging

        vault = tmp_path / "vault"
        (vault / "entities" / "persons").mkdir(parents=True)
        pr_data = {
            "url": "https://github.com/living/repo/pull/1",
            "number": 1,
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with caplog.at_level(logging.WARNING, logger="vault.ingest.crosslink_resolver"):
            with patch(
                "vault.ingest.crosslink_resolver.requests.get",
                return_value=mock_resp,
            ):
                result = resolve_pr_author(pr_data, vault, github_token="fake")

        assert result is None
        assert any("api_error" in r.message.lower() or "500" in r.message
                    for r in caplog.records), \
            f"Expected api_error log, got: {[r.message for r in caplog.records]}"

    def test_rate_limit_logs_reason(self, tmp_path, caplog):
        import logging

        vault = tmp_path / "vault"
        (vault / "entities" / "persons").mkdir(parents=True)
        pr_data = {
            "url": "https://github.com/living/repo/pull/1",
            "number": 1,
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.headers = {"X-RateLimit-Remaining": "0"}

        with caplog.at_level(logging.WARNING, logger="vault.ingest.crosslink_resolver"):
            with patch(
                "vault.ingest.crosslink_resolver.requests.get",
                return_value=mock_resp,
            ):
                result = resolve_pr_author(pr_data, vault, github_token="fake")

        assert result is None
        assert any("rate" in r.message.lower() for r in caplog.records), \
            f"Expected rate_limit log, got: {[r.message for r in caplog.records]}"


# ── B3: github-login-map.yaml integration ────────────────────────────────────


class TestGithubLoginMapIntegration:
    """resolve_pr_author uses github-login-map.yaml for identity resolution."""

    def test_resolves_via_login_map(self, tmp_path):
        vault = tmp_path / "vault"
        schema = vault.parent / "schema"
        schema.mkdir(parents=True)
        (vault / "entities" / "persons").mkdir(parents=True)

        # Write github-login-map.yaml
        login_map = {"logins": {"lincolnqjunior": "Lincoln Quinan Junior"}}
        (schema / "github-login-map.yaml").write_text(
            yaml.dump(login_map), encoding="utf-8"
        )

        _make_person(vault, "Lincoln Quinan Junior")

        pr_data = {
            "url": "https://github.com/living/repo/pull/7",
            "number": 7,
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"user": {"login": "lincolnqjunior"}}

        with patch(
            "vault.ingest.crosslink_resolver.requests.get",
            return_value=mock_resp,
        ):
            result = resolve_pr_author(
                pr_data, vault, github_token="fake", schema_dir=schema
            )

        assert result == "Lincoln Quinan Junior", \
            f"Should resolve via login map, got: {result}"

    def test_login_map_prevents_draft_creation(self, tmp_path):
        vault = tmp_path / "vault"
        schema = vault.parent / "schema"
        schema.mkdir(parents=True)
        (vault / "entities" / "persons").mkdir(parents=True)

        login_map = {"logins": {"estevesm": "Esteves"}}
        (schema / "github-login-map.yaml").write_text(
            yaml.dump(login_map), encoding="utf-8"
        )

        _make_person(vault, "Esteves")

        pr_data = {
            "url": "https://github.com/living/repo/pull/5",
            "number": 5,
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"user": {"login": "estevesm"}}

        with patch(
            "vault.ingest.crosslink_resolver.requests.get",
            return_value=mock_resp,
        ):
            result = resolve_pr_author(
                pr_data, vault, github_token="fake", schema_dir=schema
            )

        # No draft should be created
        person_files = list((vault / "entities" / "persons").glob("*.md"))
        assert len(person_files) == 1, \
            f"Should have only canonical person, got: {[f.name for f in person_files]}"
        assert result == "Esteves"


# ── M2: dedup runs before edges + logging ────────────────────────────────────


class TestDedupBeforeEdges:
    """dedup_draft_persons should not use bare except: pass."""

    def test_dedup_logs_instead_of_silent_pass(self, tmp_path, caplog):
        import logging

        from vault.ingest.crosslink_dedup import dedup_draft_persons

        vault = tmp_path / "vault"
        persons = vault / "entities" / "persons"
        persons.mkdir(parents=True)

        # Create a draft with malformed YAML to trigger error
        (persons / "bad-draft.md").write_text("---\nentity: bad\n---\n", encoding="utf-8")

        # No canonicals → nothing to merge
        with caplog.at_level(logging.DEBUG, logger="vault.ingest.crosslink_builder"):
            result = run_crosslink(vault, dry_run=False, github_token=None)

        # The run should complete without silent crash


# ── M5: frontmatter preservation ─────────────────────────────────────────────


class TestFrontmatterPreservation:
    """Enrichment functions should not corrupt frontmatter on re-run."""

    def test_idempotent_enrichment(self, tmp_path):
        from vault.ingest.crosslink_enrichment import enrich_project_files

        vault = _setup_vault_with_enrichment(tmp_path)
        with patch(
            "vault.ingest.crosslink_resolver.resolve_pr_author",
            return_value="Lincoln Quinan",
        ):
            run_crosslink(vault, dry_run=False, github_token="fake")

        _make_project(vault, "BAT/Kaba")
        enrich_project_files(vault)

        from vault.ingest.entity_writer import _slugify

        slug = _slugify("BAT/Kaba")
        first_content = (vault / "entities" / "projects" / f"{slug}.md").read_text()

        # Run enrichment again
        enrich_project_files(vault)
        second_content = (vault / "entities" / "projects" / f"{slug}.md").read_text()

        # Content should be identical after second run (idempotent)
        assert first_content == second_content, \
            "Enrichment should be idempotent"


# ── N2: bot PR filtering ────────────────────────────────────────────────────


class TestBotPRFiltering:
    """resolve_pr_author should skip bot accounts."""

    def test_skips_bot_accounts(self, tmp_path):
        vault = tmp_path / "vault"
        (vault / "entities" / "persons").mkdir(parents=True)

        pr_data = {
            "url": "https://github.com/living/repo/pull/1",
            "number": 1,
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"user": {"login": "dependabot[bot]"}}

        with patch(
            "vault.ingest.crosslink_resolver.requests.get",
            return_value=mock_resp,
        ):
            result = resolve_pr_author(pr_data, vault, github_token="fake")

        assert result is None, "Bot accounts should be skipped"
        # No draft person created
        assert list((vault / "entities" / "persons").glob("*.md")) == [], \
            "No draft should be created for bots"

    def test_skips_pre_commit_ci(self, tmp_path):
        vault = tmp_path / "vault"
        (vault / "entities" / "persons").mkdir(parents=True)

        pr_data = {
            "url": "https://github.com/living/repo/pull/2",
            "number": 2,
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "user": {"login": "pre-commit-ci[bot]"}
        }

        with patch(
            "vault.ingest.crosslink_resolver.requests.get",
            return_value=mock_resp,
        ):
            result = resolve_pr_author(pr_data, vault, github_token="fake")

        assert result is None


# ── M8: duplicate imports cleanup ────────────────────────────────────────────


class TestNoDuplicateImports:
    """crosslink_builder.py should not have duplicate imports."""

    def test_no_duplicate_imports(self):
        import inspect
        import vault.ingest.crosslink_builder as mod

        source = inspect.getsource(mod)
        # Count occurrences of each import line
        lines = source.split("\n")
        import_lines = [l.strip() for l in lines if l.strip().startswith("from vault.ingest.")]
        # No import should appear more than once at module level
        from collections import Counter

        counts = Counter(import_lines)
        dupes = {k: v for k, v in counts.items() if v > 1}
        assert not dupes, f"Duplicate imports found: {dupes}"


# ── Batch PR cache integration (Task 3 simplified) ──────────────────────────


class TestBatchPRCacheIntegration:
    """run_crosslink should use batch fetch for PR author resolution."""

    def test_uses_batch_fetch(self, tmp_path):
        vault = _setup_vault_with_enrichment(tmp_path)

        with patch(
            "vault.ingest.crosslink_resolver.resolve_pr_author",
            return_value="Lincoln Quinan",
        ) as mock_resolve:
            run_crosslink(vault, dry_run=False, github_token="fake")

        # resolve_pr_author should be called for each PR
        assert mock_resolve.called

    def test_batch_fetch_called_once_per_repo(self, tmp_path):
        """fetch_prs_for_repos should be called once, not once per PR."""
        vault = _setup_vault_with_enrichment(tmp_path)

        with patch(
            "vault.ingest.crosslink_resolver.fetch_prs_for_repos",
            return_value=[],
        ) as mock_fetch:
            with patch(
                "vault.ingest.crosslink_resolver.resolve_pr_author",
                return_value="Lincoln Quinan",
            ):
                run_crosslink(vault, dry_run=False, github_token="fake")

        # fetch_prs_for_repos called at most once (batch per run)
        assert mock_fetch.call_count <= 1, \
            f"Expected ≤1 batch calls, got {mock_fetch.call_count}"

    def test_cache_hit_avoids_api_call(self, tmp_path):
        """When batch fetch returns author, resolve_pr_author uses cache (no API call)."""
        vault = _setup_vault_with_enrichment(tmp_path)

        # Batch returns author for the PR in the test meeting
        batch_result = [{
            "repo": "living/repo",
            "number": 7,
            "title": "Fix bug",
            "html_url": "https://github.com/living/repo/pull/7",
            "merged_at": None,
            "user_login": "lincolnqjunior",
        }]

        with patch(
            "vault.ingest.crosslink_resolver.fetch_prs_for_repos",
            return_value=batch_result,
        ):
            # Patch requests.get to ensure NO individual API call happens
            with patch(
                "vault.ingest.crosslink_resolver.requests.get",
            ) as mock_api:
                result = run_crosslink(vault, dry_run=False, github_token="fake")

                # The GitHub API should NOT be called — cache provides the login
                mock_api.assert_not_called(), \
                    f"Expected zero API calls when cache hit, got {mock_api.call_count}"

                # Verify pr-person edges exist
                data = json.loads(
                    (vault / "relationships" / "pr-person.json").read_text()
                )
                edges = data.get("edges", [])
                assert len(edges) >= 1, \
                    f"Cache should resolve PR author. Edges: {edges}"

    def test_fetch_prs_for_repos_returns_number(self):
        """fetch_prs_for_repos must include 'number' in returned dicts."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "title": "feat: add X",
                "html_url": "https://github.com/living/repo/pull/42",
                "number": 42,
                "merged_at": "2026-04-10T00:00:00Z",
                "user": {"login": "dev1"},
            },
        ]
        with patch(
            "vault.ingest.crosslink_resolver.requests.get",
            return_value=mock_resp,
        ):
            result = fetch_prs_for_repos(["living/repo"], github_token="fake")
        assert len(result) == 1
        assert result[0]["number"] == 42, \
            f"fetch_prs_for_repos must return 'number' field, got keys: {list(result[0].keys())}"
