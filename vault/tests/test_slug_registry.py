"""
Tests for vault/slug_registry.py — canonical slug aliases for Memory Vault.
Phase 1C: prevents duplicate semantic pages due to naming variations.
"""
from pathlib import Path

import pytest


@pytest.fixture
def registry_module():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import vault.slug_registry as reg
    return reg


@pytest.fixture
def registry_vault(tmp_path):
    """Vault with slug divergence: entity has name X but decisions reference Y."""
    root = tmp_path / "memory" / "vault"
    for d in ("entities", "decisions", "concepts"):
        (root / d).mkdir(parents=True, exist_ok=True)

    # Entity page: "bat-conectabot.md"
    (root / "entities" / "bat-conectabot.md").write_text(
        """---
entity: BAT ConectaBot
type: entity
confidence: medium
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# BAT ConectaBot

Observability for ConectaBot.
""",
        encoding="utf-8",
    )

    # Decision references "bat-conectabot-observability" (slug divergence)
    (root / "decisions" / "d1.md").write_text(
        """---
entity: Decision
type: decision
confidence: medium
sources: []
last_verified: 2026-04-10
verification_log: []
last_touched_by: livy-agent
draft: false
---
# Decision

Mentions [[bat-conectabot-observability]] which does not exist as a page.
""",
        encoding="utf-8",
    )

    return root


# ------------------------------------------------------------------
# 1. Alias resolution
# ------------------------------------------------------------------

class TestAliasResolution:

    def test_resolve_alias_to_canonical(self, registry_module):
        canonical = registry_module.resolve("bat-conectabot-observability")
        assert canonical == "bat-conectabot"

    def test_resolve_unknown_returns_input(self, registry_module):
        result = registry_module.resolve("totally-unknown-name")
        assert result == "totally-unknown-name"

    def test_resolve_none_returns_none(self, registry_module):
        assert registry_module.resolve(None) is None


# ------------------------------------------------------------------
# 2. Coverage gap detection with aliases
# ------------------------------------------------------------------

class TestCoverageWithAliases:

    def test_gap_resolved_by_alias(self, registry_module, registry_vault):
        """A wikilink that matches an alias should NOT appear as a gap."""
        import vault.lint as lnt
        # Without registry: bat-conectabot-observability is a gap
        raw_gaps = lnt.detect_coverage_gaps(registry_vault)
        raw_names = {g["concept"] for g in raw_gaps}

        # With registry: should resolve to existing bat-conectabot entity
        aliased_gaps = registry_module.filter_aliased_gaps(raw_gaps)
        assert "bat-conectabot-observability" not in {g["concept"] for g in aliased_gaps}


# ------------------------------------------------------------------
# 3. Registry operations
# ------------------------------------------------------------------

class TestRegistryOperations:

    def test_register_alias(self, registry_module):
        registry_module.register("alias-x", "canonical-y")
        assert registry_module.resolve("alias-x") == "canonical-y"

    def test_resolve_is_case_insensitive(self, registry_module):
        registry_module.register("My-Alias", "my-canonical")
        assert registry_module.resolve("MY-ALIAS") == "my-canonical"

    def test_registry_persists_aliases(self, registry_module, tmp_path):
        root = tmp_path / "memory" / "vault"
        (root / "schema").mkdir(parents=True, exist_ok=True)
        registry_module.save_registry(root / "schema" / "slug-registry.json")

        loaded = registry_module.load_registry(root / "schema" / "slug-registry.json")
        assert "alias-x" in loaded
