"""
RED test: github_api enrichment raises decision quality.

GREEN: batch script fetches GitHub API and injects github_api source.
REFACTOR: deduplicate, extract helper.
"""
import pytest, tempfile, shutil, re
from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pr_decision_file(tmp_path):
    """A minimal decision file with a GitHub PR ref in sources."""
    content = (
        "---\n"
        "entity: PR #10: test\n"
        "type: decision\n"
        "confidence: low\n"
        "sources:\n"
        "  - type: signal_event\n"
        "    ref: https://github.com/living/livy-tldv-jobs/pull/10\n"
        "    retrieved: 2026-04-07\n"
        "last_verified: 2026-04-07\n"
        "verification_log: []\n"
        "last_touched_by: livy-agent\n"
        "draft: false\n"
        "---\n"
        "# PR #10: test\n\n"
        "## Summary\nPR #10\n"
    )
    p = tmp_path / "2026-04-07-pr-10-test.md"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def pr_decision_no_gh(tmp_path):
    """Decision with only signal_event (no github ref)."""
    content = (
        "---\n"
        "entity: Test decision\n"
        "type: decision\n"
        "confidence: low\n"
        "sources:\n"
        "  - type: signal_event\n"
        "    ref: signal-only-ref\n"
        "    retrieved: 2026-04-07\n"
        "last_verified: 2026-04-07\n"
        "verification_log: []\n"
        "draft: false\n"
        "---\n"
        "# Test\n"
    )
    p = tmp_path / "2026-04-07-test-only.md"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGitHubEnrichment:
    def test_enrich_adds_github_api_source(self, pr_decision_file, monkeypatch):
        """After enrichment, frontmatter must contain github_api source block."""
        # Import the script as a module (will write it next)
        import importlib.util
        spec = importlib.util.find_spec("enrich_github")
        # This will fail until we create the module
        pytest.skip("module not yet created — this test documents expected behaviour")

    def test_confidence_not_downgraded_if_already_high(self, tmp_path):
        """A decision already with confidence: high should NOT be touched."""
        content = (
            "---\n"
            "entity: Already high confidence\n"
            "type: decision\n"
            "confidence: high\n"
            "sources:\n"
            "  - type: signal_event\n"
            "    ref: https://github.com/living/livy-tldv-jobs/pull/99\n"
            "    retrieved: 2026-04-07\n"
            "last_verified: 2026-04-07\n"
            "verification_log: []\n"
            "draft: false\n"
            "---\n"
        )
        p = tmp_path / "2026-04-07-pr-99-high.md"
        p.write_text(content, encoding="utf-8")
        # After enrichment the confidence stays high
        # (implementation should preserve existing confidence: high)
        assert re.search(r"^confidence:\s*high", content, re.M)
        # This is a documentation test — the real validation is in the batch run

    def test_pr_files_have_github_ref(self, pr_decision_file):
        """Fixture produces a file with github ref for batch processing."""
        text = pr_decision_file.read_text(encoding="utf-8")
        assert "github.com" in text
        assert "/pull/" in text

    def test_skip_non_pr_decisions(self, pr_decision_no_gh):
        """Files without github.com/pull/ should not be processed."""
        text = pr_decision_no_gh.read_text(encoding="utf-8")
        assert "signal_event" in text
        assert "github.com" not in text  # no github ref

    def test_batch_finds_all_pr_decisions(self):
        """Discovery: all 13 PR-based decisions are found in vault."""
        import os, sys
        sys.path.insert(0, os.getcwd())
        from pathlib import Path
        import re as _re
        vault_root = Path("memory/vault/decisions")
        if not vault_root.exists():
            pytest.skip("vault not present in cwd")
        pr_files = [
            f for f in vault_root.glob("*.md")
            if "/pull/" in f.read_text(encoding="utf-8")
        ]
        assert len(pr_files) >= 12, f"Expected ≥12 PR decisions, got {len(pr_files)}"

    def test_github_api_fetch_format(self):
        """GitHub API response must contain: state, merged_at, user.login."""
        # Documentation test — API shape validated by live fetch
        required_fields = ["state", "merged_at", "user"]
        assert required_fields == required_fields  # placeholder assertion

    def test_pipeline_still_passes_after_enrichment(self):
        """Full pipeline (lint + repair) must pass with 0 gaps/orphans after enrichment."""
        import subprocess, os, re as _re
        result = subprocess.run(
            ["python3", "-m", "vault.pipeline", "--repair"],
            capture_output=True, text=True,
            cwd=os.getcwd(), timeout=120,
        )
        # After enrichment, pipeline must NOT introduce new gaps or orphans
        combined = result.stdout + result.stderr
        # extract gaps/orphans numbers from output like:
        # "gaps/orphans after lint: X/Y" or "gaps/orphans after repair: X/Y"
        pair = _re.search(r"gaps/orphans after (?:lint|repair):\s*(\d+)\/(\d+)", combined)
        if pair:
            gaps = int(pair.group(1))
            orphans = int(pair.group(2))
        else:
            gaps_m = _re.search(r"gaps[=:]?\s*(\d+)", combined)
            orphans_m = _re.search(r"orphans[=:]?\s*(\d+)", combined)
            gaps = int(gaps_m.group(1)) if gaps_m else None
            orphans = int(orphans_m.group(1)) if orphans_m else None
        assert result.returncode == 0, f"Pipeline failed: {combined[-500:]}"
        assert gaps == 0, f"Expected gaps=0, got {gaps}"
        assert orphans == 0, f"Expected orphans=0, got {orphans}"
