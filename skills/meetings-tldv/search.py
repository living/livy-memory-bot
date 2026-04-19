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
    python3 skills/meetings-tldv/search.py --dry-run --query "última semana"
"""

import argparse
import os
import re
import sys
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


def _month_map() -> dict[str, int]:
    return {
        "janeiro": 1,
        "fevereiro": 2,
        "março": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
    }


def query_recency_window_from_text(question: str) -> tuple[str, str] | None:
    """Extrai janela temporal (start,end) em YYYY-MM-DD a partir de pergunta livre."""
    q = (question or "").lower()
    now = datetime.now(BRT)

    if "última semana" in q:
        start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")
        return start, end

    if "este mês" in q:
        start = datetime(now.year, now.month, 1, tzinfo=BRT).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")
        return start, end

    months = _month_map()

    between = re.search(r"entre\s+([a-zç]+)\s+e\s+([a-zç]+)", q)
    if between:
        m1 = months.get(between.group(1))
        m2 = months.get(between.group(2))
        if m1 and m2:
            year1 = now.year if m1 <= now.month else now.year - 1
            year2 = now.year if m2 <= now.month else now.year - 1
            start = datetime(year1, m1, 1, tzinfo=BRT).strftime("%Y-%m-%d")
            end = datetime(year2, m2, 28, tzinfo=BRT).strftime("%Y-%m-%d")
            return start, end

    for month_name, month_num in months.items():
        if month_name in q:
            year = now.year if month_num <= now.month else now.year - 1
            start = datetime(year, month_num, 1, tzinfo=BRT).strftime("%Y-%m-%d")
            end = datetime(year, month_num, 28, tzinfo=BRT).strftime("%Y-%m-%d")
            return start, end

    return None


def query_recency_ts_from_text(question: str) -> float | None:
    """Retorna timestamp (epoch seconds) da data inicial inferida, para compatibilidade com testes."""
    window = query_recency_window_from_text(question)
    if not window:
        return None
    start, _ = window
    dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=BRT)
    return dt.timestamp()


def infer_mode(question: str, meeting_id: str | None = None) -> str:
    """Analisa a pergunta e decide o modo de busca: detail|temporal|semantic."""
    q = (question or "").lower()

    if meeting_id:
        return "detail"

    if (
        "detail da reunião" in q
        or "detalhe da reunião" in q
        or "summarize meeting" in q
        or re.search(r"\bmeeting\s+[a-z0-9_-]+", q)
    ):
        return "detail"

    if query_recency_window_from_text(q):
        return "temporal"

    return "semantic"


def hybrid_score(now: datetime, similarity: float | None, created_ts: float | None) -> float:
    """Score híbrido simples (similaridade + recência) para priorização."""
    sim_score = 0.5 if similarity is None else max(0.0, min(1.0, float(similarity)))

    if created_ts is None:
        recency_score = 0.5
    else:
        age_days = max(0.0, (now.timestamp() - float(created_ts)) / 86400.0)
        recency_score = max(0.0, 1.0 - (age_days / 30.0))

    return (0.7 * sim_score) + (0.3 * recency_score)


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
                "limit": str(min(max(1, limit), MAX_LIMIT)),
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
        params = [
            ("select", "id,name,created_at,enriched_at,source,enrichment_context"),
            ("enriched_at", "not.is.null"),
            ("created_at", f"gte.{start}T00:00:00Z"),
            ("created_at", f"lte.{end}T23:59:59Z"),
            ("order", "created_at.desc"),
            ("limit", str(min(max(1, limit), MAX_LIMIT))),
        ]
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/meetings",
            headers=get_headers(),
            params=params,
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


def format_result(
    meetings: list[dict],
    summaries_or_mode,
    mode_or_query,
    query_or_threshold=None,
) -> str:
    """Format search results as markdown.

    Compatibilidade:
    - API atual: format_result(meetings, summaries_dict, mode, query)
    - API esperada em tests: format_result(rows, mode, query, min_similarity)
    """
    if isinstance(summaries_or_mode, dict):
        summaries = summaries_or_mode
        mode = str(mode_or_query)
        query = str(query_or_threshold) if query_or_threshold is not None else ""
    else:
        summaries = {}
        mode = str(summaries_or_mode)
        query = str(mode_or_query)

    if not meetings:
        return f"**Nenhuma reunião encontrada** para: \"{query}\""

    lines = [
        "## Reuniões — TLDV\n",
        f"**Modo:** {mode} | **Query:** \"{query}\"\n",
        f"**Encontradas:** {len(meetings)} reuniões\n",
        "---\n",
    ]

    for i, m in enumerate(meetings, 1):
        meeting_id = m.get("id") or m.get("meeting_id") or str(i)
        name = m.get("name") or m.get("meeting_name") or "Sem título"
        created = m.get("created_at") or m.get("date_str") or ""

        if created:
            try:
                dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                date_brt = brt(dt).strftime("%d/%m/%Y, %Hh%M BRT")
            except Exception:
                date_brt = str(created)[:10]
        else:
            date_brt = "—"

        summary = summaries.get(meeting_id, {}) if summaries else {}
        topics = summary.get("topics") or []
        decisions = summary.get("decisions") or []
        tags = summary.get("tags") or []

        ctx = m.get("enrichment_context") or {}
        gh_prs = len((ctx.get("github", {}) or {}).get("pull_requests") or [])
        tr_cards = len((ctx.get("trello", {}) or {}).get("cards") or [])

        participants = m.get("participants") or []
        content = m.get("content")
        similarity = m.get("similarity")

        lines.append(f"### {i}. {name}\n")
        lines.append(f"**Data:** {date_brt}\n")

        if similarity is not None:
            try:
                lines.append(f"**Similarity:** {float(similarity):.2f}\n")
            except Exception:
                lines.append(f"**Similarity:** {similarity}\n")

        if participants:
            lines.append(f"**Participantes:** {', '.join(participants)}\n")

        if tags:
            lines.append(f"**Tags:** {', '.join(tags[:5])}\n")
        if topics:
            lines.append(f"> **Topics:** {'; '.join(topics[:2])}\n")
        if decisions:
            lines.append(f"> **Decisões:** {'; '.join(decisions[:2])}\n")
        if content:
            lines.append(f"> **Resumo:** {str(content)[:220]}\n")
        if gh_prs or tr_cards:
            lines.append(f"> **Enriquecimento:** {gh_prs} PRs, {tr_cards} cards (validação necessária)\n")

        lines.append("---\n")

    lines.append(f"_{len(meetings)} resultados_")
    return "".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="meetings-tldv search")
    parser.add_argument("--query", help="Pergunta livre (inferir modo)")
    parser.add_argument(
        "--mode",
        choices=["temporal", "keyword", "semantic", "detail"],
        help="Modo: semantic/keyword, temporal, detail",
    )
    parser.add_argument("--start", help="Data início (YYYY-MM-DD, modo temporal)")
    parser.add_argument("--end", help="Data fim (YYYY-MM-DD, modo temporal)")
    parser.add_argument("--meeting-id", help="Meeting ID (modo detail)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--dry-run", action="store_true", help="Só inferir e mostrar parâmetros")
    args = parser.parse_args()

    if not args.query and not args.meeting_id and not (args.mode == "temporal" and args.start):
        log("ERRO: forneça --query, --meeting-id, ou --mode temporal com --start/--end")
        sys.exit(1)

    mode = args.mode or infer_mode(args.query or "", args.meeting_id)

    # Inferência de janela temporal quando vier por linguagem natural
    inferred_window = query_recency_window_from_text(args.query or "") if mode == "temporal" else None
    start = args.start
    end = args.end
    if mode == "temporal" and inferred_window:
        start = start or inferred_window[0]
        end = end or inferred_window[1]

    if args.dry_run:
        print(
            f"DRY RUN mode={mode} query={args.query!r} meeting_id={args.meeting_id!r} "
            f"start={start!r} end={end!r} limit={args.limit}"
        )
        return

    # Validate env only for live runs
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        log("ERRO: SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY precisam estar em ~/.openclaw/.env")
        sys.exit(1)

    log(f"Mode: {mode}")

    # Execute search
    if mode == "temporal":
        if not start:
            log("ERRO: --start requerido para modo temporal (ou query temporal como 'última semana')")
            sys.exit(1)
        final_end = end or datetime.now(BRT).strftime("%Y-%m-%d")
        meetings = search_temporal(start, final_end, args.limit)

    elif mode == "detail":
        if not args.meeting_id:
            log("ERRO: --meeting-id requerido para modo detail")
            sys.exit(1)
        meetings = search_detail(args.meeting_id)

    else:  # semantic/keyword
        if not args.query:
            log("ERRO: --query requerido para modo semantic/keyword")
            sys.exit(1)
        meetings = search_keyword(args.query, args.limit)

    if not meetings:
        print("**Nenhuma reunião encontrada**")
        return

    meeting_ids = [m.get("id") for m in meetings if m.get("id")]
    summaries = get_summaries(meeting_ids)

    output = format_result(meetings, summaries, mode, args.query or args.meeting_id)
    print(output)


if __name__ == "__main__":
    main()
