# Plano: Consolidação Incremental + Reprocessamento QW-2

## Estado Actual

- QW-2 escreve decisões para `memory/vault/decisions/*.md`
- Dedupe via `written_refs.json` (source_ref único)
- Cursors: `.research/qw2/last_seen_{tldv,github,trello}.json`
- Honcho: só 2 conclusões (indexação não activada)

## Problemas

### P1: Honcho é append-only
**Sintoma:** Não há PUT/PATCH/DELETE em `conclusions`.
**Impacto:** Não se pode actualizar uma conclusão existente.

**Solução:** Conclusões com `supersedes` chain:
```
Conclusão B (nova, supersedes A) → content inclui "supersedes: <id_A>"
```
Na leitura, filtrar para mostrar só a mais recente de cada chain.

### P2: Duplicados no vault
**Sintoma:** QW-2 escreveu entries duplicadas (mesma source_ref em dias diferentes).
**Impacto:** Topic files com entries repetidas, poluição.

**Solução:** Consolidação pós-QW-2:
```python
def consolidate_topic_file(path):
    entries = parse_decisions(path)  # extract source_ref + date
    seen = {}
    for entry in entries:
        if entry.source_ref not in seen:
            seen[entry.source_ref] = entry
        # newer entry wins
    rewrite(path, seen.values())
```

### P3: Reprocessamento histórico
**Sintoma:** Mudar router/filter requer replay de dados históricos.
**Impacto:** Decisões antigas ficam com lógica antiga.

**Solução:** Flag `--reset` no run.py:
```
--reset              Limpa cursors + written_refs antes de correr
--reset-cursors      Limpa só cursors (mantém dedupe)
--reset-dedupe       Limpa só dedupe (mantém cursors)
```
Após reset, QW-2 faz replay completo desde `since_days`.

## Arquitectura Proposta

```
QW-2 Pipeline (diário)
│
├── fetch_tldv / fetch_github / fetch_trello
│       ↓
├── router.filter (decisions)
│       ↓
├── writer (dedupe via written_refs.json)
│       ↓
└── consolidate_duplicates()   ← NOVO: pós-write dedupe intra-file
        ↓
└── honcho_index()             ← NOVO: indexar para Honcho
```

## Honcho Integration

```python
def honcho_index(decisions: list[dict]):
    """Index decisions to Honcho conclusions.
    
    Uses content with supersedes chain:
    "DECISION | date | text | source_ref | tags | supersedes: <prev_id>"
    
    On subsequent runs, finds previous conclusion by source_ref
    and includes its ID as supersedes.
    """
    # 1. Search for existing conclusion with same source_ref
    prev = honcho_find_by_source_ref(source_ref)
    
    # 2. Build content with supersedes if found
    content = f"DECISION | {date} | {text} | {source_ref} | tags:{tags}"
    if prev:
        content += f" | supersedes: {prev['id']}"
    
    # 3. POST new conclusion
    honcho_create(content)
```

## Cron Sugerido

```
qw2-daily             seg-sex 07h BRT  → QW-2 (novas decisões)
qw2-consolidate       seg-sex 08h BRT  → Consolidação dedupe + Honcho
qw2-weekly-reprocess  dom 07h BRT      → QW-2 --reset (replay semana)
```

## Comandos

```bash
# Normal (incremental)
python3 vault/qw2/run.py --source all

# Reset completo (reprocessar tudo)
python3 vault/qw2/run.py --source all --reset

# Só consolidação (sem fetch)
python3 vault/qw2/consolidate.py --topic livy-memory-agent
```

## Métricas de Consolidação

| Métrica | Antes | Depois |
|---|---|---|
| Duplicados por source_ref | ~30% | 0% |
| Decisões no Honcho | 2 | N (indexadas) |
| Tempo de query por topic | alto | dedupe reduz |
