"""Fact-checking gate using Context7 + official docs sources.

Task 5 requirements:
- Missing CONTEXT7_API_KEY: never raise, warn and return {passed: False, skipped: True}
- Append-only JSONL log writer (open with mode "a")
- Client abstraction for Context7 + official docs source list
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


_logger = logging.getLogger(__name__)

DEFAULT_OFFICIAL_DOCS_SOURCES = [
    "https://docs.openclaw.com",
    "https://openclaw.ai/docs",
    "https://github.com/openclaw/openclaw",
]

DEFAULT_FACT_CHECK_LOG_PATH = Path(__file__).resolve().parents[2] / "memory" / "fact_check_log.jsonl"


class Context7Client:
    """Small abstraction for querying Context7 and scoring claim support."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.context7.com/v1",
        sources: list[str] | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = api_key or os.getenv("CONTEXT7_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.sources = list(sources or DEFAULT_OFFICIAL_DOCS_SOURCES)
        self.timeout_seconds = timeout_seconds

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = parse.urlencode(params or {}, doseq=True)
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"

        req = request.Request(url)
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Accept", "application/json")

        with request.urlopen(req, timeout=self.timeout_seconds) as resp:  # nosec B310
            raw = resp.read().decode("utf-8")
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return {}

    def verify_claim(self, claim: str, sources: list[str] | None = None) -> dict[str, Any]:
        """Verify a claim against Context7-backed official docs context.

        Fail-closed behavior:
        - No contexts / API errors => passed=False
        """
        check_sources = list(sources or self.sources)
        supporting_contexts: list[dict[str, Any]] = []

        try:
            payload = self._get(
                "search",
                params={
                    "q": claim,
                    "sources": check_sources,
                },
            )
        except Exception as exc:  # network/parsing/etc; caller should not crash
            _logger.warning("Context7 lookup failed: %s", exc)
            payload = {}

        content_items: list[dict[str, Any]] = []

        if isinstance(payload, dict):
            if isinstance(payload.get("result"), dict) and isinstance(payload["result"].get("content"), list):
                content_items = [item for item in payload["result"]["content"] if isinstance(item, dict)]
            elif isinstance(payload.get("content"), list):
                content_items = [item for item in payload["content"] if isinstance(item, dict)]

        claim_tokens = {token.lower() for token in claim.split() if token.strip()}

        for item in content_items:
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            haystack = text.lower()
            # lightweight relevance check: at least one claim token appears
            if claim_tokens and not any(tok in haystack for tok in claim_tokens):
                continue

            source = item.get("source")
            if not source and isinstance(item.get("location"), dict):
                source = item["location"].get("url")
            supporting_contexts.append(
                {
                    "text": text,
                    "source": source or "unknown",
                }
            )

        passed = len(supporting_contexts) > 0
        confidence = 0.9 if passed else 0.0

        return {
            "passed": passed,
            "supporting_contexts": supporting_contexts,
            "confidence": confidence,
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_fact_check_log(log_path: str | Path, record: dict[str, Any]) -> None:
    """Append a single JSONL record (append-only)."""
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Requirement: append-only writer, never overwrite.
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def fact_check(
    claim: str,
    sources: list[str] | None = None,
    log_path: str | Path | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run fact-check gate.

    Missing CONTEXT7_API_KEY behavior:
    - log warning
    - return {passed: False, skipped: True}
    - never raise
    """
    context = context or {}
    effective_sources = list(sources or DEFAULT_OFFICIAL_DOCS_SOURCES)
    effective_log_path = Path(log_path) if log_path else DEFAULT_FACT_CHECK_LOG_PATH

    api_key = os.getenv("CONTEXT7_API_KEY")
    if not api_key:
        _logger.warning("CONTEXT7_API_KEY missing; skipping fact-check for claim")
        result = {
            "passed": False,
            "skipped": True,
            "supporting_contexts": [],
            "confidence": 0.0,
        }
        record = {
            "ts": _utc_now_iso(),
            "claim": claim,
            "sources": effective_sources,
            "context": context,
            **result,
        }
        append_fact_check_log(effective_log_path, record)
        return result

    # Dynamic lookup so mocker patches applied after module load still take effect.
    _mod = sys.modules.get(__name__)
    _ctx7_cls = getattr(_mod, "Context7Client", None) if _mod else None
    if _ctx7_cls is None:
        _logger.warning("Context7Client not available; skipping fact-check")
        result = {
            "passed": False,
            "skipped": True,
            "supporting_contexts": [],
            "confidence": 0.0,
        }
        record = {"ts": _utc_now_iso(), "claim": claim, "sources": effective_sources, "context": context, **result}
        append_fact_check_log(effective_log_path, record)
        return result
    client = _ctx7_cls(api_key=api_key, sources=effective_sources)

    try:
        verification = client.verify_claim(claim=claim, sources=effective_sources)
    except Exception as exc:
        _logger.warning("Fact-check verification failed, failing closed: %s", exc)
        verification = {
            "passed": False,
            "supporting_contexts": [],
            "confidence": 0.0,
        }

    result = {
        "passed": bool(verification.get("passed", False)),
        "skipped": False,
        "supporting_contexts": verification.get("supporting_contexts", []),
        "confidence": float(verification.get("confidence", 0.0) or 0.0),
    }

    record = {
        "ts": _utc_now_iso(),
        "claim": claim,
        "sources": effective_sources,
        "context": context,
        **result,
    }
    append_fact_check_log(effective_log_path, record)
    return result
