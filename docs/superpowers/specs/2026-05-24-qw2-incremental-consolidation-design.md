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

**Padrão arquitectural:** Eventually consistent — QW-2 escreve para topic files → consolidação deduplica + enricha + adiciona frontmatter → Honcho indexing.

**Topic file format real (existente):**
```markdown
### YYYY-MM-DD — source

> Decision text

- **Source:** source_ref
- **Confidence:** 0.92        ← numeric, 0.0–1.0 (QW-2 original)
- **Tags:** tag1, tag2
```

**Após consolidação** (`consolidate.py`), é adicionado frontmatter:
```markdown
---
name: topic-name
confidence_level: high        ← string: high/medium/low/unverified (fact-check output)
---

### YYYY-MM-DD — source
...
```

**Nota:** Entries existentes (antes da primeira consolidação) não têm frontmatter nem `confidence_level`. Primeira execução do `consolidate.py` adiciona ambos.

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
--reset       Limpa frontmatter confidence_level de todos os topic files
              (força recalculo de fact-check na próxima execução)
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

**Honcho API payload (campos required):**
```python
payload = {
    "content": "DECISION | {date} | {text[:200]} | {source_ref} | confidence:{level} | tags:{tags}[ | supersedes: {id}]",
    "observer_id": "agent-memory-agent",  # quem indexa (fixed)
    "observed_id": source_type,             # tldv | github | trello
}
```
- `observer_id`: quem cria a conclusão — fixo `"agent-memory-agent"`
- `observed_id`: fonte dos dados — extraído do prefixo do `source_ref` (`tldv:`, `github:`, `trello:`)

**Processamento por decision entry:**
1. Extrai `source_ref` e `source_type` do frontmatter
2. Search Honcho: `honcho_search_conclusions(query=source_ref, topK=5, maxDistance=0.1)`
3. Exact match confirmation: `source_ref` presente no `content` E `observed_id` igual ao da entry
4. Se existe: constrói content com `supersedes: <old_id>`
5. Se não existe: constrói content sem supersedes
6. POST para `POST /v3/workspaces/{workspace}/conclusions`

**POST `/v3/workspaces/{workspace_id}/conclusions`** — Required fields (API schema):
```json
{
  "conclusions": [{
    "content": "DECISION | {date} | {text[:200]} | {source_ref} | confidence:{level} | tags:{tags}[ | supersedes: {id}]",
    "observer_id": "agent-memory-agent",   // required by API
    "observed_id": "{source_type}"        // tldv | github | trello — use agent-main for all
  }]
}
```

**GET `/conclusions/list`** — Lista conclusões com filtro por `observed_id` (source_type):
```json
POST /v3/workspaces/{id}/conclusions/list
{"filters": {"observed_id": "tldv"}}  // tldv | github | trello
```
Retorna todas as conclusões para o source type. Buscar no campo `content` por `source_ref:{ref}` para encontrar matches.

**Nota:** `/conclusions/query` semântico **não é usado** — requer `observer_id` + `observed_id` simultaneamente e não escala para dedupe linear. Usa-se `/conclusions/list` + busca em content.

**Content format:**
```
DECISION | {date} | {text[:200]} | {source_ref} | confidence:{level} | tags:{tags}[ | supersedes: {id}]
```

**Flags:**
```
--all              Indexa todos os topic files
--since DATE       Indexa só entries desde DATE (ISO format)
--dry-run          Não faz POST, só mostra o que faria
--honcho-cleanup   Quando activo: DELETE conclusions removidas pelo dedupe (default: off)
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
- Se frontmatter já tem `confidence_level`, skip (não recalcula)
- Usa `score_confidence(official, corroborated, indirect)` → high/medium/low/unverified

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

### 4.1 Módulo Partilhado `vault/qw2/lock.py`

```python
# vault/qw2/lock.py
LOCK_FILE = Path(".research/qw2/.qw2.lock")
LOCK_TTL_SECONDS = 600

def acquire_lock() -> bool:
    """Cria lock file. Retorna True se adquirido, False se lock existe e é fresco."""
    ...

def release_lock() -> None:
    """Remove lock file. Só remove se for o lock actual (mesmo PID)."""
    ...

def is_locked() -> bool:
    """Check se lock existe e não é stale."""
    ...
```

**Importado por:** `run.py`, `consolidate.py`, `honcho_indexer.py`

**Lock file:** `.research/qw2/.qw2.lock` (compartilhado por todos os módulos)
- Criado no início de `run.py`, `consolidate.py` e `honcho_indexer.py`
- TTL: 600s (10 min)
- Se lock existe e é stale (>600s), sobrescreve
- No fim: remove lock file
- Importado de `vault.qw2.lock` (módulo partilhado)

**QW-2 + Consolidação em paralelo:**
- Cron QW-2 às 07h BRT, consolidate às 08h BRT — 1h de gap (suposição: QW-2 termina em < 1h)
- Lock em todos os módulos previne concurrent runs mesmo em runs manuais
- Se QW-2 demorar > 1h, race condition possível — mitigate: lock com TTL

**Nota sobre --reset e consolidate:** após `--reset`, QW-2 re-escreve entries sem `confidence_level`. A próxima consolidação vai recalcular — comportamento desejado. Não há `--reset-consolidate` porque consolidate opera por source_ref e não por timestamp.

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

def test_honcho_dedupe_exact_match():
    """Search por source_ref retorna só exact match (mesmo observed_id)."""
    # source_ref="tldv:abc123" não conflita com "tldv:abc123_extra"
    # Verifica observed_id para confirmar match

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
| R6 | Dedupe regex não captura entries com frontmatter multilinha | 🟢 Baixa | Baixo | Regex com re.DOTALL treat frontmatter como optional group |
| R7 | Honcho conclusions crescem sem cleanup (dedupe só no topic file) | 🟡 Média | Médio | Quando dedupe remove uma entry: (1) buscar `source_ref` da entry removida no Honcho via `/conclusions/list`; (2) POST DELETE `/conclusions/{id}` para cada match. Só executa se `--honcho-cleanup` flag presente (default: off — safety first). |
| R4 | Fact-check lento em topic files grandes | 🟡 Média | Médio | Skip entries com `confidence_level` já calculado |
| R5 | QW-2 demorar > 1h e overlap com consolidate | 🟡 Média | Médio | Lock com TTL 600s + gap de 1h assume QW-2 < 1h |

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
