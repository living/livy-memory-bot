# Skill: meetings-tldv

Busca reuniões no Supabase TLDV (tabela `meeting_memories`).

## Quando invocar

O agente invoca esta skill quando o usuário pergunta sobre:
- Reuniões, decisões de reunião, contexto de reuniões
- "quais reuniões sobre X", "o que foi decidido na reunião Y"
- "reuniões do Robert", "decisões de março"

## Como funciona

1. Recebe pergunta livre
2. Inferência: `temporal` | `semantic` | `detail`
3. Extrai janela temporal via `query_recency_ts_from_text()`
4. Executa query no Supabase TLDV
5. Hybrid scoring: recência + similaridade
6. Retorna formato estilo memory search (markdown)

## Modos

### temporal
Pergunta menciona janela de tempo ("última semana", "março").
Usa `created_at` range query via Supabase REST API.

### semantic
Pergunta sobre tema/decisão sem janela específica.
Embed via OpenAI `text-embedding-3-small`, cosine similarity no Supabase.
Se RPC `match_summary_vectors` não existir → ILIKE fallback.

### detail
Pergunta menciona `meeting_id` ou título exato.
Busca registro único por `meeting_id`.

## Fallback em cascata

1. Semantic tenta RPC `match_summary_vectors`
2. Se RPC falhar → ILIKE fallback
3. Se `OPENAI_API_KEY` ausente → ILIKE fallback
4. Se zero resultados → tenta threshold -0.1

## Dependências

- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` em `~/.openclaw/.env`
- `OPENAI_API_KEY` em `~/.openclaw/.env` (para semantic mode)
- Python packages: `supabase`, `openai`

## Uso direto

```bash
# Busca por tema (semantic)
python3 skills/meetings-tldv/search.py --query "decisões sobre o BAT"

# Testa inferência (dry-run, sem API calls)
python3 skills/meetings-tldv/search.py --dry-run --query "últimas reuniões"

# Busca por ID (detail)
python3 skills/meetings-tldv/search.py --mode detail --meeting-id abc123

# Busca por período (temporal)
python3 skills/meetings-tldv/search.py --mode temporal --start 2026-03-01 --end 2026-03-31
```

## Output

Formato markdown compatível com Telegram:

```
## Reuniões — TLDV

**Modo:** semantic | **Query:** "decisões sobre o BAT"
**Encontradas:** 3 reuniões

---
### 1. Reunião Robert — BAT Monitoring
**Score:** 0.87 | **Data:** 28/03/2026, 14h BRT
> Resumo: Robert pediu mudança no schedule...

---
_3 resultados_
```
