"""
Tests for vault/fact_check.py — confidence scoring and cache.
Phase 1B TDD: these tests define the expected API before implementation.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def fact_check_module():
    """Import the fact_check module lazily so the file can be created after this test."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import vault.fact_check as fc
    return fc


# ------------------------------------------------------------------
# 1. Confidence scoring rules
# ------------------------------------------------------------------

class TestConfidenceScoring:
    """AGENTS.md defines: high ≥ 2 official | 1+1 corroborada | 1 oficial
       medium: 1 oficial | 2+ indirectos
       low: 1 indirecto
       unverified: sin evidencia
    """

    def test_two_official_is_high(self, fact_check_module):
        assert fact_check_module.score_confidence(official=2, corroborated=0, indirect=0) == "high"

    def test_one_official_one_corroborated_is_high(self, fact_check_module):
        assert fact_check_module.score_confidence(official=1, corroborated=1, indirect=0) == "high"

    def test_one_official_alone_is_medium(self, fact_check_module):
        assert fact_check_module.score_confidence(official=1, corroborated=0, indirect=0) == "medium"

    def test_three_indirect_is_medium(self, fact_check_module):
        assert fact_check_module.score_confidence(official=0, corroborated=0, indirect=3) == "medium"

    def test_two_indirect_is_medium(self, fact_check_module):
        assert fact_check_module.score_confidence(official=0, corroborated=0, indirect=2) == "medium"

    def test_one_indirect_is_low(self, fact_check_module):
        assert fact_check_module.score_confidence(official=0, corroborated=0, indirect=1) == "low"

    def test_no_evidence_is_unverified(self, fact_check_module):
        assert fact_check_module.score_confidence(official=0, corroborated=0, indirect=0) == "unverified"

    def test_unverified_not_written_to_vault(self, fact_check_module):
        """AGENTS.md rule: unverified → log only, never write to vault."""
        conf = fact_check_module.score_confidence(0, 0, 0)
        assert conf == "unverified"


# ------------------------------------------------------------------
# 2. Cache TTL 24h
# ------------------------------------------------------------------

class TestCacheTTL:
    """Cache entries expire after 24 hours (TTL = 86400 seconds)."""

    def test_cache_ttl_constant(self, fact_check_module):
        assert fact_check_module.CACHE_TTL_SECONDS == 86400

    def test_fresh_entry_not_stale(self, fact_check_module):
        now = datetime.now(timezone.utc)
        age_hours = 12
        checked_at = now - timedelta(hours=age_hours)
        assert not fact_check_module._is_stale(checked_at, now)

    def test_entry_at_23h_not_stale(self, fact_check_module):
        now = datetime.now(timezone.utc)
        checked_at = now - timedelta(hours=23)
        assert not fact_check_module._is_stale(checked_at, now)

    def test_entry_at_24h_is_stale(self, fact_check_module):
        now = datetime.now(timezone.utc)
        checked_at = now - timedelta(hours=24) - timedelta(seconds=1)
        assert fact_check_module._is_stale(checked_at, now)

    def test_entry_at_48h_is_stale(self, fact_check_module):
        now = datetime.now(timezone.utc)
        checked_at = now - timedelta(hours=48) - timedelta(seconds=1)
        assert fact_check_module._is_stale(checked_at, now)


