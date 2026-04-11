"""Tests for external ingest wiring into vault/pipeline.py.

Covers:
1) run_external_ingest writes meeting/card entities idempotently
2) run_pipeline exposes external_ingest summary
3) External ingest always runs (no feature flags)
"""
from __future__ import annotations

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


class TestExternalIngestWriter:

    def test_run_external_ingest_writes_meeting_and_card(self, wiring_workspace, monkeypatch):
        from vault.ingest import external_ingest as ext

        # Raw meeting as returned by fetch_meetings_from_supabase
        fake_raw_meeting = {
            "id": "daily-2026-04-10",
            "name": "Daily",
            "participants": [
                {"id": "p1", "name": "Robert", "email": "robert@livingnet.com.br"},
            ],
        }
        fake_card_entity = {
            "id_canonical": "card:board123:card456",
            "card_id_source": "card456",
            "title": "Implement Wave C",
            "board": "board123",
            "source_keys": ["trello:board123:card456"],
            "lineage": {"mapper_version": "wave-c-card-ingest-v1"},
        }

        monkeypatch.setattr(
            "vault.ingest.external_ingest.fetch_meetings_from_supabase",
            lambda days=7: [fake_raw_meeting],
        )
        monkeypatch.setattr(
            "vault.ingest.external_ingest.fetch_cards",
            lambda days=7: ([fake_card_entity], []),
        )

        summary = ext.run_external_ingest(
            vault_root=wiring_workspace["vault_root"],
            dry_run=False,
        )

        assert summary["meetings_fetched"] == 1
        assert summary["meetings_resolved"] == 1
        assert summary["meetings_written"] == 1
        assert summary["cards_fetched"] == 1
        assert summary["cards_written"] == 1

        entities = list((wiring_workspace["vault_root"] / "entities").glob("*.md"))
        names = {p.name for p in entities}
        assert any(name.startswith("meeting-") for name in names)
        assert any(name.startswith("card-") for name in names)

    def test_run_external_ingest_is_idempotent(self, wiring_workspace, monkeypatch):
        from vault.ingest import external_ingest as ext

        fake_raw_meeting = {
            "id": "daily-2026-04-10",
            "name": "Daily",
            "participants": [
                {"id": "p1", "name": "Robert"},
            ],
        }
        fake_card_entity = {
            "id_canonical": "card:board123:card456",
            "card_id_source": "card456",
            "title": "Implement Wave C",
            "board": "board123",
            "source_keys": ["trello:board123:card456"],
            "lineage": {"mapper_version": "wave-c-card-ingest-v1"},
        }

        monkeypatch.setattr(
            "vault.ingest.external_ingest.fetch_meetings_from_supabase",
            lambda days=7: [fake_raw_meeting],
        )
        monkeypatch.setattr(
            "vault.ingest.external_ingest.fetch_cards",
            lambda days=7: ([fake_card_entity], []),
        )

        s1 = ext.run_external_ingest(
            vault_root=wiring_workspace["vault_root"],
            dry_run=False,
        )
        s2 = ext.run_external_ingest(
            vault_root=wiring_workspace["vault_root"],
            dry_run=False,
        )

        assert s1["meetings_written"] == 1
        assert s1["cards_written"] == 1
        assert s2["meetings_written"] == 0
        assert s2["cards_written"] == 0
        assert s2["meetings_skipped"] >= 1
        assert s2["cards_skipped"] >= 1


class TestExternalIngestPipelineIntegration:

    def test_run_pipeline_exposes_external_ingest_summary(self, wiring_workspace, monkeypatch):
        import vault.pipeline as pipeline_module

        monkeypatch.setattr(pipeline_module, "VAULT_ROOT", wiring_workspace["vault_root"])

        monkeypatch.setattr(
            "vault.ingest.external_ingest.fetch_meetings_from_supabase",
            lambda days=7: [],
        )
        monkeypatch.setattr(
            "vault.ingest.external_ingest.fetch_cards",
            lambda days=7: ([], []),
        )

        summary = pipeline_module.run_signal_pipeline(
            events_path=wiring_workspace["events"],
            dry_run=True,
        )

        assert "external_ingest" in summary
        assert "meetings_fetched" in summary["external_ingest"]
        assert "cards_fetched" in summary["external_ingest"]

    def test_meeting_entity_has_source_keys_and_sources(self, wiring_workspace, monkeypatch):
        """Meeting entities must have source_keys (non-empty list) and sources array."""
        from vault.ingest import external_ingest as ext

        fake_raw_meeting = {
            "id": "daily-2026-04-10",
            "name": "Daily",
            "participants": [{"id": "p1", "name": "Robert"}],
        }
        monkeypatch.setattr(
            "vault.ingest.external_ingest.fetch_meetings_from_supabase",
            lambda days=7: [fake_raw_meeting],
        )
        monkeypatch.setattr(
            "vault.ingest.external_ingest.fetch_cards",
            lambda days=7: ([], []),
        )

        ext.run_external_ingest(vault_root=wiring_workspace["vault_root"], dry_run=False)

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

    def test_meeting_entity_sources_reference_tldv_api(self, wiring_workspace, monkeypatch):
        """When meeting entity is written, meeting sources should reference the TLDV API."""
        from vault.ingest import external_ingest as ext

        fake_raw_meeting = {
            "id": "daily-2026-04-10",
            "name": "Daily",
            "participants": [{"id": "p1", "name": "Robert"}],
        }
        monkeypatch.setattr(
            "vault.ingest.external_ingest.fetch_meetings_from_supabase",
            lambda days=7: [fake_raw_meeting],
        )
        monkeypatch.setattr(
            "vault.ingest.external_ingest.fetch_cards",
            lambda days=7: ([], []),
        )

        ext.run_external_ingest(vault_root=wiring_workspace["vault_root"], dry_run=False)

        entities = list((wiring_workspace["vault_root"] / "entities").glob("meeting-*.md"))
        import yaml
        text = entities[0].read_text(encoding="utf-8")
        fm = yaml.safe_load(text.split("---", 2)[1])

        source_types = {s.get("source_type") for s in fm.get("sources", [])}
        assert "tldv_api" in source_types

    def test_skipped_meetings_appear_in_skips_list(self, wiring_workspace, monkeypatch):
        """Meetings with no participants are skipped and recorded in skips list."""
        from vault.ingest import external_ingest as ext

        fake_raw_meeting = {
            "id": "no-participants-meeting",
            "name": "Empty Meeting",
            "participants": [],
        }
        monkeypatch.setattr(
            "vault.ingest.external_ingest.fetch_meetings_from_supabase",
            lambda days=7: [fake_raw_meeting],
        )
        monkeypatch.setattr(
            "vault.ingest.external_ingest.fetch_cards",
            lambda days=7: ([], []),
        )

        summary = ext.run_external_ingest(
            vault_root=wiring_workspace["vault_root"],
            dry_run=False,
        )

        assert summary["meetings_fetched"] == 1
        assert summary["meetings_resolved"] == 0
        assert summary["meetings_skipped"] == 1
        assert len(summary["skips"]) == 1
        assert summary["skips"][0]["reason"] == "NO_PARTICIPANTS"
