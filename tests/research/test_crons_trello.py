"""Tests for vault/crons/research_trello_cron.py.

RED phase: write failing tests first.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure vault package is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class TestResearchTrelloCron:
    """Behavioral tests for the research_trello cron entry point."""

    def test_trello_cron_module_exports_main(self):
        """The cron module must expose a `main` callable."""
        from vault.crons import research_trello_cron
        assert hasattr(research_trello_cron, "main")
        assert callable(research_trello_cron.main)

    def test_trello_cron_registered_in_crons_init(self):
        """The trello cron must be registered in vault.crons.__init__."""
        from vault.crons import (
            run_research_trello,
            run_research_github,
            run_research_tldv,
            run_research_consolidation,
        )
        # All four should be importable
        assert callable(run_research_trello)
        assert callable(run_research_github)
        assert callable(run_research_tldv)
        assert callable(run_research_consolidation)

    def test_trello_cron_lock_path_constant(self):
        """LOCK_PATH must be .research/trello/lock."""
        from vault.crons.research_trello_cron import LOCK_PATH
        assert LOCK_PATH == ".research/trello/lock"

    def test_trello_cron_research_dir_constant(self):
        """RESEARCH_DIR must be .research/trello."""
        from vault.crons.research_trello_cron import RESEARCH_DIR
        assert RESEARCH_DIR == ".research/trello"

    def test_trello_cron_interval_env_var_default_20(self, monkeypatch, capsys):
        """Default interval should be 20 minutes when env var is not set."""
        monkeypatch.delenv("RESEARCH_TRELLO_INTERVAL_MIN", raising=False)
        from vault.crons import research_trello_cron

        with patch("vault.crons.research_trello_cron.ResearchPipeline") as mock_pipeline:
            mock_pipeline.return_value.run.return_value = {
                "events_processed": 0,
                "events_skipped": 0,
                "status": "success",
            }
            with patch("vault.crons.research_trello_cron.acquire_lock", return_value=True):
                with patch("vault.crons.research_trello_cron.release_lock"):
                    research_trello_cron.main()

        captured = capsys.readouterr()
        assert "interval=20min" in captured.out

    def test_trello_cron_calls_pipeline_with_source_trello(self, tmp_path, monkeypatch):
        """When run, cron must instantiate ResearchPipeline with source='trello'."""
        monkeypatch.chdir(tmp_path)

        from vault.crons import research_trello_cron

        with patch("vault.crons.research_trello_cron.acquire_lock", return_value=True):
            with patch("vault.crons.research_trello_cron.release_lock"):
                with patch("vault.crons.research_trello_cron.ResearchPipeline") as mock_pipeline_cls:
                    mock_pipeline = MagicMock()
                    mock_pipeline.run.return_value = {
                        "events_processed": 1,
                        "events_skipped": 0,
                        "status": "success",
                    }
                    mock_pipeline_cls.return_value = mock_pipeline

                    research_trello_cron.main()

                    mock_pipeline_cls.assert_called_once()
                    call_kwargs = mock_pipeline_cls.call_args.kwargs
                    assert call_kwargs["source"] == "trello"
                    assert "state_path" in call_kwargs
                    assert "research_dir" in call_kwargs

    def test_trello_cron_skips_when_lock_held(self, monkeypatch):
        """When lock cannot be acquired, main() must return early without calling pipeline."""
        from vault.crons import research_trello_cron

        with patch("vault.crons.research_trello_cron.acquire_lock", return_value=False):
            with patch("vault.crons.research_trello_cron.ResearchPipeline") as mock_pipeline_cls:
                research_trello_cron.main()
                mock_pipeline_cls.assert_not_called()

    def test_trello_cron_releases_lock_after_run(self, tmp_path, monkeypatch):
        """After successful pipeline run, lock must be released."""
        monkeypatch.chdir(tmp_path)

        from vault.crons import research_trello_cron

        with patch("vault.crons.research_trello_cron.acquire_lock", return_value=True) as mock_acquire:
            with patch("vault.crons.research_trello_cron.release_lock") as mock_release:
                with patch("vault.crons.research_trello_cron.ResearchPipeline") as mock_pipeline_cls:
                    mock_pipeline = MagicMock()
                    mock_pipeline.run.return_value = {
                        "events_processed": 0,
                        "events_skipped": 0,
                        "status": "success",
                    }
                    mock_pipeline_cls.return_value = mock_pipeline

                    research_trello_cron.main()

                    mock_release.assert_called_once_with(".research/trello/lock")

    def test_trello_cron_releases_lock_on_exception(self, tmp_path, monkeypatch):
        """If pipeline.run() raises, lock must still be released."""
        monkeypatch.chdir(tmp_path)

        from vault.crons import research_trello_cron

        with patch("vault.crons.research_trello_cron.acquire_lock", return_value=True):
            with patch("vault.crons.research_trello_cron.release_lock") as mock_release:
                with patch("vault.crons.research_trello_cron.ResearchPipeline") as mock_pipeline_cls:
                    mock_pipeline = MagicMock()
                    mock_pipeline.run.side_effect = RuntimeError("pipeline error")
                    mock_pipeline_cls.return_value = mock_pipeline

                    with pytest.raises(RuntimeError):
                        research_trello_cron.main()

                    mock_release.assert_called_once_with(".research/trello/lock")
