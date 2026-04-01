#!/usr/bin/env python3
"""
meetings-tldv/search.py — Skill: busca reuniões no Supabase TLDV.

Busca na tabela `meetings` (não em `meeting_memories`).
Projeto: fbnelbwsjfjnkiexxtom

Usage:
    python3 skills/meetings-tldv/search.py --query "Status"
    python3 skills/meetings-tldv/search.py --query "Status" --limit 3
    python3 skills/meetings-tldv/search.py --mode temporal --start 2026-03-01 --end 2026-03-31
    python3 skills/meetings-tldv/search.py --mode detail --meeting-id 69cc323d38b6a8001405708a
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

BRT = timezone(timedelta(hours=-3))

# ── Config ────────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")        # https://fbnelbwsjfjnkiexxtom.supabase.co
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

DEFAULT_LIMIT = 5
MAX_LIMIT = 20


# ── Helpers ──────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def brt(dt: datetime) -> datetime:
    """Convert UTC datetime to BRT (no DST)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BRT)


def get_headers():
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }


def query_recency_ts_from_text(question: str) -> tuple[str, str] | None:
    """Extrai janela temporal de uma pergunta livre. Returns (start, end) as ISO strings or None."""
    q = question.lower()
    now = datetime.now(BRT)

    if "última semana" in q:
        start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")
        return start, end
    if "este mês" in q:
        start = datetime(now.year, now.month, 1, tzinfo=BRT).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")
        return start, end

    months = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
        "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    }
    for month_name, month_num in months.items():
        if month_name in q:
            year = now.year if month_num <= now.month else now.year - 1
            start = datetime(year, month_num, 1, tzinfo=BRT).strftime("%Y-%m-%d")
            end = datetime(year, month_num, 28, tzinfo=BRT).strftime("%Y-%m-%d")  # rough
            return start, end
    return None


def infer_mode(question: str, meeting_id: str | None) -> str:
    """Analisa a pergunta e decide o modo de busca."""
    if meeting_id:
        return "detail"
    if query_recency_ts_from_text(question):
        return "temporal"
    return "keyword"


