"""Tests for vault.ingest.run_report — structured run metrics."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path



def test_report_contains_all_required_fields():
    """emit_run_report produces dict with run_id, run_at, and all summary fields."""
    from vault.ingest.run_report import emit_run_report

    summary = {
        "meetings_fetched": 5,
        "meetings_written": 3,
        "cards_fetched": 10,
        "cards_written": 8,
    }

    with tempfile.TemporaryDirectory() as tmp:
        reports_dir = Path(tmp)
        result = emit_run_report(summary, reports_dir=reports_dir)

    # Must contain run metadata
    assert "run_id" in result, "report must contain run_id"
    assert "run_at" in result, "report must contain run_at"
    assert isinstance(result["run_id"], str), "run_id must be a string"
    assert len(result["run_id"]) == 36, "run_id must be a valid UUID4 (36 chars)"
    assert isinstance(result["run_at"], str), "run_at must be an ISO8601 string"

    # Must contain all original summary fields
    assert result["meetings_fetched"] == 5
    assert result["meetings_written"] == 3
    assert result["cards_fetched"] == 10
    assert result["cards_written"] == 8


def test_report_logged_to_file():
    """emit_run_report writes JSON file to reports_dir."""
    from vault.ingest.run_report import emit_run_report

    summary = {
        "stage": "external_ingest",
        "errors": 0,
    }

    with tempfile.TemporaryDirectory() as tmp:
        reports_dir = Path(tmp)
        result = emit_run_report(summary, reports_dir=reports_dir)

        run_id = result["run_id"]
        run_at = result["run_at"]
        date_part = run_at[:10]  # "YYYY-MM-DD"

        # Find the written file
        files = list(reports_dir.glob("*.json"))
        assert len(files) == 1, f"expected exactly one JSON file, got {files}"

        report_file = files[0]

        # Filename pattern: {date}-{run_id[:8]}.json
        expected_basename = f"{date_part}-{run_id[:8]}.json"
        assert report_file.name == expected_basename, \
            f"expected {expected_basename}, got {report_file.name}"

        # Content matches returned dict
        with report_file.open(encoding="utf-8") as f:
            loaded = json.load(f)

        assert loaded == result, "file content must match returned dict"
        assert loaded["run_id"] == run_id
        assert loaded["run_at"] == run_at
        assert loaded["stage"] == "external_ingest"
        assert loaded["errors"] == 0


def test_report_filename_date_part_matches_run_at():
    """Filename date part is derived from run_at UTC date."""
    from vault.ingest.run_report import emit_run_report

    summary = {"count": 1}

    with tempfile.TemporaryDirectory() as tmp:
        reports_dir = Path(tmp)
        result = emit_run_report(summary, reports_dir=reports_dir)

        run_at = result["run_at"]
        date_in_file = run_at[:10]

        files = list(reports_dir.glob("*.json"))
        assert len(files) == 1
        file_date_prefix = files[0].name[:10]
        assert file_date_prefix == date_in_file, \
            f"filename prefix {file_date_prefix} must match run_at date {date_in_file}"
