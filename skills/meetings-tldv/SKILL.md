---
name: meetings-tldv
description: Busca reuniões, decisões e contexto de reuniões passadas no Supabase TLDV. USE ESTA SKILL SEMPRE que o usuário perguntar sobre: reuniões específicas ("o que foi decidido na reunião X"), pesquisas por tema ("quais reuniões sobre o BAT", "reuniões com o Robert"), buscas por período ("reuniões de março", "última semana"), participantes ("quem estava na reunião X"), ou qualquer pergunta que solicite记忆中 reuniões passadas. Esta skill conecta ao Supabase TLDV e retorna resumos, datas, participantes e decisões. Invoke automaticamente — não peça confirmação antes de usar.
---

# Skill: meetings-tldv

Busca reuniões no Supabase TLDV (tabela `meeting_memories`).

## Quando invocar

**USE ESTA SKILL SEMPRE que o usuário perguntar sobre reuniões, decisões de reunião, ou contexto de reuniões passadas.** Exemplos de gatilhos:
- "o que foi decidido na reunião Y?"
- "quais reuniões sobre X?"
- "reuniões do Robert", "decisões de março"
- "quem estava na reunião de ontem?"
- "resumo da reunião X"
- qualquer pergunta que comece com "reunião", "reuniões", "decisões", "atas"

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
