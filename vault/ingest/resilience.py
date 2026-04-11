"""HTTP resilience — retry with backoff, error classification."""
from __future__ import annotations

import time
from typing import Any, Callable

import requests


def classify_error(exc_or_response: Any) -> str:
    """Classify an HTTP error or exception into a category."""
    if isinstance(exc_or_response, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(exc_or_response, requests.exceptions.ConnectionError):
        return "connection_error"

    # If the object has a status_code directly (e.g., a response object passed in),
    # use it; otherwise look for a nested .response attribute (e.g., HTTPError).
    if hasattr(exc_or_response, "status_code") and isinstance(
        exc_or_response.status_code, int
    ):
        status = exc_or_response.status_code
    else:
        # e.g. requests.exceptions.HTTPError carries .response
        resp = getattr(exc_or_response, "response", None)
        status = getattr(resp, "status_code", None)
        if not isinstance(status, int):
            return "unknown"

    if status == 429:
        return "rate_limit"
    if status == 401:
        return "auth"
    if status == 404:
        return "not_found"
    if 500 <= status < 600:
        return "server_error"
    return "unknown"


def is_retryable(exc_or_response: Any) -> bool:
    """Determine if an error is worth retrying."""
    category = classify_error(exc_or_response)
    return category in ("server_error", "rate_limit", "timeout", "connection_error")


def retry_with_backoff(
    fn: Callable,
    max_retries: int = 3,
    backoff_base: float = 30.0,
) -> Any:
    """Execute fn with retry and exponential backoff."""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if not is_retryable(exc) or attempt >= max_retries:
                raise

            # Check Retry-After header
            resp = getattr(exc, "response", None)
            retry_after = None
            if resp and resp.headers.get("Retry-After"):
                try:
                    retry_after = float(resp.headers["Retry-After"])
                except (ValueError, TypeError):
                    retry_after = None

            wait = retry_after if retry_after is not None else backoff_base * (2**attempt)
            time.sleep(wait)

    raise last_exc  # Should not reach here
