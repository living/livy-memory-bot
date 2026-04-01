#!/usr/bin/env python3
"""
meetings-tldv/search.py — Skill: busca reuniões no Supabase TLDV.

Usage:
    python3 skills/meetings-tldv/search.py --query "decisões sobre o BAT"
    python3 skills/meetings-tldv/search.py --dry-run --query "últimas reuniões"
    python3 skills/meetings-tldv/search.py --mode detail --meeting-id abc123
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal

import requests

BRT = timezone(timedelta(hours=-3))

# ── Config ────────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DEFAULT_LIMIT = 5
MAX_LIMIT = 20
DEFAULT_THRESHOLD = 0.55


# ── Helpers ──────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def brt(dt: datetime) -> datetime:
    """Convert UTC datetime to BRT (no DST)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BRT)


def query_recency_ts_from_text(question: str) -> float | None:
    """Extrai timestamp de recência de uma pergunta livre."""
    q = question.lower()
    now = datetime.now(BRT)

    if "última semana" in q:
        return (now - timedelta(days=7)).timestamp()
    if "este mês" in q:
        return datetime(now.year, now.month, 1, tzinfo=BRT).timestamp()

    months = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
        "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    }
    for month_name, month_num in months.items():
        if month_name in q:
            year = now.year if month_num <= now.month else now.year - 1
            start = datetime(year, month_num, 1, tzinfo=BRT)
            return start.timestamp()

    return None


def infer_mode(question: str) -> Literal["temporal", "semantic", "detail"]:
    """Analisa a pergunta e decide o modo de busca."""
    q = question.lower()

    if any(kw in q for kw in ["meeting ", "meeting_id", "summarize", "detail da reun"]):
        return "detail"
    if any(kw in q for kw in ["última semana", "este mês", "março", "janeiro", "fevereiro",
                                 "entre ", "período"]):
        return "temporal"
    return "semantic"


@lru_cache(maxsize=1000)
def get_embedding(text: str) -> list[float] | None:
    """Embed text via OpenAI, cached 5 min per text string."""
    if not OPENAI_API_KEY:
        return None
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return resp.data[0].embedding
    except Exception as e:
        log(f"Embedding error: {e}")
        return None


def get_supabase_headers():
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }


def rpc_match_vectors(embedding: list[float], threshold: float, limit: int) -> list[dict] | None:
    """Call match_summary_vectors RPC. Returns None if RPC unavailable (caller falls back)."""
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/match_summary_vectors",
            headers=get_supabase_headers(),
            json={"query_embedding": embedding, "threshold": threshold, "limit": limit},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        log(f"RPC returned {resp.status_code}, falling back to ILIKE")
    except Exception as e:
        log(f"RPC call failed: {e}, falling back to ILIKE")
    return None


