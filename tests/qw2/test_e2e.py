"""QW-2 E2E dry-run tests with fixtures."""
import json, pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TLDV_FIXTURE = FIXTURE_DIR / "tldv_meeting_with_decisions.json"


@pytest.fixture
def tldv_fixture():
    return json.loads(TLDV_FIXTURE.read_text())


@patch("vault.qw2.fetch_tldv.TLDVClient")
def test_e2e_tldv_dry_run(mock_client_cls, tldv_fixture, tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw2.cursor.QW2_CURSOR_DIR", tmp_path / ".research/qw2")
    monkeypatch.setattr("vault.qw2.writer.QW2_BASE", tmp_path / ".research/qw2")
    monkeypatch.setattr("vault.qw2.writer.DECISIONS_DIR", tmp_path / "decisions")
    mock_client = MagicMock()
    # fetch_events_since returns list of meetings with meeting_id
    mock_client.fetch_events_since.return_value = [
        {
            "id": "meeting_test_1",
            "meeting_id": "meeting_test_1",
            "name": "Daily BAT — decisões técnicas",
            "created_at": "2026-05-24T10:00:00Z",
            "updated_at": "2026-05-24T10:00:00Z",
        }
    ]
    # fetch_summaries returns summaries with decisions
    mock_client.fetch_summaries.return_value = tldv_fixture["full_meeting"]["summaries"]
    mock_client_cls.return_value = mock_client

    from vault.qw2.run import run
    result = run(source="tldv", dry_run=True, since_days=7)

    assert result["processed"] >= 1
    assert result["written"] == 0  # dry-run
    assert result["errors"] == 0
