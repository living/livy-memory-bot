---
name: meetings-tldv
description: Busca reuniões, decisões e contexto de reuniões passadas no Supabase TLDV. USE ESTA SKILL SEMPRE que o usuário perguntar sobre: reuniões específicas ("o que foi decidido na reunião X"), pesquisas por tema ("quais reuniões sobre o BAT", "reuniões com o Robert"), buscas por período ("reuniões de março", "última semana"), participantes ("quem estava na reunião X"), ou qualquer pergunta que solicite reuniões passadas. Esta skill conecta ao Supabase TLDV e retorna resumos, datas, topics, decisões, PRs e cards enriquecidos. Invoke automaticamente — não peça confirmação antes de usar.
---

# Skill: meetings-tldv

Busca reuniões no Supabase TLDV (tabela **`meetings`** + **`summaries`**, projeto `fbnelbwsjfjnkiexxtom`).

## Fontes de dados

| Tabela | Conteúdo |
|--------|----------|
| `meetings` | name, created_at, enriched_at, source, enrichment_context (PRs GitHub + Cards Trello) |
| `summaries` | meeting_id, topics, decisions, tags, raw_text, model_used |
| `meeting_participants` | meeting_id → participants (name, email) — **pode estar vazio** |

## IMPORTANTE — Limitação atual

- `meeting_participants` frequentemente vazio (não está a ser populado pela pipeline)
- `enrichment_context` (PRs/Cards) retorna últimos 7 dias, não contexto específico da reunião — validar relevância
- `summaries.topics` e `summaries.decisions` podem estar vazios mesmo com `enriched_at` preenchido

## Quando invocar

**USE ESTA SKILL SEMPRE que o usuário perguntar sobre reuniões, decisões de reunião, ou contexto de reuniões passadas.** Exemplos:
- "o que foi decidido na reunião Y?"
- "quais reuniões sobre X?"
- "reuniões do Robert", "decisões de março"
- "quem estava na reunião de ontem?"
- "resumo da reunião X"
- qualquer pergunta com "reunião", "reuniões", "decisões", "atas"

## Como funciona

1. Recebe pergunta livre
2. Inferência de modo: `temporal` | `keyword` | `detail`
3. Query REST API no Supabase: `meetings` → `summaries`
4. Formata output em markdown

## Modos de busca

### keyword (default)
Pergunta sem janela temporal específica. Busca por ILIKE no `name` da reunião.

```
GET /rest/v1/meetings?select=id,name,created_at,enrichment_context&enriched_at=not.is.null&name=ilike.*{query}*&order=created_at.desc&limit=5
+ GET /rest/v1/summaries?meeting_id=eq.{id}
```

### temporal
Pergunta menciona janela de tempo ("última semana", "março").
```
GET /rest/v1/meetings?select=id,name,created_at,enrichment_context&enriched_at=not.is.null&created_at=gte.{start}&created_at=lte.{end}&order=created_at.desc&limit=10
```

### detail
meeting_id ou nome exato.
```
GET /rest/v1/meetings?select=id,name,created_at,enrichment_context&enriched_at=not.is.null&id=eq.{meeting_id}
+ GET /rest/v1/summaries?meeting_id=eq.{meeting_id}
```

## Endpoints

- **URL base**: `https://fbnelbwsjfjnkiexxtom.supabase.co/rest/v1`
- **Auth header**: `apikey: $SUPABASE_SERVICE_ROLE_KEY` + `Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY`
- Variáveis em `~/.openclaw/.env` (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`)

## Dependências

- `SUPABASE_SERVICE_ROLE_KEY` em `~/.openclaw/.env`
- Apenas `requests` (sem `openai` para este modo — usa ILIKE, não vector search)

## Feedback

Se o usuário corrigir ou validar uma reunião/topics/decisions → gravar em `memory/meetings-tldv-feedback-log.jsonl` com formato:
```
{"meeting_id": "...", "feedback": "...", "timestamp": "..."}
```

Este feedback alimenta o `learned-rules.md` e pode circular para a pipeline do tldv (issue em `living/livy-tldv-jobs`).

## Output

```
## Reuniões — TLDV

**Modo:** keyword | **Query:** "Status"
**Encontradas:** 3 reuniões

---
### 1. Status — 31/03/2026, 17h44 BRT
**Tags:** delfos, sinistro, whatsapp
> **Topics:** Integração WhatsApp para gestão de sinistros; Levantamento casos de uso Delfos
> **Decisões:** Foco em funcionalidades essenciais para demo; Delfos como camada de integração
> **Enriquecimento:** 12 PRs, 15 cards Trello (validação necessária)
> [ver no TLDV →](https://tldv.io/meetings/69cc323d38b6a8001405708a)

---
_3 resultados_
```
