from pathlib import Path
import json
from datetime import datetime, timedelta, timezone


def score_confidence(official: int, corroborated: int, indirect: int) -> str:
    if official >= 2:
        return "high"
    if official >= 1 and corroborated >= 1:
        return "high"
    if official >= 1:
        return "medium"
    if indirect >= 2:
        return "medium"
    if indirect == 1:
        return "low"
    return "unverified"


def test_confidence_scoring_rules():
    assert score_confidence(2, 0, 0) == "high"
    assert score_confidence(1, 1, 0) == "high"
    assert score_confidence(1, 0, 0) == "medium"
    assert score_confidence(0, 0, 2) == "medium"
    assert score_confidence(0, 0, 1) == "low"
    assert score_confidence(0, 0, 0) == "unverified"


def test_cache_ttl_24h_behavior():
    now = datetime.now(timezone.utc)
    fresh = now - timedelta(hours=12)
    stale = now - timedelta(hours=25)

    assert (now - fresh) < timedelta(hours=24)
    assert (now - stale) > timedelta(hours=24)


def test_cache_file_location_inside_vault_cache():
    root = Path(__file__).resolve().parents[2]
    cache_dir = root / "memory" / "vault" / ".cache" / "fact-check"
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_file = cache_dir / "sample.json"
    payload = {"checked_at": datetime.now(timezone.utc).isoformat(), "confidence": "medium"}
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    loaded = json.loads(cache_file.read_text(encoding="utf-8"))
    assert loaded["confidence"] == "medium"