def search_keyword(query: str, limit: int) -> list[dict]:
    """Busca por ILIKE no nome da reunião."""
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/meetings",
            headers=get_headers(),
            params={
                "select": "id,name,created_at,enriched_at,source,enrichment_context",
                "enriched_at": "not.is.null",
                "name": f"ilike.*{query}*",
                "order": "created_at.desc",
                "limit": str(limit),
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        log(f"Keyword search failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        log(f"Keyword search error: {e}")
    return []


def search_temporal(start: str, end: str, limit: int) -> list[dict]:
    """Busca por janela temporal."""
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/meetings",
            headers=get_headers(),
            params={
                "select": "id,name,created_at,enriched_at,source,enrichment_context",
                "enriched_at": "not.is.null",
                "created_at": f"gte.{start}T00:00:00Z",
                "created_at": f"lte.{end}T23:59:59Z",
                "order": "created_at.desc",
                "limit": str(limit),
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        log(f"Temporal search failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        log(f"Temporal search error: {e}")
    return []


def search_detail(meeting_id: str) -> list[dict]:
    """Busca reunião por ID."""
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/meetings",
            headers=get_headers(),
            params={
                "select": "id,name,created_at,enriched_at,source,enrichment_context",
                "enriched_at": "not.is.null",
                "id": f"eq.{meeting_id}",
                "limit": "1",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            rows = resp.json()
            return rows if rows else []
        log(f"Detail search failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        log(f"Detail search error: {e}")
    return []


def get_summaries(meeting_ids: list[str]) -> dict[str, dict]:
    """Busca summaries para uma lista de meeting_ids. Retorna dict keyed by meeting_id."""
    if not meeting_ids:
        return {}
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/summaries",
            headers=get_headers(),
            params={
                "select": "meeting_id,topics,decisions,tags,raw_text,model_used",
                "meeting_id": f"in.({','.join(meeting_ids)})",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            rows = resp.json()
            return {r["meeting_id"]: r for r in rows}
    except Exception as e:
        log(f"Summaries fetch error: {e}")
    return {}


def format_result(meetings: list[dict], summaries: dict[str, dict],
                  mode: str, query: str) -> str:
    """Format search results as markdown."""
    if not meetings:
        return f"**Nenhuma reunião encontrada** para: \"{query}\""

    lines = [
        f"## Reuniões — TLDV\n",
        f"**Modo:** {mode} | **Query:** \"{query}\"\n",
        f"**Encontradas:** {len(meetings)} reuniões\n",
        "---\n",
    ]

    for i, m in enumerate(meetings, 1):
        name = m.get("name") or "Sem título"
        created = m.get("created_at") or ""
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                date_brt = brt(dt).strftime("%d/%m/%Y, %Hh%M BRT")
            except:
                date_brt = created[:10]
        else:
            date_brt = "—"

        summary = summaries.get(m["id"], {})
        topics = summary.get("topics") or []
        decisions = summary.get("decisions") or []
        tags = summary.get("tags") or []
        ctx = m.get("enrichment_context") or {}
        gh_prs = len(ctx.get("github", {}).get("pull_requests") or [])
        tr_cards = len(ctx.get("trello", {}).get("cards") or [])

        lines.append(f"### {i}. {name}\n")
        lines.append(f"**Data:** {date_brt}\n")
        if tags:
            lines.append(f"**Tags:** {', '.join(tags[:5])}\n")
        if topics:
            lines.append(f"> **Topics:** {'; '.join(topics[:2])}\n")
        if decisions:
            lines.append(f"> **Decisões:** {'; '.join(decisions[:2])}\n")
        if gh_prs or tr_cards:
            lines.append(f"> **Enriquecimento:** {gh_prs} PRs, {tr_cards} cards (validação necessária)\n")
        lines.append("---\n")

    lines.append(f"_{len(meetings)} resultados_")
    return "".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="meetings-tldv search")
    parser.add_argument("--query", help="Pergunta livre (infern modo)")
    parser.add_argument("--mode", choices=["temporal", "keyword", "detail"],
                        help="Modo: keyword (default), temporal, detail")
    parser.add_argument("--start", help="Data início (YYYY-MM-DD, modo temporal)")
    parser.add_argument("--end", help="Data fim (YYYY-MM-DD, modo temporal)")
    parser.add_argument("--meeting-id", help="Meeting ID (modo detail)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()

    if not args.query and not args.meeting_id and not (args.mode == "temporal" and args.start):
        log("ERRO: forneça --query, --meeting-id, ou --mode temporal com --start/--end")
        sys.exit(1)

    # Validate env
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        log("ERRO: SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY precisam estar em ~/.openclaw/.env")
        sys.exit(1)

    # Determine mode
    mode = args.mode
    if not mode:
        mode = infer_mode(args.query or "", args.meeting_id)

    log(f"Mode: {mode}")

    # Execute search
    if mode == "temporal":
        if not args.start:
            log("ERRO: --start requerido para modo temporal")
            sys.exit(1)
        end = args.end or datetime.now(BRT).strftime("%Y-%m-%d")
        meetings = search_temporal(args.start, end, args.limit)

    elif mode == "detail":
        if not args.meeting_id:
            log("ERRO: --meeting-id requerido para modo detail")
            sys.exit(1)
        meetings = search_detail(args.meeting_id)

    else:  # keyword
        if not args.query:
            log("ERRO: --query requerido para modo keyword")
            sys.exit(1)
        meetings = search_keyword(args.query, args.limit)

    if not meetings:
        print(f"**Nenhuma reunião encontrada**")
        return

    # Fetch summaries for all meetings
    meeting_ids = [m["id"] for m in meetings]
    summaries = get_summaries(meeting_ids)

    output = format_result(meetings, summaries, mode, args.query or args.meeting_id)
    print(output)


if __name__ == "__main__":
    main()
