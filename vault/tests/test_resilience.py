"""Tests for HTTP resilience — retry with backoff and error classification."""
import pytest
from unittest.mock import Mock, patch
from vault.ingest.resilience import (
    is_retryable,
    retry_with_backoff,
    classify_error,
)


class TestClassifyError:
    def test_429_is_rate_limit(self):
        resp = Mock(status_code=429, headers={"Retry-After": "30"})
        assert classify_error(resp) == "rate_limit"

    def test_500_is_server_error(self):
        resp = Mock(status_code=500, headers={})
        assert classify_error(resp) == "server_error"

    def test_401_is_auth(self):
        resp = Mock(status_code=401, headers={})
        assert classify_error(resp) == "auth"

    def test_404_is_not_found(self):
        resp = Mock(status_code=404, headers={})
        assert classify_error(resp) == "not_found"

    def test_timeout_is_timeout(self):
        import requests
        err = requests.exceptions.Timeout("connection timed out")
        assert classify_error(err) == "timeout"


class TestIsRetryable:
    def test_server_error_is_retryable(self):
        resp = Mock(status_code=500, headers={})
        assert is_retryable(resp) is True

    def test_429_is_retryable(self):
        resp = Mock(status_code=429, headers={"Retry-After": "30"})
        assert is_retryable(resp) is True

    def test_timeout_is_retryable(self):
        import requests
        assert is_retryable(requests.exceptions.Timeout()) is True

    def test_401_is_not_retryable(self):
        resp = Mock(status_code=401, headers={})
        assert is_retryable(resp) is False

    def test_404_is_not_retryable(self):
        resp = Mock(status_code=404, headers={})
        assert is_retryable(resp) is False


class TestRetryWithBackoff:
    def test_succeeds_on_first_try(self):
        fn = Mock(return_value="ok")
        result = retry_with_backoff(fn, max_retries=3)
        assert result == "ok"
        assert fn.call_count == 1

    def test_retries_on_server_error(self):
        import requests
        fn = Mock(side_effect=[
            requests.exceptions.HTTPError(response=Mock(status_code=500)),
            "ok",
        ])
        with patch("time.sleep"):
            result = retry_with_backoff(fn, max_retries=3, backoff_base=0.01)
        assert result == "ok"
        assert fn.call_count == 2

    def test_raises_after_max_retries(self):
        import requests
        fn = Mock(side_effect=requests.exceptions.HTTPError(
            response=Mock(status_code=500)
        ))
        with patch("time.sleep"), pytest.raises(requests.exceptions.HTTPError):
            retry_with_backoff(fn, max_retries=2, backoff_base=0.01)
        assert fn.call_count == 3  # initial + 2 retries

    def test_does_not_retry_non_retryable(self):
        import requests
        fn = Mock(side_effect=requests.exceptions.HTTPError(
            response=Mock(status_code=401)
        ))
        with pytest.raises(requests.exceptions.HTTPError):
            retry_with_backoff(fn, max_retries=3, backoff_base=0.01)
        assert fn.call_count == 1  # No retry for 401

    def test_respects_retry_after_header(self):
        import requests
        resp = Mock(status_code=429, headers={"Retry-After": "0.01"})
        fn = Mock(side_effect=[
            requests.exceptions.HTTPError(response=resp),
            "ok",
        ])
        with patch("time.sleep") as mock_sleep:
            result = retry_with_backoff(fn, max_retries=3, backoff_base=0.01)
        assert result == "ok"
        mock_sleep.assert_called()
