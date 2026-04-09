"""TDD tests for triage payload schema and append-only triage decisions artifact.

Contract for triage payload routed by TriageBridge / MattermostClient:
    {
        "id": str,
        "signal_text": str,
        "source_channel": str,
        "causal_score": float,            # 0-1
        "tier": "A" | "B" | "C",
        "fact_check_passed": bool,
        "dedup_hash": str,
        "timestamp": str,
        "pending_reason": str,
    }

Contract for triage-decisions.jsonl decision records (append-only):
    {
        "timestamp": str,
        "action": "route_to_triage" | "hold" | "promote",
        "signal_id": str,
        ...
    }
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


BRIDGE_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "memoria-consolidation"
    / "triage_bridge.py"
)
MATTERMOST_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "memoria-consolidation"
    / "mattermost_client.py"
)


def _load_module(file_path: Path, module_name: str):
    if not file_path.exists():
        raise ModuleNotFoundError(f"Missing module: {file_path}")

    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load spec from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _bridge_module():
    return _load_module(BRIDGE_FILE, "memoria_consolidation_triage_bridge_task8")


def _mattermost_module():
    return _load_module(MATTERMOST_FILE, "memoria_consolidation_mattermost_client_task8")


_REQUIRED_TRIAGE_KEYS = {
    "id",
    "signal_text",
    "source_channel",
    "causal_score",
    "tier",
    "fact_check_passed",
    "dedup_hash",
    "timestamp",
    "pending_reason",
}
_VALID_TIERS = {"A", "B", "C"}


def _sample_triage_payload(**overrides):
    base = {
        "id": "sig-2026-0420-001",
        "signal_text": "OpenClaw v2.3 adds semantic memory deduplication.",
        "source_channel": "webhook",
        "causal_score": 0.91,
        "tier": "A",
        "fact_check_passed": True,
        "dedup_hash": "a3f2b8c1d4e5f678901234567890123ab",
        "timestamp": "2026-04-09T22:00:00Z",
        "pending_reason": "Awaiting Mattermost triage review",
    }
    base.update(overrides)
    return base


def _assert_valid_triage_payload(payload: dict):
    missing = _REQUIRED_TRIAGE_KEYS - set(payload.keys())
    assert not missing, f"triage payload missing keys: {missing}"

    assert isinstance(payload["id"], str)
    assert payload["id"].strip()
    assert isinstance(payload["signal_text"], str)
    assert payload["signal_text"].strip()
    assert isinstance(payload["source_channel"], str)
    assert payload["source_channel"].strip()
    assert isinstance(payload["causal_score"], (int, float))
    assert 0.0 <= float(payload["causal_score"]) <= 1.0
    assert isinstance(payload["tier"], str)
    assert payload["tier"] in _VALID_TIERS
    assert isinstance(payload["fact_check_passed"], bool)
    assert isinstance(payload["dedup_hash"], str)
    assert payload["dedup_hash"].strip()
    assert isinstance(payload["timestamp"], str)
    assert isinstance(payload["pending_reason"], str)
    assert payload["pending_reason"].strip()


# ---------------------------------------------------------------------------
# Schema tests for payload and outbound Mattermost body
# ---------------------------------------------------------------------------

def test_triage_payload_contains_all_required_keys():
    payload = _sample_triage_payload()
    _assert_valid_triage_payload(payload)


def test_triage_payload_tier_enum_accepts_a_b_c():
    for tier in _VALID_TIERS:
        payload = _sample_triage_payload(tier=tier)
        _assert_valid_triage_payload(payload)


def test_triage_payload_rejects_invalid_tier_value():
    payload = _sample_triage_payload(tier="D")
    with pytest.raises(AssertionError):
        _assert_valid_triage_payload(payload)


def test_triage_payload_requires_fact_check_boolean():
    payload = _sample_triage_payload(fact_check_passed="yes")
    with pytest.raises(AssertionError):
        _assert_valid_triage_payload(payload)


def test_triage_payload_causal_score_range_0_1():
    with pytest.raises(AssertionError):
        _assert_valid_triage_payload(_sample_triage_payload(causal_score=1.2))
    with pytest.raises(AssertionError):
        _assert_valid_triage_payload(_sample_triage_payload(causal_score=-0.1))


def test_mattermost_client_builds_structured_body_with_required_keys():
    module = _mattermost_module()
    Client = module.MattermostClient
    client = Client("https://mattermost.example.com/hooks/abc123")

    payload = _sample_triage_payload()
    body = client._build_payload(payload)

    assert isinstance(body, dict)
    assert body["id"] == payload["id"]
    assert "text" in body
    assert "attachments" in body
    assert isinstance(body["attachments"], list)
    assert len(body["attachments"]) >= 1


def test_mattermost_client_escapes_html_in_text():
    module = _mattermost_module()
    Client = module.MattermostClient
    client = Client("https://mattermost.example.com/hooks/abc123")

    payload = _sample_triage_payload(signal_text="Possible <script>alert(1)</script>")
    body = client._build_payload(payload)

    assert "<script>" not in body["text"]
    assert "&lt;script&gt;" in body["text"]


# ---------------------------------------------------------------------------
# Append-only triage-decisions.jsonl behavior
# ---------------------------------------------------------------------------

def test_triage_bridge_appends_decision_record_to_jsonl(tmp_path):
    module = _bridge_module()
    Bridge = module.TriageBridge

    audit_path = tmp_path / "triage-decisions.jsonl"
    bridge = Bridge(
        webhook_url="https://mattermost.example.com/hooks/abc123",
        audit_log_path=audit_path,
    )

    payload = _sample_triage_payload(tier="A")
    with patch("urllib.request.urlopen") as mock_urlopen:
        resp = MagicMock()
        resp.read.return_value = b'{"status":"OK"}'
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        decision = bridge.route_for_triage(payload)

    assert decision["routed"] is True
    assert audit_path.exists()

    lines = audit_path.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["action"] == "route_to_triage"
    assert record["signal_id"] == payload["id"]
    assert record["destination"] == "mattermost"


def test_triage_decisions_jsonl_is_append_only(tmp_path):
    module = _bridge_module()
    Bridge = module.TriageBridge

    audit_path = tmp_path / "triage-decisions.jsonl"
    bridge = Bridge(
        webhook_url="https://mattermost.example.com/hooks/abc123",
        audit_log_path=audit_path,
    )

    with patch("urllib.request.urlopen") as mock_urlopen:
        resp = MagicMock()
        resp.read.return_value = b'{"status":"OK"}'
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        bridge.route_for_triage(_sample_triage_payload(id="sig-1", tier="A"))
        first_size = audit_path.stat().st_size
        first_lines = audit_path.read_text().splitlines()

        bridge.route_for_triage(_sample_triage_payload(id="sig-2", tier="B"))
        second_size = audit_path.stat().st_size
        second_lines = audit_path.read_text().splitlines()

    assert second_size > first_size
    assert len(first_lines) == 1
    assert len(second_lines) == 2
    assert second_lines[0] == first_lines[0]


def test_triage_bridge_skips_tier_c_and_logs_skip_reason(tmp_path):
    module = _bridge_module()
    Bridge = module.TriageBridge

    audit_path = tmp_path / "triage-decisions.jsonl"
    bridge = Bridge(
        webhook_url="https://mattermost.example.com/hooks/abc123",
        audit_log_path=audit_path,
    )

    decision = bridge.route_for_triage(_sample_triage_payload(id="sig-c", tier="C"))

    assert decision["routed"] is False
    assert decision["skipped_reason"] == "tier_c_deferred"

    lines = audit_path.read_text().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["webhook_status"] == "skipped"
    assert record["signal_id"] == "sig-c"


def test_triage_decision_records_are_valid_json_per_line(tmp_path):
    module = _bridge_module()
    Bridge = module.TriageBridge

    audit_path = tmp_path / "triage-decisions.jsonl"
    bridge = Bridge(
        webhook_url="https://mattermost.example.com/hooks/abc123",
        audit_log_path=audit_path,
    )

    # One routed, one skipped
    with patch("urllib.request.urlopen") as mock_urlopen:
        resp = MagicMock()
        resp.read.return_value = b'{"status":"OK"}'
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        bridge.route_for_triage(_sample_triage_payload(id="sig-a", tier="A"))
    bridge.route_for_triage(_sample_triage_payload(id="sig-c", tier="C"))

    lines = audit_path.read_text().splitlines()
    assert len(lines) == 2
    for i, line in enumerate(lines):
        line = line.strip()
        assert line, f"line {i} empty"
        obj = json.loads(line)
        assert isinstance(obj, dict)
        assert isinstance(obj.get("timestamp"), str)
        assert obj.get("action") == "route_to_triage"
        assert isinstance(obj.get("signal_id"), str)
