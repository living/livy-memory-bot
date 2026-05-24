# QW-2 — Consolidação Incremental + Honcho Indexing + Fact-Check

**Data:** 2026-05-24
**Status:** Design approved
**Specs:** Opção A (módulos separados)

---

## 1. Visão Geral

QW-2 extrai decisões de TLDV + GitHub + Trello para topic files em `memory/vault/decisions/`. Este design adiciona três capacidades:

1. **Consolidação incremental** — dedupe intra-file por `source_ref`, correção de duplicados
2. **Honcho indexing** — decisões indexadas como conclusões no Honcho com supersedes chain
3. **Fact-check enrichment** — `confidence_level` calculado via `vault/fact_check.py`

**Padrão arquitectural:** Eventually consistent — QW-2 escreve para topic files → consolidação deduplica + enricha → Honcho indexing.

---

## 2. Arquitectura de Fluxo

```
┌─────────────────────────────────────────────────────────┐
│  CRON: qw2-daily (seg-sex 07h BRT)                     │
│  python vault/qw2/run.py --source all                   │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌──────────▼──────────┐
         │  fetch_tldv         │
         │  fetch_github        │
         │  fetch_trello        │
         └──────────┬──────────┘
                     │
         ┌──────────▼──────────┐
         │  router.filter       │  (confidence < 0.85 → DM)
         └──────────┬──────────┘
                     │
         ┌──────────▼──────────┐
         │  writer              │  (dedupe via written_refs.json)
         └──────────┬──────────┘
                     │
         ┌──────────▼──────────┐
         │  cursor update        │
         └──────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  CRON: qw2-consolidate (seg-sex 08h BRT)                │
│  python vault/qw2/consolidate.py --all                  │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌──────────▼──────────┐
         │  Dedupe intra-file    │  (latest entry wins per source_ref)
         └──────────┬──────────┘
                     │
         ┌──────────▼──────────┐
         │  Fact-check           │  (confidence_level no frontmatter)
         └──────────┬──────────┘
                     │
         ┌──────────▼──────────┐
         │  honcho_indexer       │  (supersedes chain)
         └──────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  CRON: qw2-weekly-reprocess (dom 07h BRT)              │
│  python vault/qw2/run.py --source all --reset           │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Módulos

### 3.1 `vault/qw2/consolidate.py`

**Responsabilidade:** Dedupe intra-file + fact-check enrichment.

**Input:** `memory/vault/decisions/*.md`

**Processamento por topic file:**
1. Parse todas as entries (regex `\n### (\d{4}-\d{2}-\d{2}) — (\w+)\n> (.+?)\n- \*\*Source\*\*: (.+?)\n- \*\*Confidence\*\*: (.+?)\n`)
2. Dedupe: se `source_ref` aparecer mais de uma vez, mantém só a mais recente (por data)
3. Fact-check: para cada entry, invoca `fact_check.py` wrapper → obtém `confidence_level`
4. Reescreve topic file com entries deduplicadas + `confidence_level` no frontmatter

**Output:** Topic files reescritos (ou dry-run).

**Flags:**
```
--all         Consolida todos os topic files (padrão)
--topic NAME  Consolida só o topic file NAME (sem .md)
--dry-run     Não modifica ficheiros, só mostra o que faria
```

**Return dict:**
```python
{
    "processed": int,    # topic files processados
    "entries_total": int,
    "deduped": int,     # entries removidas por dedupe
    "fact_checked": int,
    "written": int,      # ficheiros modificados
    "errors": int,
}
```

### 3.2 `vault/qw2/honcho_indexer.py`

**Responsabilidade:** Indexa decisões para Honcho com supersedes chain (append-only).

**Input:** `memory/vault/decisions/*.md` (só entries com `source_ref` e `confidence_level`)

**Processamento por decision entry:**
1. Extrai `source_ref` do frontmatter
2. Search Honcho por conclusão existente com mesmo `source_ref` (usando `honcho_search_conclusions` com query `source_ref:<ref>`)
3. Se existe: constrói content com `supersedes: <old_id>`
4. Se não existe: constrói content sem supersedes
5. POST para `POST /v3/workspaces/{workspace}/conclusions`

**Content format:**
```
DECISION | {date} | {text[:200]} | {source_ref} | confidence:{level} | tags:{tags}[ | supersedes: {id}]
```

**Flags:**
```
--all         Indexa todos os topic files
--since DATE  Indexa só entries desde DATE (ISO format)
--dry-run     Não faz POST, só mostra o que faria
```

**Return dict:**
```python
{
    "indexed": int,      # conclusões criadas
    "superseded": int,   # conclusões que substituíram outras
    "skipped": int,      # entries sem source_ref ou já no Honcho
    "errors": int,
}
```

### 3.3 `vault/qw2/fact_check.py`

**Responsabilidade:** Wrapper que usa `vault/fact_check.py` para calcular confidence level.

**API:**
```python
def enrich_decision(decision: dict) -> dict:
    """
    Recebe decision dict com 'source' (tldv/github/trello).
    Retorna decision com 'confidence_level' adicionado.

    Usa vault/fact_check.score_confidence():
    - high:  2+ official OR 1 official + 1 corroborated
    - medium: 1 official OR 2+ indirect
    - low:   1 indirect
    - unverified: no evidence
    """
    ...

def enrich_decisions(decisions: list[dict]) -> list[dict]:
    """Batch version of enrich_decision."""
    ...
```

**Notas de implementação:**
- Para TLDV: source="tldv" → `official+=1`
- Para GitHub: source="github" → `official+=1`
- Para Trello: source="trello" → `indirect+=1`
- Se a entry já tem `confidence_level`, skip (não recalcula)

### 3.4 `vault/qw2/run.py` — Flags de Reset

Extensão dos flags existentes:

```
--reset              Hard reset: limpa cursors + written_refs + dedupe refs
--reset-cursors     Limpa só cursors (mantém dedupe)
--reset-dedupe      Limpa só dedupe refs (mantém cursors)
--reset-tldv        Limpa só TLDV cursor + dedupe refs
--reset-github      Limpa só GitHub cursor + dedupe refs
--reset-trello      Limpa só Trello cursor + dedupe refs
```

**Comportamento do --reset:**
1. Apaga `.research/qw2/last_seen_*.json` (todos ou só o especificado)
2. Apaga `.research/qw2/written_refs.json`
3. Apaga `.research/qw2/write_log.jsonl`
4. QW-2 re-processa tudo desde `since_days` (padrão 7)

**Consolidação dedupe corre sempre após reset** (via cron separado).

---

## 4. Locking e Concorrência

**Lock file:** `.research/qw2/.consolidate.lock`
- Criado no início de `consolidate.py` e `honcho_indexer.py`
- TTL: 600s (10 min)
- Se lock existe e é stale (>600s), sobrescreve
- No fim: remove lock file

**QW-2 + Consolidação em paralelo:** evitado pelo lock.

---

## 5. Testes

### `tests/qw2/test_consolidate.py`

```python
def test_dedupe_keeps_latest():
    """Entries com mesmo source_ref: latest date wins."""
    # topic file com 2 entries (mesmo source_ref, datas diferentes)
    # run consolidate
    # assert: só a mais recente permanece

def test_dedupe_keeps_different_source_refs():
    """Entries com source_ref diferente: mantém ambas."""
    ...

def test_fact_check_calls_score_confidence():
    """fact_check.py invoca score_confidence com parâmetros correctos."""
    ...

def test_dry_run_no_files_modified():
    """--dry-run não modifica nenhum ficheiro."""
    ...

def test_lock_prevents_parallel_run():
    """Se lock existe, segunda execução falha."""
    ...
```

### `tests/qw2/test_honcho_indexer.py`

```python
def test_new_decision_posts_without_supersedes():
    """source_ref novo no Honcho: POST sem supersedes."""
    ...

def test_existing_decision_posts_with_supersedes():
    """source_ref já existe: POST com supersedes: <old_id>."""
    ...

def test_dry_run_no_post():
    """--dry-run: nenhum POST feito."""
    ...

def test_content_format():
    """Content segue formato: DECISION | date | text | source_ref | confidence | tags."""
    ...
```

### `tests/qw2/test_reset_flags.py`

```python
def test_reset_clears_all():
    """--reset: apaga 3 cursors + written_refs + write_log."""
    ...

def test_reset_tldv_clears_only_tldv():
    """--reset-tldv: só apaga TLDV cursor, mantém GitHub/Trello."""
    ...

def test_reset_cursors_keeps_dedupe():
    """--reset-cursors:written_refs mantido."""
    ...
```

---

## 6. Riscos e Mitigações

| ID | Risco | Prob | Impacto | Mitigação |
|---|---|---|---|---|
| R1 | Honcho rate limit ao indexar | 🟡 Média | Perde entries | Batch 50, retry 3x, log falhas |
| R2 | Consolidação reescreve e perde entries | 🔴 Baixa | Critical | `--dry-run` obrigatório antes de `--all` |
| R3 | `--reset` limpa dedupe e duplica | 🟡 Média | Alto | Consolidação dedupe corre após reset (cron) |
| R4 | Fact-check lento em topic files grandes | 🟡 Média | Médio | Skip entries com `confidence_level` já calculado |
| R5 | Consolidação || QW-2 escrevem mesmo topic | 🟢 Baixa | Médio | Lock file com TTL 600s |

---

## 7. Quick Wins Identificados

1. **Consolidate dedupe** — remove ~30% entries duplicadas nos topic files existentes
2. **Honcho indexer** — primeiras conclusões no Honcho (vai populando o knowledge base)
3. **Lock file** — segurança mínima para concorrência
4. **--dry-run em tudo** — permite validar antes de executar

---

## 8. Métricas de Sucesso

| Métrica | Antes | Depois |
|---|---|---|
| Duplicados por source_ref | ~30% | 0% |
| Entries com confidence_level | 0 | 100% |
| Conclusões no Honcho | 2 | N (indexadas) |
| Tempo consolidate (10 topic files) | n/a | < 5s |
