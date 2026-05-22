"""Tests for vault_lint_scanner — especially wiki-link regex handling."""
from __future__ import annotations

import re
import tempfile
import pytest
from pathlib import Path


class TestWikiLinkRegex:
    """Regression tests for wiki-link parsing in _read_index_paths."""

    def _make_vault(self, tmpdir: Path, index_content: str, entity_files: dict[str, str]) -> Path:
        """Create a minimal vault structure.

        Args:
            tmpdir: temp directory root
            index_content: content for index.md
            entity_files: dict of relative path -> content for entity files
        Returns the vault_root path.
        """
        vault_root = tmpdir / "vault"
        vault_root.mkdir()
        (vault_root / "index.md").write_text(index_content, encoding="utf-8")
        for rel_path, content in entity_files.items():
            f = vault_root / rel_path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content, encoding="utf-8")
        return vault_root

    def test_brackets_inside_link_text_are_extracted(self):
        """Links like [[2026-03-25 [Tech] Reunião de Cadência 4D imobi]] must resolve.

        The old regex r'\\[\\[(?:[^\\]]+)\\]\\]' cannot match when ] appears
        inside the wiki-link text (it stops at that inner ] and never finds ]]).
        The new regex r'\\[\\[(.+?)\\]\\]' uses non-greedy matching and handles any
        content between [[ and the final ]].
        """
        from vault.ingest.vault_lint_scanner import _read_index_paths

        index_content = """
        ## 🗂 Meetings

        - [[2026-03-25 [Tech] Reunião de Cadência 4D imobi]]
        - [[2026-04-15 [Tech] Reunião de Cadência 4D imobi]]
        - [[2026-03-18 [Tech] Reunião de Cadência 4D imobi]]
        - [[2026-04-08 [Tech] Reunião de Cadência 4D imobi]]
        - [[2026-04-01 [Tech] Reunião de Cadência 4D imobi]]
        - [[Regular Meeting without brackets]]
        - [[Meeting with (parentheses) in name]]
        - [[2026-03-25 [External] Client Meeting]]
        """
        entity_files = {
            "entities/meetings/2026-03-25 [Tech] Reunião de Cadência 4D imobi.md": "test",
            "entities/meetings/2026-04-15 [Tech] Reunião de Cadência 4D imobi.md": "test",
            "entities/meetings/2026-03-18 [Tech] Reunião de Cadência 4D imobi.md": "test",
            "entities/meetings/2026-04-08 [Tech] Reunião de Cadência 4D imobi.md": "test",
            "entities/meetings/2026-04-01 [Tech] Reunião de Cadência 4D imobi.md": "test",
            "entities/meetings/Regular Meeting without brackets.md": "test",
            "entities/meetings/Meeting with (parentheses) in name.md": "test",
            "entities/meetings/2026-03-25 [External] Client Meeting.md": "test",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = self._make_vault(Path(tmpdir), index_content, entity_files)
            paths = _read_index_paths(vault_root)

        # All 8 links should be found and resolved
        assert len(paths) == 8, f"Expected 8 paths, got {len(paths)}: {sorted(paths)}"

        # Key check: full link text was captured (brackets inside don't truncate)
        bracket_links = [p for p in paths if 'Cadência' in p]
        assert len(bracket_links) == 5, f"Expected 5 Cadência links, got {len(bracket_links)}: {sorted(paths)}"

        external_links = [p for p in paths if 'External' in p]
        assert len(external_links) == 1, f"Expected 1 External link, got {len(external_links)}"

    def test_plain_wiki_links_still_work(self):
        """Plain links without brackets must continue to work."""
        from vault.ingest.vault_lint_scanner import _read_index_paths

        index_content = """
        ## Projects

        - [[BAT - ConectaBot]]
        - [[TLDV Pipeline]]
        - [[Forge Platform]]
        """
        entity_files = {
            "entities/projects/BAT - ConectaBot.md": "test",
            "entities/projects/TLDV Pipeline.md": "test",
            "entities/projects/Forge Platform.md": "test",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = self._make_vault(Path(tmpdir), index_content, entity_files)
            paths = _read_index_paths(vault_root)

        assert len(paths) == 3, f"Expected 3, got {len(paths)}: {sorted(paths)}"
        assert all('[' not in p and ']' not in p for p in paths)

    def test_slash_paths_added_as_wiki_paths(self):
        """Paths containing / are added as-is (wiki-link paths, not resolved to files)."""
        from vault.ingest.vault_lint_scanner import _read_index_paths

        index_content = """
        - [[https://example.com/page]]
        - [[Some Entity with/slash in name]]
        - [[Valid Entity]]
        """
        entity_files = {
            "entities/misc/Valid Entity.md": "test",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = self._make_vault(Path(tmpdir), index_content, entity_files)
            paths = _read_index_paths(vault_root)

        # 2 from slash paths (added as-is) + 1 from valid entity = 3
        assert len(paths) == 3, f"Expected 3, got {len(paths)}: {sorted(paths)}"

    def test_old_regex_fails_on_nested_brackets(self):
        r"""Demonstrate the old regex bug: [^\\\]]+ fails to match when ] appears inside.

        The old regex r'\[\[(?:[^\]]+)\]\]' uses [^\]]+ which stops at the first ]
        inside the wiki-link text. Since the content itself contains ], the pattern
        finds that inner ] and then fails to match the required ]] closing,
        resulting in NO MATCH at all (not truncation).

        The new non-greedy regex r'\[\[(.+?)\]\]' correctly matches any content
        between the outermost [[ and the final ]].
        """
        old_text = "[[2026-03-25 [Tech] Reunião de Cadência 4D imobi]]"
        old_regex = r'\[\[([^\]]+)\]\]'
        new_regex = r'\[\[(.+?)\]\]'

        old_match = re.search(old_regex, old_text)
        new_match = re.search(new_regex, old_text)

        # Old regex FAILS to match — it stops at the inner ] and then
        # finds ]e3f4]] instead of the required ]] ending
        assert old_match is None, "Old regex should FAIL to match wiki-link with inner ]"
        # New non-greedy regex matches correctly
        assert new_match is not None
        assert new_match.group(1) == "2026-03-25 [Tech] Reunião de Cadência 4D imobi"


class TestStaleThresholds:
    """Test stale detection with per-entity-type thresholds."""

    def test_meetings_stale_at_60_days_not_30(self):
        """Meeting with last_seen_at 45 days ago should NOT be stale (threshold = 60d)."""
        from vault.ingest.vault_lint_scanner import run_lint_scans
        import tempfile
        from datetime import datetime, timezone, timedelta

        # A meeting seen 45 days ago
        past = (datetime.now(timezone.utc) - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
        index_content = """
        ## 🗂 Meetings

        - [[Test Meeting]]
        """
        entity_files = {
            "entities/meetings/Test Meeting.md": f"---\ntype: meeting\nlast_seen_at: {past}\n---\n# Test Meeting",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir) / "vault"
            vault_root.mkdir()
            (vault_root / "index.md").write_text(index_content)
            for rel_path, content in entity_files.items():
                f = vault_root / rel_path
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(content)
            report = run_lint_scans(vault_root)
            stale_meetings = [s for s in report["stale"] if "Test Meeting" in s]
            # Should NOT be stale at 45 days (threshold 60d for meetings)
            assert len(stale_meetings) == 0, f"Meeting at 45d should NOT be stale, got: {stale}"

    def test_meetings_stale_at_90_days(self):
        """Meeting with last_seen_at 90 days ago SHOULD be stale (threshold = 60d)."""
        from vault.ingest.vault_lint_scanner import run_lint_scans
        import tempfile
        from datetime import datetime, timezone, timedelta

        past = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
        entity_files = {
            "entities/meetings/Old Meeting.md": f"---\ntype: meeting\nlast_seen_at: {past}\n---\n# Old Meeting",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir) / "vault"
            vault_root.mkdir()
            (vault_root / "index.md").write_text("- [[Old Meeting]]")
            for rel_path, content in entity_files.items():
                f = vault_root / rel_path
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(content)
            report = run_lint_scans(vault_root)
            stale_meetings = [s for s in report["stale"] if "Old Meeting" in s]
            assert len(stale_meetings) == 1, f"Meeting at 90d should be stale, got: {stale_meetings}"

    def test_cards_stale_at_90_days_not_60(self):
        """Card with last_seen_at 75 days ago should NOT be stale (threshold = 90d)."""
        from vault.ingest.vault_lint_scanner import run_lint_scans
        import tempfile
        from datetime import datetime, timezone, timedelta

        past = (datetime.now(timezone.utc) - timedelta(days=75)).strftime("%Y-%m-%dT%H:%M:%SZ")
        entity_files = {
            "entities/cards/card-old-test.md": f"---\ntype: card\nlast_seen_at: {past}\n---\n# Old Card",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir) / "vault"
            vault_root.mkdir()
            (vault_root / "index.md").write_text("- [[Old Card]]")
            for rel_path, content in entity_files.items():
                f = vault_root / rel_path
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(content)
            report = run_lint_scans(vault_root)
            stale_cards = [s for s in report["stale"] if "card-old-test" in s]
            assert len(stale_cards) == 0, f"Card at 75d should NOT be stale (threshold 90d), got: {stale_cards}"
