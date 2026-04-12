"""LLM-based meeting enrichment — extract summary and decisions from transcript.

Uses OpenAI-compatible API (OmniRoute) to process transcripts.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Você é um assistente que analisa transcrições de reuniões de trabalho.
Dado o transcript de uma reunião, extraia:

1. **Resumo** (2-4 parágrafos): O que foi discutido, pontos principais, acordos.
2. **Decisões** (lista): Cada decisão tomada, com responsável quando mencionado.

Responda em JSON:
{
  "summary": "texto do resumo...",
  "decisions": ["decisão 1", "decisão 2", ...]
}

Seja objetivo e técnico. Responda em português."""

_USER_TEMPLATE = """Analise esta transcrição de reunião:

---
{transcript}
---

Extraia o resumo e as decisões em JSON."""


def _call_llm(messages: list[dict], model: str | None = None) -> str:
    """Call LLM via OpenAI-compatible API."""
    import requests

    base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:20128/v1")
    api_key = os.environ.get(
        "VAULT_LLM_API_KEY",
        os.environ.get("OMNIROUT_API_KEY", "sk-666bb73565412876-w1unhf-b4a81e18"),
    )

    model = model or os.environ.get("VAULT_ENRICH_MODEL", "PremiumFirst")

    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2000,
            "stream": False,
            "stream": False,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def extract_meeting_insights(
    transcript: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Extract summary and decisions from a meeting transcript."""
    if not transcript or not transcript.strip():
        return {"summary": "", "decisions": []}

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_TEMPLATE.format(transcript=transcript[:8000])},
    ]

    try:
        raw = _call_llm(messages, model=model)
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        return {"summary": "", "decisions": [], "error": str(exc)}

    # Parse JSON from response
    try:
        result = json.loads(raw)
        return {
            "summary": result.get("summary", ""),
            "decisions": result.get("decisions", []),
        }
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                return {
                    "summary": result.get("summary", ""),
                    "decisions": result.get("decisions", []),
                }
            except json.JSONDecodeError:
                pass
        # Fallback: use raw text as summary
        return {"summary": raw[:500], "decisions": []}


def enrich_meeting_file(meeting_path: str | Path, transcript: str, model: str | None = None) -> bool:
    """Enrich a meeting markdown file with LLM-extracted summary and decisions.

    Returns True if enrichment was applied.
    """
    path = Path(meeting_path)
    if not path.exists():
        return False

    insights = extract_meeting_insights(transcript, model=model)
    if not insights.get("summary") and not insights.get("decisions"):
        return False

    text = path.read_text(encoding="utf-8")

    # Replace ## Resumo section
    summary_block = insights["summary"]
    text = re.sub(
        r"(## Resumo\n\n)(.*?)(\n\n## Decisões)",
        lambda m: m.group(1) + summary_block + "\n" + m.group(3),
        text,
        flags=re.DOTALL,
    )

    # Replace ## Decisões section
    if insights.get("decisions"):
        decisions_md = "\n".join(f"- {d}" for d in insights["decisions"])
        text = re.sub(
            r"(## Decisões\n\n)(.*?)(\n\n## )",
            lambda m: m.group(1) + decisions_md + "\n" + m.group(3),
            text,
            flags=re.DOTALL,
        )

    path.write_text(text, encoding="utf-8")
    return True