def search_semantic_fallback(query: str, limit: int) -> list[dict]:
    """Fallback: ILIKE search when RPC or OpenAI API unavailable."""
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/meeting_memories",
            headers=get_supabase_headers(),
            params={
                "select": "id,meeting_id,user_id,title,summary,created_at",
                "summary": f"ilike.*{query}*",
                "order": "created_at.desc",
                "limit": str(limit),
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        log(f"Fallback search failed: {resp.status_code}")
    except Exception as e:
        log(f"Fallback search error: {e}")
    return []


def search_temporal(start_utc: datetime, end_utc: datetime, limit: int) -> list[dict]:
    """SELECT via REST API for temporal range."""
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/meeting_memories",
            headers=get_supabase_headers(),
            params={
                "select": "id,meeting_id,user_id,title,summary,created_at",
                "created_at": f"gte.{start_utc.isoformat()}",
                "created_at": f"lte.{end_utc.isoformat()}",
                "order": "created_at.desc",
                "limit": str(limit),
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        log(f"Temporal search failed: {resp.status_code} {resp.text}")
    except Exception as e:
        log(f"Temporal search error: {e}")
    return []


def search_detail(meeting_id: str) -> dict | None:
    """SELECT single meeting by meeting_id."""
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/meeting_memories",
            headers=get_supabase_headers(),
            params={
                "select": "id,meeting_id,user_id,title,summary,insights_json,created_at",
                "meeting_id": f"eq.{meeting_id}",
                "limit": "1",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            rows = resp.json()
            return rows[0] if rows else None
    except Exception as e:
        log(f"Detail search error: {e}")
    return None


def hybrid_score(result_created_at: datetime, semantic_sim: float | None,
                 query_recency_ts: float | None) -> float:
    """score = 0.4 * recency_normalized + 0.6 * semantic_similarity"""
    DAYS_90 = 90 * 86400
    now_ts = datetime.now(BRT).timestamp()

    if query_recency_ts is not None:
        age_days = (now_ts - result_created_at.timestamp()) / 86400
        recency_norm = max(0.0, 1.0 - age_days / DAYS_90)
    else:
        recency_norm = 0.5

    sim = 0.5 if semantic_sim is None else semantic_sim
    return 0.4 * recency_norm + 0.6 * sim


def format_result(rows: list[dict], mode: str, query: str,
                  threshold: float) -> str:
    """Format search results as markdown."""
    if not rows:
        return f"**Nenhuma reunião encontrada** para: \"{query}\""

    lines = [
        f"## Reuniões — TLDV\n",
        f"**Modo:** {mode} | **Query:** \"{query}\" | **Threshold:** {threshold}\n",
        f"**Encontradas:** {len(rows)} reuniões\n",
        "---\n",
    ]

    for i, row in enumerate(rows, 1):
        created = row.get("created_at", "")
        if created:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            created_brt = brt(dt).strftime("%d/%m/%Y, %Hh%M BRT")
        else:
            created_brt = "—"

        score = row.get("similarity", 0.0) or row.get("hybrid_score", 0.0)
        title = row.get("title", "Sem título")
        summary = row.get("summary", "")[:200]

        lines.append(f"### {i}. {title}\n")
        lines.append(f"**Score:** {score:.2f} | **Data:** {created_brt}\n")
        if summary:
            lines.append(f"> {summary}\n")
        lines.append("---\n")

    lines.append(f"_{len(rows)} resultados · query: \"{query}\" · threshold: {threshold}_")
    return "".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="meetings-tldv search")
    parser.add_argument("--query", help="Pergunta livre (infern modo)")
    parser.add_argument("--mode", choices=["temporal", "semantic", "detail"],
                        help="Modo forçado (sobressai inferência)")
    parser.add_argument("--start", help="Data início (YYYY-MM-DD)")
    parser.add_argument("--end", help="Data fim (YYYY-MM-DD)")
    parser.add_argument("--meeting-id", help="Meeting ID (modo detail)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--dry-run", action="store_true",
                        help="Testa inferência sem queryar Supabase")
    args = parser.parse_args()

    # Validate env (skip for dry-run since it doesn't query Supabase)
    if not args.dry_run:
        missing = []
        if not SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not SUPABASE_SERVICE_ROLE_KEY:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if missing:
            log(f"ERRO: variáveis de ambiente faltando: {', '.join(missing)}")
            sys.exit(1)

    # Infer or validate mode
    if args.mode:
        mode = args.mode
    elif args.meeting_id:
        mode = "detail"
    elif args.query:
        mode = infer_mode(args.query)
    else:
        log("ERRO: forneça --query, --meeting-id, ou --mode")
        sys.exit(1)

    if args.dry_run:
        log(f"[DRY RUN] mode={mode} query={args.query}")
        recency = query_recency_ts_from_text(args.query or "")
        log(f"[DRY RUN] recency_ts={recency}")
        return

    log(f"Mode: {mode}")

    # Execute
    if mode == "temporal":
        start_dt = datetime.fromisoformat(args.start) if args.start \
            else datetime.now(BRT) - timedelta(days=30)
        end_dt = datetime.fromisoformat(args.end) if args.end \
            else datetime.now(BRT)
        start_utc = start_dt.astimezone(timezone.utc)
        end_utc = end_dt.astimezone(timezone.utc)
        rows = search_temporal(start_utc, end_utc, args.limit)

    elif mode == "semantic":
        if not args.query:
            log("ERRO: --query requerido para modo semantic")
            sys.exit(1)
        embedding = get_embedding(args.query)
        if embedding:
            rows = rpc_match_vectors(embedding, args.threshold, args.limit)
            if rows is None:
                rows = search_semantic_fallback(args.query, args.limit)
        else:
            log("OpenAI API indisponível, usando fallback ILIKE")
            rows = search_semantic_fallback(args.query, args.limit)

    elif mode == "detail":
        if not args.meeting_id:
            log("ERRO: --meeting-id requerido para modo detail")
            sys.exit(1)
        row = search_detail(args.meeting_id)
        rows = [row] if row else []

    if not rows:
        print(f"**Nenhuma reunião encontrada**")
        return

    output = format_result(rows, mode, args.query or args.meeting_id, args.threshold)
    print(output)


if __name__ == "__main__":
    main()
