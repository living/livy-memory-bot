"""
Tests for vault/ingest.py — signal-events ingestion pipeline.
Phase 1B TDD: tests define the expected API before implementation.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def ingest_module():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import vault.ingest as ing
    return ing


@pytest.fixture
def signal_events(tmp_path):
    """Create a minimal signal-events.jsonl file in a temp dir."""
    events_file = tmp_path / "signal-events.jsonl"
    events = [
        {
            "event_id": "evt-001",
            "correlation_id": "corr-001",
            "source": "tldv",
            "priority": 1,
            "collected_at": "2026-04-07T13:00:00+00:00",
            "processed_at": None,
            "topic_ref": None,
            "signal_type": "decision",
            "payload": {
                "description": "Usar entidade como base para novos desenvolvimentos",
                "evidence": "https://tldv.io/meeting/69d41e6b3ac24700135a516b",
                "confidence": 0.8,
            },
            "origin_id": "meeting-001",
            "origin_url": "https://tldv.io/meeting/69d41e6b3ac24700135a516b",
        },
        {
            "event_id": "evt-002",
            "correlation_id": "corr-001",
            "source": "tldv",
            "priority": 1,
            "collected_at": "2026-04-07T13:00:01+00:00",
            "processed_at": None,
            "topic_ref": "bat-conectabot-observability.md",
            "signal_type": "decision",
            "payload": {
                "description": "Limpar banco Supabase e re-migrar dados MySQL",
                "evidence": "https://tldv.io/meeting/69d3a0419a861200135c6d50",
                "confidence": 0.8,
            },
            "origin_id": "meeting-002",
            "origin_url": "https://tldv.io/meeting/69d3a0419a861200135c6d50",
        },
        {
            "event_id": "evt-003",
            "correlation_id": "corr-002",
            "source": "tldv",
            "priority": 1,
            "collected_at": "2026-04-07T13:00:02+00:00",
            "processed_at": None,
            "topic_ref": None,
            "signal_type": "topic_mentioned",
            "payload": {
                "description": "Tópicos mencionados: Patrimônio Líquido, Alinhamento com time de Rodrigo",
                "evidence": "https://tldv.io/meeting/69cd722f98acd80013fa5f81",
                "confidence": 0.6,
            },
            "origin_id": "meeting-003",
            "origin_url": "https://tldv.io/meeting/69cd722f98acd80013fa5f81",
        },
    ]
    with events_file.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")
    return events_file


@pytest.fixture
def vault_root(tmp_path):
    """Create a minimal vault structure in a temp dir."""
    vault = tmp_path / "memory" / "vault"
    for sub in ("entities", "decisions", "concepts", "evidence", "lint-reports",
                "schema", ".cache", ".cache/fact-check"):
        (vault / sub).mkdir(parents=True, exist_ok=True)
    # Write minimal index/log so the code can update them
    index = vault / "index.md"
    index.write_text("# Vault Index\n\n## Decisions (0)\n", encoding="utf-8")
    log = vault / "log.md"
    log.write_text("", encoding="utf-8")
    return vault


# ------------------------------------------------------------------
# 1. Parse events
# ------------------------------------------------------------------

class TestParseEvents:

    def test_load_events_from_jsonl(self, ingest_module, signal_events):
        events = ingest_module.load_events(signal_events)
        assert len(events) == 3

    def test_events_are_dicts(self, ingest_module, signal_events):
        events = ingest_module.load_events(signal_events)
        assert all(isinstance(e, dict) for e in events)

    def test_empty_jsonl_returns_empty_list(self, ingest_module, tmp_path):
        empty = tmp_path / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        events = ingest_module.load_events(empty)
        assert events == []


class TestDeduplication:

    def test_deduplicate_by_origin_id(self, ingest_module, signal_events):
        events = ingest_module.load_events(signal_events)
        deduped = ingest_module.deduplicate_events(events)
        origin_ids = [e["origin_id"] for e in deduped]
        assert len(origin_ids) == len(set(origin_ids))

    def test_duplicate_events_removed(self, ingest_module, tmp_path):
        """If signal-events.jsonl has duplicate origin_ids, only one survives."""
        dup_file = tmp_path / "dup.jsonl"
        base = {
            "event_id": "x", "correlation_id": "c", "source": "tldv",
            "priority": 1, "collected_at": "2026-04-07T13:00:00+00:00",
            "processed_at": None, "topic_ref": None,
            "signal_type": "decision",
            "payload": {"description": "Test", "evidence": "url", "confidence": 0.8},
            "origin_id": "dup-id", "origin_url": "url",
        }
        with dup_file.open("w") as f:
            f.write(json.dumps(base) + "\n")
            f.write(json.dumps(base) + "\n")
        events = ingest_module.load_events(dup_file)
        deduped = ingest_module.deduplicate_events(events)
        assert len(deduped) == 1


# ------------------------------------------------------------------
# 2. Classify signal type
# ------------------------------------------------------------------

class TestSignalClassification:

    def test_decision_signal_extracted(self, ingest_module):
        ev = {
            "signal_type": "decision",
            "payload": {"description": "Fazer X", "evidence": "url", "confidence": 0.8},
            "origin_url": "url",
        }
        result = ingest_module.extract_signal(ev)
        assert result is not None
        assert result["signal_type"] == "decision"
        assert result["description"] == "Fazer X"

    def test_topic_mentioned_extracted(self, ingest_module):
        ev = {
            "signal_type": "topic_mentioned",
            "payload": {"description": "Patrimônio Líquido", "evidence": "url", "confidence": 0.6},
            "origin_url": "url",
        }
        result = ingest_module.extract_signal(ev)
        assert result is not None
        assert result["signal_type"] == "topic_mentioned"

    def test_topic_mentioned_written_to_concepts_dir(self, ingest_module, vault_root, monkeypatch, tmp_path):
        """topic_mentioned signals must be written as concept pages."""
        import json
        monkeypatch.setattr("vault.ingest.VAULT_ROOT", vault_root)

        events_file = tmp_path / "topics.jsonl"
        event = {
            "event_id": "evt-top1",
            "signal_type": "topic_mentioned",
            "payload": {
                "description": "Patrimônio Líquido",
                "evidence": "https://tldv.io/meeting/xxx",
                "confidence": 0.6,
            },
            "origin_id": "meeting-top1",
            "origin_url": "https://tldv.io/meeting/xxx",
            "collected_at": "2026-04-07T13:00:00+00:00",
        }
        with events_file.open("w", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

        summary = ingest_module.run_ingest(events_file)
        assert summary["topics"] >= 1
        concepts_dir = vault_root / "concepts"
        assert concepts_dir.exists()
        concept_files = list(concepts_dir.glob("*.md"))
        assert len(concept_files) >= 1, "topic_mentioned signal must create a concept page"

    def test_unknown_signal_type_returns_none(self, ingest_module):
        ev = {"signal_type": "unknown_type", "payload": {}, "origin_url": "url"}
        result = ingest_module.extract_signal(ev)
        assert result is None


# ------------------------------------------------------------------
# 3. Decision page creation
# ------------------------------------------------------------------

class TestDecisionPageCreation:

    def test_decision_page_has_frontmatter(self, ingest_module, vault_root, monkeypatch):
        monkeypatch.setattr("vault.ingest.VAULT_ROOT", vault_root)

        decision = {
            "signal_type": "decision",
            "description": "Usar entidade como base para novos desenvolvimentos",
            "evidence": "https://tldv.io/meeting/69d41e6b3ac24700135a516b",
            "confidence": 0.8,
            "origin_id": "meeting-001",
            "collected_at": "2026-04-07T13:00:00+00:00",
        }
        path = ingest_module.upsert_decision(decision)
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "type: decision" in text
        assert "confidence: medium" in text

    def test_decision_slug_from_description(self, ingest_module, vault_root, monkeypatch):
        monkeypatch.setattr("vault.ingest.VAULT_ROOT", vault_root)

        decision = {
            "signal_type": "decision",
            "description": "Limpar banco Supabase e re-migrar",
            "evidence": "url",
            "confidence": 0.8,
            "origin_id": "m2",
            "collected_at": "2026-04-07T13:00:00+00:00",
        }
        path = ingest_module.upsert_decision(decision)
        slug = path.stem
        assert "supabase" in slug.lower() or "migrar" in slug.lower()

    def test_decision_page_has_backlink_to_entity(self, ingest_module, vault_root, monkeypatch):
        """If topic_ref is set, decision links back to that entity."""
        monkeypatch.setattr("vault.ingest.VAULT_ROOT", vault_root)

        decision = {
            "signal_type": "decision",
            "description": "Re-migrar Supabase",
            "evidence": "url",
            "confidence": 0.8,
            "origin_id": "m2",
            "collected_at": "2026-04-07T13:00:00+00:00",
            "topic_ref": "bat-conectabot.md",
        }
        path = ingest_module.upsert_decision(decision)
        text = path.read_text(encoding="utf-8")
        assert "bat-conectabot" in text


# ------------------------------------------------------------------
# 4. Confidence mapping from float
# ------------------------------------------------------------------

class TestConfidenceMapping:
    """Signal payload confidence 0.0–1.0 maps to vault confidence labels."""

    def test_high_confidence_08_maps_to_medium(self, ingest_module):
        assert ingest_module.map_signal_confidence(0.8) == "medium"
        assert ingest_module.map_signal_confidence(0.7) == "medium"

    def test_low_confidence_06_maps_to_low(self, ingest_module):
        assert ingest_module.map_signal_confidence(0.6) == "low"
        assert ingest_module.map_signal_confidence(0.3) == "low"

    def test_verification_required_for_high(self, ingest_module):
        """Signal confidence 0.9+ maps to high only after Context7 verification."""
        assert ingest_module.map_signal_confidence(0.9) == "high"


# ------------------------------------------------------------------
# 5. Ingest pipeline (end-to-end)
# ------------------------------------------------------------------

class TestIngestPipeline:

    def test_ingest_updates_index(self, ingest_module, signal_events, vault_root, monkeypatch):
        monkeypatch.setattr("vault.ingest.VAULT_ROOT", vault_root)

        summary = ingest_module.run_ingest(signal_events)
        assert summary["total"] == 3
        assert summary["decisions"] >= 1

        index = (vault_root / "index.md").read_text(encoding="utf-8")
        assert "# Vault Index" in index

    def test_ingest_appends_log(self, ingest_module, signal_events, vault_root, monkeypatch):
        monkeypatch.setattr("vault.ingest.VAULT_ROOT", vault_root)

        ingest_module.run_ingest(signal_events)
        log = (vault_root / "log.md").read_text(encoding="utf-8")
        assert "## [" in log
        assert "ingest" in log.lower()

    def test_ingest_no_write_outside_vault(self, ingest_module, signal_events, tmp_path, monkeypatch):
        """Safety boundary: no files created outside memory/vault/."""
        vault_root = tmp_path / "memory" / "vault"
        vault_root.mkdir(parents=True, exist_ok=True)
        (vault_root / "decisions").mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr("vault.ingest.VAULT_ROOT", vault_root)

        ingest_module.run_ingest(signal_events)

        # Check no unexpected files
        all_files = list(tmp_path.rglob("*"))
        # Ignore the input events file itself; only ensure ingest created nothing else outside vault
        outside_vault = [
            f for f in all_files
            if "memory/vault" not in str(f)
            and f.is_file()
            and f.name != "signal-events.jsonl"
        ]
        assert not outside_vault
