"""Tests for vault/research/retry_policy.py"""
import datetime
import os
import tempfile
from unittest.mock import patch

import pytest

from vault.research.retry_policy import (
    NonRetriableError,
    build_retry_record,
    log_exhausted_event,
    next_retry_delay,
    should_retry,
)


# ---------------------------------------------------------------------------
# should_retry
# ---------------------------------------------------------------------------


class TestShouldRetry:
    def test_429_retries_when_under_max(self):
        assert should_retry(429, retry_count=0) is True
        assert should_retry(429, retry_count=1) is True
        assert should_retry(429, retry_count=2) is True

    def test_429_no_retry_when_exhausted(self):
        assert should_retry(429, retry_count=3) is False

    def test_500_retries_when_under_max(self):
        assert should_retry(500, retry_count=0) is True
        assert should_retry(500, retry_count=2) is True

    def test_503_retries_when_under_max(self):
        assert should_retry(503, retry_count=1) is True

    def test_5xx_no_retry_when_exhausted(self):
        assert should_retry(500, retry_count=3) is False
        assert should_retry(503, retry_count=3) is False

    def test_401_no_retry(self):
        assert should_retry(401, retry_count=0) is False

    def test_403_no_retry(self):
        assert should_retry(403, retry_count=0) is False

    def test_timeout_retry_once_immediately(self):
        # "timeout" represented as status_code=None
        assert should_retry(None, retry_count=0) is True

    def test_timeout_exhausted_after_combined_retries(self):
        # After 1 immediate + 3 5xx-policy retries = 4 total → exhausted at retry_count=4
        assert should_retry(None, retry_count=4) is False


# ---------------------------------------------------------------------------
# next_retry_delay
# ---------------------------------------------------------------------------


class TestNextRetryDelay:
    def test_429_exponential_backoff(self):
        # 60, 120, 240, 480
        assert next_retry_delay(429, retry_count=0) == 60
        assert next_retry_delay(429, retry_count=1) == 120
        assert next_retry_delay(429, retry_count=2) == 240
        assert next_retry_delay(429, retry_count=3) == 480

    def test_5xx_backoff(self):
        # 30, 60, 120
        assert next_retry_delay(500, retry_count=0) == 30
        assert next_retry_delay(500, retry_count=1) == 60
        assert next_retry_delay(500, retry_count=2) == 120

    def test_503_same_backoff_as_500(self):
        assert next_retry_delay(503, retry_count=0) == 30
        assert next_retry_delay(503, retry_count=1) == 60

    def test_timeout_first_retry_is_immediate(self):
        # retry_count=0 → immediate (0s)
        assert next_retry_delay(None, retry_count=0) == 0

    def test_timeout_subsequent_retries_follow_5xx_policy(self):
        # retry_count=1 → first 5xx-style delay (30s)
        assert next_retry_delay(None, retry_count=1) == 30
        assert next_retry_delay(None, retry_count=2) == 60
        assert next_retry_delay(None, retry_count=3) == 120

    def test_401_raises(self):
        with pytest.raises(NonRetriableError):
            next_retry_delay(401, retry_count=0)

    def test_403_raises(self):
        with pytest.raises(NonRetriableError):
            next_retry_delay(403, retry_count=0)


# ---------------------------------------------------------------------------
# build_retry_record
# ---------------------------------------------------------------------------


class TestBuildRetryRecord:
    def test_schema_keys(self):
        record = build_retry_record(
            event_key="github:pr:42",
            error="HTTP 429",
            retry_count=1,
            next_retry_at="2026-04-18T18:00:00Z",
        )
        assert set(record.keys()) == {
            "event_key",
            "status",
            "retry_count",
            "last_error",
            "next_retry_at",
            "last_attempt_at",
        }

    def test_status_pending_retry_while_under_max(self):
        record = build_retry_record(
            event_key="github:pr:42",
            error="HTTP 500",
            retry_count=2,
            next_retry_at="2026-04-18T18:00:00Z",
        )
        assert record["status"] == "pending_retry"

    def test_status_exhausted_at_max_retries(self):
        record = build_retry_record(
            event_key="github:pr:42",
            error="HTTP 500",
            retry_count=3,
            next_retry_at=None,
        )
        assert record["status"] == "exhausted"

    def test_field_values(self):
        record = build_retry_record(
            event_key="github:pr:99",
            error="timeout",
            retry_count=0,
            next_retry_at="2026-04-18T18:30:00Z",
        )
        assert record["event_key"] == "github:pr:99"
        assert record["last_error"] == "timeout"
        assert record["retry_count"] == 0
        assert record["next_retry_at"] == "2026-04-18T18:30:00Z"
        assert record["last_attempt_at"] is not None  # set by function

    def test_exhausted_has_none_next_retry_at(self):
        record = build_retry_record(
            event_key="github:pr:1",
            error="HTTP 429",
            retry_count=3,
            next_retry_at=None,
        )
        assert record["next_retry_at"] is None


# ---------------------------------------------------------------------------
# log_exhausted_event
# ---------------------------------------------------------------------------


class TestLogExhaustedEvent:
    def test_appends_to_consolidation_log(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            log_path = f.name

        try:
            record = build_retry_record(
                event_key="github:pr:77",
                error="HTTP 500",
                retry_count=3,
                next_retry_at=None,
            )
            log_exhausted_event(record, log_path=log_path)

            with open(log_path) as f:
                content = f.read()

            assert "exhausted" in content
            assert "github:pr:77" in content
            assert "HTTP 500" in content
        finally:
            os.unlink(log_path)

    def test_creates_log_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "consolidation-log.md")
            record = build_retry_record(
                event_key="github:pr:88",
                error="timeout",
                retry_count=3,
                next_retry_at=None,
            )
            log_exhausted_event(record, log_path=log_path)
            assert os.path.exists(log_path)
            content = open(log_path).read()
            assert "exhausted" in content

    def test_default_log_path_is_memory_consolidation_log(self):
        """log_exhausted_event default log_path should be memory/consolidation-log.md"""
        import inspect
        from vault.research.retry_policy import log_exhausted_event as _fn
        sig = inspect.signature(_fn)
        default = sig.parameters["log_path"].default
        assert "memory/consolidation-log.md" in default
