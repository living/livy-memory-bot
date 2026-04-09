"""TDD tests for Context7 + official-docs fact-check gate (Task 5)."""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


FACT_CHECKER_FILE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "memoria-consolidation"
    / "fact_checker.py"
)


def _load_fact_checker_module():
    """Load the fact_checker module under a stable import name for patching."""
    if not FACT_CHECKER_FILE.exists():
        raise ModuleNotFoundError(f"Missing production fact_checker module: {FACT_CHECKER_FILE}")

    existing = sys.modules.get("memoria_consolidation_fact_checker")
    if existing is not None:
        return existing

    spec = importlib.util.spec_from_file_location(
        "memoria_consolidation_fact_checker", FACT_CHECKER_FILE
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load fact_checker module spec from {FACT_CHECKER_FILE}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["memoria_consolidation_fact_checker"] = module
    spec.loader.exec_module(module)
    return module


def _check(claim, sources=None, log_path=None, context=None):
    module = _load_fact_checker_module()
    return module.fact_check(claim, sources=sources, log_path=log_path, context=context)


# ---------------------------------------------------------------------------
# API existence
# ---------------------------------------------------------------------------

def test_module_exists():
    module = _load_fact_checker_module()
    assert module is not None


def test_module_exports_fact_check_function():
    module = _load_fact_checker_module()
    assert hasattr(module, "fact_check")


def test_module_exports_context7_client_class():
    module = _load_fact_checker_module()
    assert hasattr(module, "Context7Client")


# ---------------------------------------------------------------------------
# Success path — verified claim
# ---------------------------------------------------------------------------

def test_fact_check_returns_passed_true_when_context7_verifies_claim(mocker):
    """When Context7Client finds supporting context, fact_check returns passed=True."""
    mocker.patch.dict(os.environ, {"CONTEXT7_API_KEY": "test-key-123"})
    module = _load_fact_checker_module()
    mocker.patch.object(
        module.Context7Client,
        "verify_claim",
        return_value={
            "passed": True,
            "supporting_contexts": [
                {"text": "OpenClaw supports cron scheduling", "source": "docs.openclaw.com"}
            ],
            "confidence": 0.95,
        },
    )

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        log_path = tmp.name

    try:
        result = _check(
            claim="OpenClaw supports cron scheduling",
            sources=["https://docs.openclaw.com"],
            log_path=log_path,
        )
        assert result["passed"] is True
        assert result["skipped"] is False
        assert "supporting_contexts" in result
        assert result["confidence"] == 0.95
    finally:
        Path(log_path).unlink(missing_ok=True)


def test_fact_check_returns_passed_false_when_context7_finds_no_support(mocker):
    """When Context7Client finds no supporting context, fact_check returns passed=False."""
    mock_client = MagicMock()
    mock_client.verify_claim.return_value = {
        "passed": False,
        "supporting_contexts": [],
        "confidence": 0.1,
    }

    mocker.patch(
        "memoria_consolidation_fact_checker.Context7Client",
        return_value=mock_client,
    )

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        log_path = tmp.name

    try:
        result = _check(
            claim="This is definitely false and has no supporting docs",
            sources=["https://docs.openclaw.com"],
            log_path=log_path,
        )
        assert result["passed"] is False
        assert result["skipped"] is False
    finally:
        Path(log_path).unlink(missing_ok=True)


def test_fact_check_appends_to_log_on_success(mocker):
    """Successful fact-check writes a JSONL record with passed=true."""
    mocker.patch.dict(os.environ, {"CONTEXT7_API_KEY": "test-key-123"})
    module = _load_fact_checker_module()
    mocker.patch.object(
        module.Context7Client,
        "verify_claim",
        return_value={
            "passed": True,
            "supporting_contexts": [
                {"text": "Example", "source": "https://example.com"}
            ],
            "confidence": 0.9,
        },
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "fact_check_log.jsonl")
        _check(
            claim="Sample claim",
            sources=["https://example.com"],
            log_path=log_path,
        )

        assert Path(log_path).exists()
        lines = Path(log_path).read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["passed"] is True
        assert record["skipped"] is False
        assert record["claim"] == "Sample claim"


def test_fact_check_appends_to_log_on_failure(mocker):
    """Failed fact-check writes a JSONL record with passed=false."""
    mock_client = MagicMock()
    mock_client.verify_claim.return_value = {
        "passed": False,
        "supporting_contexts": [],
        "confidence": 0.05,
    }

    mocker.patch(
        "memoria_consolidation_fact_checker.Context7Client",
        return_value=mock_client,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "fact_check_log.jsonl")
        _check(
            claim="Unsubstantiated claim",
            sources=["https://example.com"],
            log_path=log_path,
        )

        lines = Path(log_path).read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["passed"] is False
        assert record["skipped"] is False
        assert record["claim"] == "Unsubstantiated claim"


# ---------------------------------------------------------------------------
# Append-only log behaviour
# ---------------------------------------------------------------------------

def test_log_is_append_only_prevents_overwrite(mocker):
    """Multiple calls append; existing records are never overwritten."""
    mock_client = MagicMock()
    mock_client.verify_claim.return_value = {
        "passed": True,
        "supporting_contexts": [],
        "confidence": 0.9,
    }

    mocker.patch(
        "memoria_consolidation_fact_checker.Context7Client",
        return_value=mock_client,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "fact_check_log.jsonl")

        _check(claim="First claim", sources=[], log_path=log_path)
        _check(claim="Second claim", sources=[], log_path=log_path)
        _check(claim="Third claim", sources=[], log_path=log_path)

        lines = Path(log_path).read_text().strip().splitlines()
        assert len(lines) == 3

        # Verify each line is distinct (append only)
        claims = [json.loads(line)["claim"] for line in lines]
        assert claims == ["First claim", "Second claim", "Third claim"]


def test_log_opened_in_append_mode(mocker):
    """Log file must be opened with 'a', never 'w' or 'r+'."""
    open_calls = []

    original_open = open

    def tracking_open(path, mode="r", *args, **kwargs):
        if "fact_check" in str(path) or "jsonl" in str(path):
            open_calls.append((str(path), mode))
        return original_open(path, mode, *args, **kwargs)

    mocker.patch("builtins.open", side_effect=tracking_open)

    mock_client = MagicMock()
    mock_client.verify_claim.return_value = {
        "passed": True,
        "supporting_contexts": [],
        "confidence": 0.9,
    }
    mocker.patch(
        "memoria_consolidation_fact_checker.Context7Client",
        return_value=mock_client,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "fact_check_log.jsonl")
        _check(claim="test", sources=[], log_path=log_path)

    # All jsonl opens must use append mode 'a'
    jsonl_opens = [(p, m) for p, m in open_calls if "fact_check" in p or "jsonl" in p]
    for _path, mode in jsonl_opens:
        assert "a" in mode, f"Log file opened with mode={mode!r}, expected append mode"
        assert "w" not in mode and "+" not in mode, f"Log file opened with unsafe mode={mode!r}"


# ---------------------------------------------------------------------------
# CONTEXT7_API_KEY missing — skipped, never raises
# ---------------------------------------------------------------------------

def test_missing_context7_api_key_returns_skipped_and_warns(mocker):
    """CONTEXT7_API_KEY missing → warning logged + {passed: False, skipped: True}."""
    # Ensure the env var is not set (or explicitly delete it for this test)
    mocker.patch.dict(os.environ, {}, clear=True)

    # Spy on logging so we can assert a warning was emitted
    warning_calls = []
    mocker.patch(
        "memoria_consolidation_fact_checker._logger.warning",
        side_effect=lambda *args, **kwargs: warning_calls.append(args[0] if args else ""),
    )

    result = _check(
        claim="Any claim",
        sources=["https://example.com"],
        log_path=None,
    )

    assert result["passed"] is False
    assert result["skipped"] is True
    assert "CONTEXT7_API_KEY" in str(warning_calls) or any(
        "CONTEXT7_API_KEY" in str(w) for w in warning_calls
    ), "Expected warning about missing CONTEXT7_API_KEY"


def test_missing_api_key_does_not_raise(mocker):
    """Missing CONTEXT7_API_KEY must never raise an exception."""
    mocker.patch.dict(os.environ, {}, clear=True)

    # This should complete without raising
    try:
        result = _check(claim="test", sources=[], log_path=None)
        # Must return skipped result, not raise
        assert "skipped" in result
    except Exception as exc:
        pytest.fail(f"fact_check raised {type(exc).__name__} instead of returning skipped result: {exc}")


def test_missing_api_key_appends_skipped_record_to_log(mocker):
    """When CONTEXT7_API_KEY is missing, the log record should reflect skipped=True."""
    mocker.patch.dict(os.environ, {}, clear=True)

    mock_warning = mocker.patch(
        "memoria_consolidation_fact_checker._logger.warning",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "fact_check_log.jsonl")
        _check(claim="Test skipped", sources=[], log_path=log_path)

        # The record should be written with skipped=True
        assert Path(log_path).exists()
        lines = Path(log_path).read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["skipped"] is True
        assert record["passed"] is False


# ---------------------------------------------------------------------------
# Context7Client — verify_claim contract
# ---------------------------------------------------------------------------

def test_context7_client_verify_claim_returns_dict_with_required_keys(mocker):
    """verify_claim must return a dict with passed, supporting_contexts, confidence."""
    mocker.patch.dict(os.environ, {"CONTEXT7_API_KEY": "test-key-123"})

    module = _load_fact_checker_module()
    client = module.Context7Client()

    # Mock the requests session to avoid real HTTP calls
    mock_get = mocker.patch.object(client, "_get", return_value=[])

    result = client.verify_claim(
        claim="Test claim",
        sources=["https://example.com"],
    )

    assert isinstance(result, dict)
    assert "passed" in result
    assert "supporting_contexts" in result
    assert "confidence" in result
    assert result["passed"] is False  # No context found → fails closed


def test_context7_client_reports_supporting_contexts(mocker):
    """verify_claim populates supporting_contexts when docs contain relevant text."""
    mocker.patch.dict(os.environ, {"CONTEXT7_API_KEY": "test-key-123"})

    module = _load_fact_checker_module()
    client = module.Context7Client()

    mock_result = {
        "result": {
            "content": [
                {"text": "OpenClaw runs as a daemon service", "location": {"url": "https://docs.openclaw.com/readme"}}
            ]
        }
    }
    mocker.patch.object(client, "_get", return_value=mock_result)

    result = client.verify_claim(
        claim="OpenClaw runs as a daemon",
        sources=["https://docs.openclaw.com"],
    )

    assert result["passed"] is True
    assert len(result["supporting_contexts"]) == 1
    assert result["supporting_contexts"][0]["text"] == "OpenClaw runs as a daemon service"
    assert result["confidence"] > 0.0


def test_context7_client_empty_result_yields_passed_false(mocker):
    """No matching docs → passed=False, empty supporting_contexts."""
    mocker.patch.dict(os.environ, {"CONTEXT7_API_KEY": "test-key-123"})

    module = _load_fact_checker_module()
    client = module.Context7Client()
    mocker.patch.object(client, "_get", return_value={"result": {"content": []}})

    result = client.verify_claim(
        claim="No docs exist for this claim",
        sources=["https://example.com"],
    )

    assert result["passed"] is False
    assert result["supporting_contexts"] == []


# ---------------------------------------------------------------------------
# Context & claim passthrough
# ---------------------------------------------------------------------------

def test_context_passed_to_context7_client(mocker):
    """The context dict is forwarded to Context7Client and included in the log."""
    mocker.patch.dict(os.environ, {"CONTEXT7_API_KEY": "test-key-123"})

    mock_client = MagicMock()
    mock_client.verify_claim.return_value = {
        "passed": True,
        "supporting_contexts": [],
        "confidence": 0.9,
    }
    mocker.patch(
        "memoria_consolidation_fact_checker.Context7Client",
        return_value=mock_client,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "fact_check_log.jsonl")
        _check(
            claim="Test",
            sources=["https://example.com"],
            log_path=log_path,
            context={"entity_key": "e1", "rule_id": "R001"},
        )

        lines = Path(log_path).read_text().strip().splitlines()
        record = json.loads(lines[0])
        assert record["context"]["entity_key"] == "e1"
        assert record["context"]["rule_id"] == "R001"


def test_sources_default_to_official_docs_list(mocker):
    """When sources is None, the official docs list is used."""
    mocker.patch.dict(os.environ, {"CONTEXT7_API_KEY": "test-key-123"})
    module = _load_fact_checker_module()
    mocker.patch.object(
        module.Context7Client,
        "verify_claim",
        return_value={
            "passed": True,
            "supporting_contexts": [],
            "confidence": 0.9,
        },
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "fact_check_log.jsonl")
        # Call without sources → should default
        _check(claim="test", sources=None, log_path=log_path)

        lines = Path(log_path).read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["sources"] == module.DEFAULT_OFFICIAL_DOCS_SOURCES