class TestCacheReadWrite:
    """Cache lives at memory/vault/.cache/fact-check/, entries are JSON."""

    def test_get_returns_none_for_missing_key(self, fact_check_module):
        result = fact_check_module.cached_lookup("nonexistent_claim")
        assert result is None

    def test_set_and_get_roundtrip(self, fact_check_module):
        claim_key = "my_test_claim"
        data = {"confidence": "medium", "checked_at": datetime.now(timezone.utc).isoformat()}
        fact_check_module.cache_set(claim_key, data)
        loaded = fact_check_module.cache_get(claim_key)
        assert loaded is not None
        assert loaded["confidence"] == "medium"

    def test_stale_entry_returns_none(self, fact_check_module):
        """When cached entry is older than 24h, cache_get returns None."""
        claim_key = "stale_claim"
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        entry = {
            "confidence": "high",
            "checked_at": old_time.isoformat(),
        }
        fact_check_module.cache_set(claim_key, entry)
        result = fact_check_module.cache_get(claim_key)
        assert result is None

    def test_cache_dir_within_vault_boundary(self, fact_check_module):
        """Cache dir must be inside memory/vault/ — never outside."""
        root = Path(__file__).resolve().parents[2]
        cache_dir = fact_check_module.CACHE_DIR
        assert str(cache_dir).startswith(str(root / "memory" / "vault"))

    def test_cache_filename_is_safe(self, fact_check_module):
        """Path traversal attempts should be neutralised."""
        key = "claim/with/slashes"
        safe = fact_check_module._safe_key(key)
        assert "/" not in safe
        assert "\\" not in safe
        assert safe.endswith(".json")

    def test_empty_key_not_in_cache(self, fact_check_module):
        result = fact_check_module.cache_get("")
        assert result is None


# ------------------------------------------------------------------
# 3. Source classification helpers
# ------------------------------------------------------------------

class TestSourceClassification:
    """Classify evidence sources as official / corroborated / indirect."""

    def test_openclaw_exec_is_official(self, fact_check_module):
        assert fact_check_module.classify_source({"type": "exec"}) == "official"

    def test_openclaw_config_get_is_official(self, fact_check_module):
        assert fact_check_module.classify_source({"type": "openclaw_config"}) == "official"

    def test_api_direct_call_is_official(self, fact_check_module):
        assert fact_check_module.classify_source({"type": "api_direct"}) == "official"

    def test_tldv_api_is_official(self, fact_check_module):
        assert fact_check_module.classify_source({"type": "tldv_api"}) == "official"

    def test_github_api_is_official(self, fact_check_module):
        assert fact_check_module.classify_source({"type": "github_api"}) == "official"

    def test_supabase_rest_is_official(self, fact_check_module):
        assert fact_check_module.classify_source({"type": "supabase_rest"}) == "official"

    def test_signal_event_is_indirect(self, fact_check_module):
        assert fact_check_module.classify_source({"type": "signal_event"}) == "indirect"

    def test_observation_is_indirect(self, fact_check_module):
        assert fact_check_module.classify_source({"type": "observation"}) == "indirect"

    def test_chat_history_is_indirect(self, fact_check_module):
        assert fact_check_module.classify_source({"type": "chat_history"}) == "indirect"

    def test_curated_topic_is_corroborated(self, fact_check_module):
        assert fact_check_module.classify_source({"type": "curated_topic"}) == "corroborated"

    def test_unknown_type_is_indirect(self, fact_check_module):
        assert fact_check_module.classify_source({"type": "unknown_type"}) == "indirect"


# ------------------------------------------------------------------
# 4. Integration: score from list of sources
# ------------------------------------------------------------------

class TestScoreFromSources:
    """score_from_sources() aggregates a list of source dicts into a confidence."""

    def test_empty_sources_yields_unverified(self, fact_check_module):
        assert fact_check_module.score_from_sources([]) == "unverified"

    def test_single_official_yields_medium(self, fact_check_module):
        sources = [{"type": "exec"}]
        assert fact_check_module.score_from_sources(sources) == "medium"

    def test_two_officials_yields_high(self, fact_check_module):
        sources = [{"type": "exec"}, {"type": "tldv_api"}]
        assert fact_check_module.score_from_sources(sources) == "high"

    def test_official_plus_corroborated_yields_high(self, fact_check_module):
        sources = [{"type": "exec"}, {"type": "curated_topic"}]
        assert fact_check_module.score_from_sources(sources) == "high"

    def test_two_indirects_yields_medium(self, fact_check_module):
        sources = [{"type": "signal_event"}, {"type": "observation"}]
        assert fact_check_module.score_from_sources(sources) == "medium"

    def test_single_indirect_yields_low(self, fact_check_module):
        sources = [{"type": "observation"}]
        assert fact_check_module.score_from_sources(sources) == "low"
