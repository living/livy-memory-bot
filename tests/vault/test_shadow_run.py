import json
from pathlib import Path

from vault.ops.shadow_run import run_shadow


def test_run_shadow_passes_when_diff_under_threshold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    v1 = [
        {"entity_id": "e1", "text": "same"},
        {"entity_id": "e2", "text": "same2"},
    ]
    v2 = [
        {"entity_id": "e1", "text": "same"},
        {"entity_id": "e2", "text": "same2"},
    ]

    report = run_shadow(v1, v2, threshold=0.05)

    assert report["passed"] is True
    assert report["diff_ratio"] == 0.0
    assert report["diverged_count"] == 0
    assert Path(report["report_path"]).exists()


def test_run_shadow_fails_when_diff_over_threshold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    v1 = [{"entity_id": "e1", "text": "old"}]
    v2 = [{"entity_id": "e1", "text": "new"}]

    report = run_shadow(v1, v2, threshold=0.05)

    assert report["passed"] is False
    assert report["diff_ratio"] == 1.0
    assert report["diverged_count"] == 1
    assert report["diverged_items"][0]["reason"] == "text_mismatch"


def test_run_shadow_marks_missing_entity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    v1 = [{"entity_id": "e1", "text": "a"}]
    v2 = []

    report = run_shadow(v1, v2, threshold=1.0)

    assert report["diverged_count"] == 1
    assert report["diverged_items"][0]["entity_id"] == "e1"
    assert report["diverged_items"][0]["reason"] == "missing_in_one_version"


def test_run_shadow_writes_report_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    report = run_shadow([], [], threshold=0.05)
    report_path = Path(report["report_path"])

    on_disk = json.loads(report_path.read_text(encoding="utf-8"))
    assert on_disk["total_entities"] == 0
    assert on_disk["diverged_count"] == 0
    assert on_disk["threshold"] == 0.05
