"""
TDD tests for shadow-to-triage bridge: Mattermost webhook emission + Telegram override parsing.
Implements Task 6 of the Shadow Evolution Pipeline V2.

All external HTTP calls are mocked — no real webhook calls during tests.

Pattern: modules are loaded via importlib from skills/memoria-consolidation/ directory
using synthetic module names to allow stable mocking across test runs.
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime, timezone

import pytest


# ─── Module loaders ────────────────────────────────────────────────────────────

MATTERMOST_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "memoria-consolidation"
    / "mattermost_client.py"
)
BRIDGE_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "memoria-consolidation"
    / "triage_bridge.py"
)
HANDLER_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "memoria-consolidation"
    / "telegram_override_handler.py"
)


def _load_module(file_path: Path, module_name: str):
    """Load a module from a file path, caching under a synthetic name."""
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


def _mattermost_module():
    return _load_module(MATTERMOST_FILE, "memoria_consolidation_mattermost_client")


def _bridge_module():
    return _load_module(BRIDGE_FILE, "memoria_consolidation_triage_bridge")


def _handler_module():
    return _load_module(HANDLER_FILE, "memoria_consolidation_telegram_override_handler")


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def triage_payload():
    """Minimal triage payload matching triage-decisions schema."""
    return {
        "id": "sig-2026-0420-001",
        "signal_text": "OpenClaw v2.3 adds semantic memory deduplication across sessions.",
        "source_channel": "webhook",
        "causal_score": 0.91,
        "tier": "A",
        "fact_check_passed": True,
        "dedup_hash": "a3f2b8c1d4e5f678901234567890123ab",
        "timestamp": "2026-04-09T22:00:00Z",
        "pending_reason": "Awaiting Mattermost triage review",
    }


@pytest.fixture
def mattermost_webhook_url():
    return "https://mattermost.example.com/hooks/abc123xyz"


@pytest.fixture
def audit_log_path(tmp_path):
    return str(tmp_path / "triage-decisions.jsonl")


# ─── API-existence sanity checks ───────────────────────────────────────────────

def test_mattermost_client_module_exists():
    module = _mattermost_module()
    assert module is not None


def test_mattermost_client_exports_mattermost_client_class():
    module = _mattermost_module()
    assert hasattr(module, "MattermostClient")


def test_bridge_module_exists():
    module = _bridge_module()
    assert module is not None


def test_bridge_exports_triage_bridge_class():
    module = _bridge_module()
    assert hasattr(module, "TriageBridge")


def test_handler_module_exists():
    module = _handler_module()
    assert module is not None


def test_handler_exports_telegram_override_handler_class():
    module = _handler_module()
    assert hasattr(module, "TelegramOverrideHandler")


# ─── Mattermost Client Tests ───────────────────────────────────────────────────

class TestMattermostClient:
    """Step 1: Failing tests for Mattermost webhook client."""

    def test_mattermost_client_posts_structured_json_to_webhook(self, triage_payload, mattermost_webhook_url):
        """MattermostClient must POST a structured JSON payload to the webhook URL."""
        module = _mattermost_module()
        ClientClass = module.MattermostClient
        client = ClientClass(webhook_url=mattermost_webhook_url)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"status": "OK"}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            result = client.send_triage_payload(triage_payload)

        assert result is True
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        req = call_args[0][0]

        assert req.method == "POST"
        # HTTP headers are case-insensitive; normalise for comparison
        header_dict = {k.lower(): v for k, v in dict(req.headers).items()}
        assert "content-type" in header_dict
        assert header_dict["content-type"] == "application/json"

        body = json.loads(req.data.decode("utf-8"))
        assert "id" in body
        assert "text" in body
        assert "attachments" in body
        assert body["id"] == triage_payload["id"]

    def test_mattermost_client_respects_timeout(self, triage_payload, mattermost_webhook_url):
        """MattermostClient must raise on timeout (504), not hang."""
        import urllib.error

        module = _mattermost_module()
        ClientClass = module.MattermostClient
        client = ClientClass(webhook_url=mattermost_webhook_url, timeout_seconds=3)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url=mattermost_webhook_url,
                code=504,
                msg="Gateway Timeout",
                hdrs={},
                fp=None,
            )

            with pytest.raises(urllib.error.HTTPError) as exc_info:
                client.send_triage_payload(triage_payload)

            assert exc_info.value.code == 504

    def test_mattermost_client_returns_false_on_connection_error(self, triage_payload, mattermost_webhook_url):
        """MattermostClient must return False on connection errors, not raise."""
        import urllib.error

        module = _mattermost_module()
        ClientClass = module.MattermostClient
        client = ClientClass(webhook_url=mattermost_webhook_url)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            result = client.send_triage_payload(triage_payload)

        assert result is False

    def test_mattermost_client_escapes_html_in_signal_text(self, triage_payload, mattermost_webhook_url):
        """Signal text with < > must be HTML-escaped to prevent Mattermost formatting issues."""
        module = _mattermost_module()
        ClientClass = module.MattermostClient
        triage_payload["signal_text"] = "Test <script>alert('xss')</script> and `code`"
        client = ClientClass(webhook_url=mattermost_webhook_url)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"status": "OK"}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            client.send_triage_payload(triage_payload)

            req = mock_urlopen.call_args[0][0]
            body = json.loads(req.data.decode("utf-8"))

            # HTML chars must be escaped
            assert "<script>" not in body["text"]
            # Should contain escaped form (either &lt; or &#60;)
            escaped = body["text"]
            assert ("&lt;" in escaped or "&#60;" in escaped)


# ─── Triage Bridge Tests ──────────────────────────────────────────────────────

class TestTriageBridge:
    """Step 1-2: Failing tests for triage bridge orchestration."""

    def test_triage_bridge_posts_to_mattermost_for_tier_a_signals(self, triage_payload, mattermost_webhook_url):
        """Bridge must POST to Mattermost for every Tier A signal needing triage."""
        module = _bridge_module()
        BridgeClass = module.TriageBridge
        bridge = BridgeClass(webhook_url=mattermost_webhook_url)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"status": "OK"}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            decision = bridge.route_for_triage(triage_payload)

        assert decision["routed"] is True
        assert decision["destination"] == "mattermost"
        assert decision["signal_id"] == triage_payload["id"]

    def test_triage_bridge_skips_tier_c_signals(self, triage_payload):
        """Bridge must NOT route Tier C signals to Mattermost — deferred/low priority."""
        module = _bridge_module()
        BridgeClass = module.TriageBridge
        triage_payload["tier"] = "C"
        bridge = BridgeClass(webhook_url="https://mattermost.example.com/hooks/fake")

        with patch.object(bridge, "_post_to_mattermost") as mock_post:
            decision = bridge.route_for_triage(triage_payload)

        mock_post.assert_not_called()
        assert decision["routed"] is False
        assert decision["skipped_reason"] == "tier_c_deferred"

    def test_triage_bridge_logs_decision_to_jsonl(self, triage_payload, audit_log_path):
        """Bridge must append triage routing decision to triage-decisions.jsonl."""
        module = _bridge_module()
        BridgeClass = module.TriageBridge
        bridge = BridgeClass(
            webhook_url="https://mattermost.example.com/hooks/fake",
            audit_log_path=audit_log_path,
        )

        with patch("urllib.request.urlopen"):
            bridge.route_for_triage(triage_payload)

        with open(audit_log_path, "r") as f:
            lines = f.readlines()

        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["signal_id"] == triage_payload["id"]
        assert record["action"] == "route_to_triage"
        assert "timestamp" in record

    def test_triage_bridge_returns_failure_on_webhook_error(self, triage_payload, audit_log_path):
        """Bridge must return failure status and log error when Mattermost is unreachable."""
        module = _bridge_module()
        BridgeClass = module.TriageBridge
        bridge = BridgeClass(
            webhook_url="https://mattermost.example.com/hooks/fake",
            audit_log_path=audit_log_path,
        )

        import urllib.error
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
            decision = bridge.route_for_triage(triage_payload)

        assert decision["routed"] is False
        assert decision["webhook_status"] == "failed"

        with open(audit_log_path, "r") as f:
            record = json.loads(f.readlines()[-1])
        assert record["webhook_status"] == "failed"

    def test_triage_bridge_re_raises_http_504(self, triage_payload, audit_log_path):
        """Bridge must preserve timeout semantics by re-raising HTTP 504 errors."""
        import urllib.error

        module = _bridge_module()
        BridgeClass = module.TriageBridge
        bridge = BridgeClass(
            webhook_url="https://mattermost.example.com/hooks/fake",
            audit_log_path=audit_log_path,
        )

        with patch.object(bridge, "_post_to_mattermost") as mock_post:
            mock_post.side_effect = urllib.error.HTTPError(
                url="https://mattermost.example.com/hooks/fake",
                code=504,
                msg="Gateway Timeout",
                hdrs={},
                fp=None,
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                bridge.route_for_triage(triage_payload)

        assert exc_info.value.code == 504

    def test_triage_bridge_bubbles_unexpected_exceptions(self, triage_payload, audit_log_path):
        """Bridge must not swallow unexpected exceptions from routing internals."""
        module = _bridge_module()
        BridgeClass = module.TriageBridge
        bridge = BridgeClass(
            webhook_url="https://mattermost.example.com/hooks/fake",
            audit_log_path=audit_log_path,
        )

        with patch.object(bridge, "_post_to_mattermost", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError, match="boom"):
                bridge.route_for_triage(triage_payload)


# ─── Telegram Override Handler Tests ─────────────────────────────────────────

class TestTelegramOverrideHandler:
    """Step 2: Failing tests for Telegram override parsing (hold/promote + reason)."""

    def test_parse_callback_data_hold_with_reason(self):
        """Handler must parse callback_data 'hold:<signal_id>:<reason>' correctly."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        handler = HandlerClass(audit_log_path=":memory:")

        callback_data = "hold:sig-2026-0420-001:Low causal confidence, needs more evidence"
        result = handler.parse_override(callback_data)

        assert result["action"] == "hold"
        assert result["signal_id"] == "sig-2026-0420-001"
        assert result["reason"] == "Low causal confidence, needs more evidence"
        assert result["override_type"] == "callback_data"

    def test_parse_callback_data_promote_with_reason(self):
        """Handler must parse callback_data 'promote:<signal_id>:<reason>' correctly."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        handler = HandlerClass(audit_log_path=":memory:")

        callback_data = "promote:sig-2026-0420-001:Confirmed via manual research"
        result = handler.parse_override(callback_data)

        assert result["action"] == "promote"
        assert result["signal_id"] == "sig-2026-0420-001"
        assert result["reason"] == "Confirmed via manual research"
        assert result["override_type"] == "callback_data"

    def test_parse_message_text_hold(self):
        """Handler must parse message text '/override hold sig-2026-0420-001 reason'."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        handler = HandlerClass(audit_log_path=":memory:")

        message_text = "/override hold sig-2026-0420-001 Low causal confidence, needs more evidence"
        result = handler.parse_override(message_text, override_type="message_text")

        assert result["action"] == "hold"
        assert result["signal_id"] == "sig-2026-0420-001"
        assert result["reason"] == "Low causal confidence, needs more evidence"
        assert result["override_type"] == "message_text"

    def test_parse_message_text_promote(self):
        """Handler must parse message text '/override promote <id> <reason>'."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        handler = HandlerClass(audit_log_path=":memory:")

        message_text = "/override promote sig-2026-0420-001 Confirmed via manual research"
        result = handler.parse_override(message_text, override_type="message_text")

        assert result["action"] == "promote"
        assert result["signal_id"] == "sig-2026-0420-001"
        assert result["reason"] == "Confirmed via manual research"

    def test_parse_raises_on_unknown_action(self):
        """Handler must raise ValueError for unknown action types."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        handler = HandlerClass(audit_log_path=":memory:")

        with pytest.raises(ValueError, match="Unknown override action"):
            handler.parse_override("skip:sig-2026-0420-001:some reason")

    def test_parse_raises_on_missing_signal_id(self):
        """Handler must raise ValueError when signal_id is absent."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        handler = HandlerClass(audit_log_path=":memory:")

        with pytest.raises(ValueError, match="signal_id"):
            handler.parse_override("hold::no_signal_id")

    def test_parse_rejects_signal_id_with_whitespace(self):
        """signal_id must be a stable token and reject whitespace."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        handler = HandlerClass(audit_log_path=":memory:")

        with pytest.raises(ValueError, match="signal_id"):
            handler.parse_override("hold:sig 2026 001:reason")

    def test_parse_rejects_signal_id_with_unsafe_chars(self):
        """signal_id should reject punctuation outside conservative pattern."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        handler = HandlerClass(audit_log_path=":memory:")

        with pytest.raises(ValueError, match="signal_id"):
            handler.parse_override("hold:sig/2026?001:reason")

    def test_parse_accepts_conservative_signal_id_pattern(self):
        """signal_id should allow alnum with internal - _ . separators."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        handler = HandlerClass(audit_log_path=":memory:")

        result = handler.parse_override("hold:sig-2026_04.20-001:reason")
        assert result["signal_id"] == "sig-2026_04.20-001"

    def test_apply_hold_writes_audit_log(self, tmp_path):
        """Applying hold override must append to triage-decisions.jsonl append-only."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        audit_path = str(tmp_path / "triage-decisions.jsonl")
        handler = HandlerClass(audit_log_path=audit_path)

        override = {
            "action": "hold",
            "signal_id": "sig-2026-0420-001",
            "reason": "Low causal confidence",
            "override_type": "callback_data",
        }

        result = handler.apply_override(override)
        assert result["logged"] is True

        with open(audit_path, "r") as f:
            lines = f.readlines()

        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["action"] == "hold"
        assert record["signal_id"] == "sig-2026-0420-001"
        assert record["reason"] == "Low causal confidence"
        assert "timestamp" in record

    def test_apply_promote_writes_audit_log(self, tmp_path):
        """Applying promote override must append to triage-decisions.jsonl append-only."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        audit_path = str(tmp_path / "triage-decisions.jsonl")
        handler = HandlerClass(audit_log_path=audit_path)

        override = {
            "action": "promote",
            "signal_id": "sig-2026-0420-001",
            "reason": "Confirmed via manual research",
            "override_type": "message_text",
        }

        result = handler.apply_override(override)
        assert result["logged"] is True

        with open(audit_path, "r") as f:
            lines = f.readlines()

        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["action"] == "promote"
        assert record["signal_id"] == "sig-2026-0420-001"
        assert record["reason"] == "Confirmed via manual research"

    def test_audit_log_is_append_only(self, tmp_path):
        """Audit log must be append-only — existing entries never overwritten."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        audit_path = str(tmp_path / "triage-decisions.jsonl")
        handler = HandlerClass(audit_log_path=audit_path)

        override1 = {
            "action": "hold",
            "signal_id": "sig-001",
            "reason": "reason1",
            "override_type": "callback_data",
        }
        override2 = {
            "action": "promote",
            "signal_id": "sig-002",
            "reason": "reason2",
            "override_type": "callback_data",
        }

        handler.apply_override(override1)
        handler.apply_override(override2)

        with open(audit_path, "r") as f:
            lines = f.readlines()

        assert len(lines) == 2
        assert json.loads(lines[0])["signal_id"] == "sig-001"
        assert json.loads(lines[1])["signal_id"] == "sig-002"

    def test_handler_rejects_empty_reason(self):
        """Override without reason must raise ValueError to prevent unlogged skips."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        handler = HandlerClass(audit_log_path=":memory:")

        with pytest.raises(ValueError, match="reason"):
            handler.parse_override("hold:sig-2026-0420-001:")

    def test_handler_requires_reason_for_hold(self):
        """Hold action requires a non-empty reason — enforced at parse time."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        handler = HandlerClass(audit_log_path=":memory:")

        with pytest.raises(ValueError, match="reason"):
            handler.parse_override("hold:sig-2026-0420-001:")

    def test_handler_requires_reason_for_promote(self):
        """Promote action requires a non-empty reason — enforced at parse time."""
        module = _handler_module()
        HandlerClass = module.TelegramOverrideHandler
        handler = HandlerClass(audit_log_path=":memory:")

        with pytest.raises(ValueError, match="reason"):
            handler.parse_override("promote:sig-2026-0420-001:")
