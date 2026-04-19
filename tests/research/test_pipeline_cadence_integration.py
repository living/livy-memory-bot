"""Integration tests for cadence wiring in ResearchPipeline.run()."""

from datetime import datetime, timezone
from pathlib import Path

from vault.research.cadence_manager import (
    DEFAULT_INTERVAL_HOURS,
    ESCALATED_INTERVAL_HOURS,
    get_interval_hours,
)
from vault.research.pipeline import ResearchPipeline
from vault.research.state_store import save_state


def _state_file(tmp_path: Path) -> Path:
    p = tmp_path / "state.json"
    save_state(
        {
            "processed_event_keys": {"github": [], "tldv": [], "trello": []},
            "last_seen_at": {"github": None, "tldv": None, "trello": None},
            "version": 1,
        },
        p,
    )
    return p


def test_pipeline_escalates_to_6h_after_three_budget_like_runs(tmp_path, monkeypatch):
    cadence_path = tmp_path / "cadence.json"
    state_path = _state_file(tmp_path)
    research_dir = tmp_path / ".research" / "github"
    research_dir.mkdir(parents=True)

    class _Client:
        def fetch_events_since(self, _):
            # Trigger budget-like condition in pipeline: len(events) >= 100
            return [
                {
                    "source": "github",
                    "type": "pr_merged",
                    "id": f"repo#{i}",
                    "event_type": "github:pr_merged",
                    "pr_number": i,
                    "event_at": datetime(2026, 4, 19, 1, 0, 0, tzinfo=timezone.utc).isoformat(),
                }
                for i in range(100)
            ]

        def fetch_pr(self, _):
            return {"author": {"login": "dev"}}

    monkeypatch.setattr("vault.research.pipeline.GitHubClient", lambda: _Client())

    for _ in range(3):
        p = ResearchPipeline(
            source="github",
            state_path=state_path,
            research_dir=research_dir,
            # Allow research_dir so _is_path_allowed passes for GitHub hypothesis paths
            allowed_paths=[str(research_dir)],
        )
        p.cadence_state_path = cadence_path
        p.run()

    assert get_interval_hours(cadence_path) == ESCALATED_INTERVAL_HOURS


def test_pipeline_reduces_back_to_4h_after_three_healthy_runs(tmp_path, monkeypatch):
    cadence_path = tmp_path / "cadence.json"
    state_path = _state_file(tmp_path)
    research_dir = tmp_path / ".research" / "github"
    research_dir.mkdir(parents=True)

    class _BudgetClient:
        def fetch_events_since(self, _):
            return [
                {
                    "source": "github",
                    "type": "pr_merged",
                    "id": f"repo#{i}",
                    "event_type": "github:pr_merged",
                    "pr_number": i,
                    "event_at": datetime(2026, 4, 19, 1, 0, 0, tzinfo=timezone.utc).isoformat(),
                }
                for i in range(100)
            ]

        def fetch_pr(self, _):
            return {"author": {"login": "dev"}}

    class _HealthyClient:
        def fetch_events_since(self, _):
            return [
                {
                    "source": "github",
                    "type": "pr_merged",
                    "id": "repo#1",
                    "event_type": "github:pr_merged",
                    "pr_number": 1,
                    "event_at": datetime(2026, 4, 19, 1, 0, 0, tzinfo=timezone.utc).isoformat(),
                }
            ]

        def fetch_pr(self, _):
            return {"author": {"login": "dev"}}

    # First escalate
    monkeypatch.setattr("vault.research.pipeline.GitHubClient", lambda: _BudgetClient())
    for _ in range(3):
        p = ResearchPipeline(
            source="github",
            state_path=state_path,
            research_dir=research_dir,
            allowed_paths=[str(research_dir)],
        )
        p.cadence_state_path = cadence_path
        p.run()

    assert get_interval_hours(cadence_path) == ESCALATED_INTERVAL_HOURS

    # Then recover
    monkeypatch.setattr("vault.research.pipeline.GitHubClient", lambda: _HealthyClient())
    for _ in range(3):
        p = ResearchPipeline(
            source="github",
            state_path=state_path,
            research_dir=research_dir,
            allowed_paths=[str(research_dir)],
        )
        p.cadence_state_path = cadence_path
        p.run()

    assert get_interval_hours(cadence_path) == DEFAULT_INTERVAL_HOURS
