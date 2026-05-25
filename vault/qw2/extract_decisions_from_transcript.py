#!/usr/bin/env python3
"""
Extract structured decisions from TLDV meeting transcripts using LLM.
Uses fastest model via OmniRoute for low-latency extraction.
Segments are fetched from Azure Blob / Supabase and formatted to readable text.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Você é um assistente que analisa transcrições de reuniões de trabalho.
Sua tarefa é extrair TODAS as decisões tomadas na reunião.

Uma decisão é: algo que o grupo concordou em fazer, aprovou, definiu, ou se comprometeu.
Inclua decisões explícitas e implícitas (quando o grupo aceita uma proposta sem objeção).

Responda APENAS com JSON válido:
{
  "decisions": [
    {
      "text": "descrição curta e objetiva da decisão (máx 200 chars)",
      "confidence": 0.0-1.0,
      "responsible": "nome da pessoa responsável (ou null se não mencionado)"
    }
  ]
}

Regras:
- Seja conservador: só inclua se houver evidência clara de decisão
- Não inclua TO-DO items individuais sem decisão do grupo
- decisões em português
- confidence: 0.9 se for explícita, 0.7 se for implícita, 0.5 se houver dúvida
- Se não houver nenhuma decisão, retorne {"decisions": [], "meeting_summary": ""}"""


def _call_llm(messages: list[dict], model: str = "fastest") -> str:
    """Call LLM via OmniRoute OpenAI-compatible API."""
    import requests

    base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:20128/v1")
    api_key = os.environ.get(
        "OMNIROUT_API_KEY",
        os.environ.get("VAULT_LLM_API_KEY", "sk-666bb73565412876-w1unhf-b4a81e18"),
    )

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 1024,
        "stream": False,
    }

    try:
        resp = requests.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=60)
        if resp.status_code != 200:
            logger.warning(f"LLM call failed: {resp.status_code} {resp.text[:200]}")
            return "{}"
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"LLM call error: {e}")
        return "{}"


def _segments_to_text(segments: list[dict], max_chars: int = 12000) -> str:
    """Convert transcript segments to readable text."""
    lines = []
    for s in segments:
        speaker = s.get("speaker") or ""
        text = s.get("text", "").strip()
        if text:
            if speaker:
                lines.append(f"{speaker}: {text}")
            else:
                lines.append(text)
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:6000] + "\n...\n" + text[-6000:]
    return text


def _get_meeting_tags(meeting_id: str, tldv_client) -> list[str]:
    """Fetch meeting tags from Supabase summaries."""
    try:
        summaries = tldv_client.fetch_summaries(meeting_id) or []
        for summary in summaries:
            tags = summary.get("tags")
            if isinstance(tags, list) and tags:
                return [str(t).strip() for t in tags if str(t).strip()]
    except Exception:
        pass
    return []


def extract_decisions_from_transcript(
    meeting_id: str,
    meeting_name: str = "",
    model: str = "fastest",
    tldv_client=None,
) -> list[dict[str, Any]]:
    """
    Extract structured decisions from a meeting transcript using LLM.

    Fetches segments from Azure/Supabase, formats to readable text, sends to LLM.
    Also fetches meeting tags from Supabase summaries.
    Returns list of decision dicts with keys: text, confidence, responsible, tags.
    """
    if tldv_client is None:
        os.environ.setdefault("SUPABASE_URL", "https://supabase.living.locaweb.com.br")
        os.environ.setdefault(
            "SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        )
        from vault.research.tldv_client import TLDVClient

        tldv_client = TLDVClient(lookback_days=60)

    # Fetch tags from Supabase (lightweight call)
    tags = _get_meeting_tags(meeting_id, tldv_client)

    segments = tldv_client.load_transcript_segments(meeting_id)
    if not segments:
        logger.debug(f"No segments for meeting {meeting_id}")
        return []

    transcript = _segments_to_text(segments)
    logger.debug(f"Transcript text for meeting {meeting_id}: {len(transcript)} chars, tags={tags}")

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Reunião: {meeting_name}\n\n---\n{transcript}\n---",
        },
    ]

    raw = _call_llm(messages, model=model)

    try:
        json_str = raw.strip()
        if json_str.startswith("```"):
            json_str = re.sub(r"^```(?:json)?\s*", "", json_str)
            json_str = re.sub(r"\s*```$", "", json_str)
        data = json.loads(json_str)
        decisions = data.get("decisions", [])
        # Add tags to each decision
        for d in decisions:
            d["tags"] = tags
        logger.debug(f"Extracted {len(decisions)} decisions from meeting {meeting_id}")
        return decisions
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response for meeting {meeting_id}: {e}")
        logger.debug(f"Raw response: {raw[:500]}")
        return []


def main():
    """Test script — extract decisions from a meeting given as argument."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract decisions from transcript using LLM")
    parser.add_argument("meeting_id", help="TLDV meeting ID")
    parser.add_argument("--model", default="fastest")
    args = parser.parse_args()

    os.environ.setdefault("SUPABASE_URL", "https://supabase.living.locaweb.com.br")
    os.environ.setdefault(
        "SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from vault.research.tldv_client import TLDVClient

    client = TLDVClient(lookback_days=60)
    meetings = client.fetch_events_since(None)
    meeting = next(
        (m for m in meetings if m.get("meeting_id") == args.meeting_id), None
    )

    if not meeting:
        print(f"Meeting {args.meeting_id} not found")
        sys.exit(1)

    name = meeting.get("name", "")
    segments = client.load_transcript_segments(args.meeting_id)

    if not segments:
        print(f"No transcript for meeting {args.meeting_id}")
        sys.exit(1)

    print(f"Meeting: {name}")
    print(f"Segments: {len(segments)}")
    print()

    decisions = extract_decisions_from_transcript(
        args.meeting_id, name, args.model, tldv_client=client
    )

    if not decisions:
        print("No decisions found")
    else:
        print(f"Decisions ({len(decisions)}):")
        for i, d in enumerate(decisions, 1):
            print(f"  {i}. [{d.get('confidence', 0):.1f}] {d.get('text', '')[:120]}")
            if d.get("responsible"):
                print(f"     Responsible: {d['responsible']}")


if __name__ == "__main__":
    main()
