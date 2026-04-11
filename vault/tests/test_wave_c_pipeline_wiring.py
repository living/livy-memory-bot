"""Tests for Wave C pipeline wiring into vault/pipeline.py.

Covers:
1) run_wave_c_ingest writes meeting/card entities idempotently
2) run_pipeline exposes wave_c_ingest summary
3) WAVE_C_C1_ENABLED=false bypasses Wave C ingest stage
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def wiring_workspace(tmp_path, monkeypatch):
    root = tmp_path
    vault_root = root / "memory" / "vault"
    for d in ("entities", "decisions", "concepts", "evidence", "lint-reports", "relationships"):
        (vault_root / d).mkdir(parents=True, exist_ok=True)

    # minimal events file for run_pipeline
    events = root / "memory" / "signal-events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    sample_events = [
        {
            "event_id": "evt-1",
            "signal_type": "decision",
            "origin_id": "o1",
            "origin_url": "https://example.com/o1",
            "collected_at": "2026-04-10T03:00:00+00:00",
            "payload": {
                "description": "Decision for wiring test",
                "evidence": "https://example.com/e1",
                "confidence": 0.9,
            },
        }
    ]
    with events.open("w", encoding="utf-8") as f:
        for e in sample_events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # patch globals used by lint/status/ingest side effects
    monkeypatch.setattr("vault.ingest.VAULT_ROOT", vault_root)
    monkeypatch.setattr("vault.lint.VAULT_ROOT", vault_root)
    monkeypatch.setattr("vault.status.VAULT_ROOT", vault_root)

    return {"root": root, "vault_root": vault_root, "events": events}


class TestWaveCIngestWriter:

    def test_run_wave_c_ingest_writes_meeting_and_card(self, wiring_workspace, monkeypatch):
        from vault.ingest import wave_c_pipeline as wcp

        fake_meeting = {
            "id_canonical": "meeting:daily-2026-04-10",
            "meeting_id_source": "daily-2026-04-10",
            "title": "Daily",
            "source_keys": ["tldv:daily-2026-04-10"],
            "lineage": {"mapper_version": "wave-c-meeting-ingest-v1"},
        }
        fake_card = {
            "id_canonical": "card:board123:card456",
            "card_id_source": "card456",
            "title": "Implement Wave C",
            "board": "board123",
            "source_keys": ["trello:board123:card456"],
            "lineage": {"mapper_version": "wave-c-card-ingest-v1"},
        }

        monkeypatch.setattr(wcp, "fetch_meetings", lambda days=7: ([fake_meeting], []))
        monkeypatch.setattr(wcp, "fetch_cards", lambda days=7: ([fake_card], []))

        summary = wcp.run_wave_c_ingest(vault_root=wiring_workspace["vault_root"], dry_run=False)

        assert summary["meetings_fetched"] == 1
        assert summary["meetings_written"] == 1
        assert summary["cards_fetched"] == 1
        assert summary["cards_written"] == 1

        entities = list((wiring_workspace["vault_root"] / "entities").glob("*.md"))
        names = {p.name for p in entities}
        assert any(name.startswith("meeting-") for name in names)
        assert any(name.startswith("card-") for name in names)

    def test_run_wave_c_ingest_is_idempotent(self, wiring_workspace, monkeypatch):
        from vault.ingest import wave_c_pipeline as wcp

        fake_meeting = {
            "id_canonical": "meeting:daily-2026-04-10",
            "meeting_id_source": "daily-2026-04-10",
            "title": "Daily",
            "source_keys": ["tldv:daily-2026-04-10"],
            "lineage": {"mapper_version": "wave-c-meeting-ingest-v1"},
        }
        fake_card = {
            "id_canonical": "card:board123:card456",
            "card_id_source": "card456",
            "title": "Implement Wave C",
            "board": "board123",
            "source_keys": ["trello:board123:card456"],
            "lineage": {"mapper_version": "wave-c-card-ingest-v1"},
        }

        monkeypatch.setattr(wcp, "fetch_meetings", lambda days=7: ([fake_meeting], []))
        monkeypatch.setattr(wcp, "fetch_cards", lambda days=7: ([fake_card], []))

        s1 = wcp.run_wave_c_ingest(vault_root=wiring_workspace["vault_root"], dry_run=False)
        s2 = wcp.run_wave_c_ingest(vault_root=wiring_workspace["vault_root"], dry_run=False)

        assert s1["meetings_written"] == 1
        assert s1["cards_written"] == 1
        assert s2["meetings_written"] == 0
        assert s2["cards_written"] == 0
        assert s2["meetings_skipped"] >= 1
        assert s2["cards_skipped"] >= 1


class TestWaveCPipelineIntegration:

    def test_run_pipeline_exposes_wave_c_ingest_summary(self, wiring_workspace, monkeypatch):
        import vault.pipeline as pipeline_module

        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", wiring_workspace["vault_root"])

        # Avoid real external calls; emulate empty fetches
        monkeypatch.setattr(
            "vault.ingest.wave_c_pipeline.fetch_meetings",
            lambda days=7: ([], []),
        )
        monkeypatch.setattr(
            "vault.ingest.wave_c_pipeline.fetch_cards",
            lambda days=7: ([], []),
        )

        summary = pipeline_module.run_pipeline(
            events_path=wiring_workspace["events"],
            dry_run=True,
        )

        assert "wave_c_ingest" in summary
        assert "meetings_fetched" in summary["wave_c_ingest"]
        assert "cards_fetched" in summary["wave_c_ingest"]

    def test_wave_c_stage_can_be_disabled_via_env(self, wiring_workspace, monkeypatch):
        # Re-import module so env flag is re-evaluated at import-time.
        monkeypatch.setenv("WAVE_C_C1_ENABLED", "false")

        import vault.pipeline as p
        p = importlib.reload(p)

        monkeypatch.setattr(p, "VAULT_ROOT", wiring_workspace["vault_root"])

        summary = p.run_pipeline(
            events_path=wiring_workspace["events"],
            dry_run=True,
        )

        assert summary["wave_c_ingest"]["wave_c_enabled"] is False
        assert summary["wave_c_ingest"]["meetings_fetched"] == 0
        assert summary["wave_c_ingest"]["cards_fetched"] == 0

    def test_meeting_entity_has_source_keys_and_sources(self, wiring_workspace, monkeypatch):
        """Meeting entities must have source_keys (non-empty list) and sources array."""
        from vault.ingest import wave_c_pipeline as wcp

        fake_meeting = {
            "id_canonical": "meeting:daily-2026-04-10",
            "meeting_id_source": "daily-2026-04-10",
            "title": "Daily",
            "source_keys": ["tldv:daily-2026-04-10"],
            "lineage": {"mapper_version": "wave-c-meeting-ingest-v1"},
        }
        monkeypatch.setattr(wcp, "fetch_meetings", lambda days=7: ([fake_meeting], []))
        monkeypatch.setattr(wcp, "fetch_cards", lambda days=7: ([], []))

        wcp.run_wave_c_ingest(vault_root=wiring_workspace["vault_root"], dry_run=False)

        entities = list((wiring_workspace["vault_root"] / "entities").glob("meeting-*.md"))
        assert len(entities) == 1

        import yaml
        text = entities[0].read_text(encoding="utf-8")
        fm = yaml.safe_load(text.split("---", 2)[1])

        assert "source_keys" in fm, "meeting must have source_keys"
        assert isinstance(fm["source_keys"], list), "source_keys must be a list"
        assert len(fm["source_keys"]) > 0, "source_keys must be non-empty"
        assert "sources" in fm, "meeting must have sources"
        assert isinstance(fm["sources"], list), "sources must be a list"
        assert len(fm["sources"]) > 0, "sources must be non-empty"
        assert fm["sources"][0].get("source_type") == "tldv_api"

    def test_meeting_entity_references_person_via_sources(self, wiring_workspace, monkeypatch):
        """When person entities exist for participants, meeting sources should reference them."""
        from vault.ingest import wave_c_pipeline as wcp

        # A meeting with participants that already have person entities written
        fake_meeting = {
            "id_canonical": "meeting:daily-2026-04-10",
            "meeting_id_source": "daily-2026-04-10",
            "title": "Daily",
            "participants": [
                {"id_canonical": "person:lincoln", "display_name": "Lincoln"},
                {"id_canonical": "person:robert", "display_name": "Robert"},
            ],
            "source_keys": ["tldv:daily-2026-04-10"],
            "lineage": {"mapper_version": "wave-c-meeting-ingest-v1"},
        }
        monkeypatch.setattr(wcp, "fetch_meetings", lambda days=7: ([fake_meeting], []))
        monkeypatch.setattr(wcp, "fetch_cards", lambda days=7: ([], []))

        wcp.run_wave_c_ingest(vault_root=wiring_workspace["vault_root"], dry_run=False)

        entities = list((wiring_workspace["vault_root"] / "entities").glob("meeting-*.md"))
        import yaml
        text = entities[0].read_text(encoding="utf-8")
        fm = yaml.safe_load(text.split("---", 2)[1])

        # Sources should reference both the TLDV meeting and person participants
        source_types = {s.get("source_type") for s in fm.get("sources", [])}
        assert "tldv_api" in source_types
