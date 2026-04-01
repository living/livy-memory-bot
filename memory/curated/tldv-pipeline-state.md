---
name: tldv-pipeline-state
description: Pipeline de transcrição e sumário de reuniões via API tl;dv — inclui AutoResearch para enriquecimento contínuo
type: pipeline
date: 2026-04-01
project: livy-tldv-jobs
status: ativo_com_bugs
---

# TLDV Pipeline

## Repo

`living/livy-tldv-jobs`
- Branch main
- Branch feature: `feat/autoresearch-tldv-pipeline`
- Path local: `~/.openclaw/workspace/livy-tldv-jobs/`

## Status Operacional

Pipeline ativo com bugs conhecidos. 30 jobs total, 23 enriched (dados de 2026-03-30).

## Cron Jobs

| Job | ID | Schedule (BRT) | Status |
|---|---|---|---|
| `enrich-discover` | `fbad081f-...` | `0 * * * *` | ✅ ok |
| `enrich-process` | `03b18e15-...` | `30 * * * *` | ✅ ok |
| `tldv-archive-videos` | `a1b53e4b-...` | `0 3 * * *` | ✅ ok |
| `livy-meetings-pipeline` | `7c7c6966-...` | `0 0,6,12,18 * * *` | 🔴 **DESAPARECEU — precisa recriar** |

## State Machine do Pipeline

```
PENDING → AZURE_DOWNLOADED → DOWNLOADED → TRANSCRIBED → ENRICHED
    ↓           (source=tldv) ↗ UNARCHIVE_REQUESTED ↘ UNARCHIVE_WAITING
    → DEAD_LETTER (após 3 tentativas)
```

| Fonte | Flow |
|---|---|
| `azure-native` | PENDING → AZURE_DOWNLOADED → DOWNLOADED → TRANSCRIBED → ENRICHED |
| `tldv` (hls_url) | PENDING → UNARCHIVE_REQUESTED → UNARCHIVE_WAITING → DOWNLOADED → TRANSCRIBED → ENRICHED |
| `upload` | PENDING → AZURE_DOWNLOADED → DOWNLOADED → TRANSCRIBED → ENRICHED |

## Variáveis Críticas

| Var | Valor | Status |
|---|---|---|
| `TLDV_JWT_TOKEN` | `eyJhbGci...` | ✅ expira 2026-04-29 (~29 dias) |
| `SUMMARIZER_MODEL` | `openrouter/auto` | ✅ NÃO usar `minimax/minimax-m2.7` (retorna null content) |
| `GITHUB_ORGS` | `living` | ✅ |
| `OPENAI_API_KEY` | Necessária | ✅ para embeddings em `meeting_memories` |

## Bugs Corrigidos (Histórico)

| Bug | Root Cause | Fix |
|---|---|---|
| Blob path com YYYY-MM subdir | `_blob_path_for_meeting()` gerava `meetings/YYYY-MM/{id}.mp4` mas blobs estão em `meetings/{id}.mp4` | Normalizar path no discover, commit `04843aa` |
| GitHub timezone naive | `_fetch_org_context` usava `meeting_date` naive vs API retorna aware | Converter para UTC-aware, commit `d7b6fec` |
| AZURE_DOWNLOADED blob deletado | TTL Azure expira → blob some → 502 em unarchive → loop infinito | `step_download()` verifica `get_blob_properties()` antes; `BlobNotFound` → RuntimeError → caller re-requer unarchive |
| `step_request_unarchive()` transição prematura | `transition()` ANTES do try/except → exceção subia sem ter enfileirado | RuntimeError sobe ANTES da transição; caller insere backoff |
| summarizer 402 credits | `max_tokens=1500` → 402 OpenRouter | Reduzido para 1000, commit `2ae11fd` |
| enrich-process cron timeout | Cron timeout 120s < polling 90min → cron morria antes de processar jobs | timeout 120s→600s, limit 10→1, commit `981db36` |
| discover source=azure-native (errado) | Meetings sem `hls_url` classificados `azure-native` sem ter blob | `source='tldv'` forçado no `_ensure_meeting`; sem `hls_url` → UNARCHIVE_REQUESTED |

## Bugs Abertos

| Bug | Descrição | Impacto | Workaround |
|---|---|---|---|
| gw.tldv.io 502 Bad Gateway | Endpoint de unarchive retorna 502 | Meetings com blobs expirados travam em `UNARCHIVE_REQUESTED` | Usar `video_archiver.py` diretamente |
| TLDV discover sem hls_url | `list_meetings_with_transcript()` não retorna video URLs | Só afeta tldv-source jobs | — |
| Whisper RAM no VPS | srv1405423 tem ~2.3GB livre; `small` model causa OOMKilled após 4-5 reuniões | Transcrição falha | Usar `enrich_no_whisper.py` ou OpenAI Whisper API |
| Trello card sem `trello_card_id` | Schema outdated | Cards não vinculam | — |
| Supabase TLDV stale | Última sync foi 2026-03-20; meetings de 31/03 e 01/04 faltando | Dados desatualizados | — |
| `livy-meetings-pipeline` desaparecido | Cron job não aparece mais na lista | Pipeline de 6h não executa | Recriar cron job |

## AutoResearch Pipeline (Nova Feature)

**Status:** Em implementação — branch `feat/autoresearch-tldv-pipeline`

**Objetivo:** Enriquecer meetings com contexto de múltiplas fontes (memória, GitHub, Trello) automaticamente, criando loop de melhoria contínua.

**Arquitetura:**
```
hook_pre_enrich → transcript_analyzer (participants + topics + context)
                          ↓
              run_all_branches (parallel):
                • memory_search (OpenClaw + claude-mem)
                • github_enricher (PRs do org living)
                • trello_enricher (cards vinculados)
                          ↓
              consolidate → quality_scorer → learning_engine
                                              ↓
                              SE 3+ samples positive + delta ≥ 15%
                              → feature branch + TDD tests + PR via gh CLI
```

**Mudanças architectureais:**
- **pgvector removido** — substituído por OpenClaw subprocess + claude-mem HTTP
- **Estado de learning:** `.learning_state.json` (gitignored)
- **Hypotheses:** `.hypotheses.jsonl` (append-only)
- **Regra de resiliência:** qualquer falha de dependência → retry, NUNCA retorna contexto vazio silenciosamente

**12-step TDD plan:** `docs/superpowers/plans/2026-04-01-autoresearch-tldv-pipeline-plan.md`
**SPEC:** `docs/superpowers/specs/2026-04-01-autoresearch-tldv-pipeline-design.md`

## Cross-references

- [bat-conectabot-observability.md](bat-conectabot-observability.md) — ambos são pipelines com Sev2/problems
- [livy-memory-agent.md](livy-memory-agent.md) — agente monitora este pipeline via cron jobs
- Evolution plan #11: `2026-04-01-tldv-critical-bugs-napkin.md`

---

## Status

**ativo_com_bugs** — 2026-04-01

- ✅ Pipeline operacional (30 jobs, 23 enriched)
- ✅ 7 bugs corrigidos historicamente
- 🔴 6 bugs em aberto (incluindo Supabase stale e cron desaparecido)
- 🔴 `gw.tldv.io` 502 — unarchive travado
- 🟡 AutoResearch em implementação (feat branch)

---

## Decisões

### 2026-03-30 — gw.tldv.io 502 Bad Gateway (Token JWT vs API Issue)

**Decisão:** Investigar o endpoint de unarchive como causa raiz do 502, não o JWT.

**MOTIVO:** A suposição inicial era de token expirado. Análise posterior revelou que o token `TLDV_JWT_TOKEN` expira apenas em 2026-04-29 — ainda válido. O 502 no `gw.tldv.io` indica problema no endpoint de unarchive da API do tl;dv (provavelmente rate limit ou endpoint temporariamente indisponível). Workaround: usar `video_archiver.py` diretamente.

### 2026-03-30 — Whisper via OpenAI API em vez de modelo local

**Decisão:** Não usar `small` model do Whisper local no srv1405423.

**MOTIVO:** VPS tem ~2.3GB RAM livre. Após 4-5 reuniões, o processo é OOMKilled. Solução: usar `enrich_no_whisper.py` (que não transcreve) ou OpenAI Whisper API (cloud, não consome RAM local).

### 2026-04-01 — AutoResearch como Loop de Melhoria Contínua

**Decisão:** Criar pipeline de AutoResearch que busca contexto em memória, GitHub e Trello para cada meeting.

**MOTIVO:** Meetings eram enriquecidos apenas com contexto limitado. O AutoResearch fecha o loop: a cada job, o sistema aprende o que funcionou (quality scorer) e gera hipóteses. Se 3+ samples mostram improvement ≥15%, cria PR automaticamente. Isso permite evolução contínua sem intervenção manual.

**Arquitetura:** Subprocess OpenClaw + claude-mem HTTP em vez de pgvector. Evita dependência de Supabase/Postgres para vetores.

### 2026-04-01 — pgvector REMOVIDO do tldv-jobs

**Decisão:** Substituir pgvector por OpenClaw subprocess + claude-mem HTTP API.

**MOTIVO:** Opgvector exigia Postgres dedicado e complicava o setup. O OpenClaw já tem memory search semantic (built-in) e o claude-mem worker já está rodando. A mudança simplifica a stack e elimina uma dependência de infraestrutura.

---

## Pendências

- [ ] **CRÍTICO:** Recriar `livy-meetings-pipeline` cron job (desapareceu)
- [ ] **CRÍTICO:** Investigar `gw.tldv.io` 502 — usar `video_archiver.py` como workaround
- [ ] Investigar Supabase sync — dados stale desde 2026-03-20
- [ ] Implementar AutoResearch pipeline (branch `feat/autoresearch-tldv-pipeline`)
- [ ] Resolver Whisper RAM — migrar para OpenAI Whisper API ou `enrich_no_whisper.py`
- [ ] Atualizar schema Trello para incluir `trello_card_id`
- [ ] TLDV token renova em 2026-04-29 — preparar renovação

---

## Bugs

### gw.tldv.io 502 Bad Gateway — ABERTO

**Sintoma:** `gw.tldv.io` retorna `502 Bad Gateway` para requests de unarchive.
**Impacto:** Meetings com blobs expirados no Azure travam em `UNARCHIVE_REQUESTED`.
**Workaround:** Usar `video_archiver.py` diretamente.
**Root cause:** Endpoint da API do tl;dv com problema (não é JWT — token válido até 2026-04-29).

### Whisper OOMKilled — ABERTO

**Sintoma:** srv1405423 mata processo Whisper após 4-5 reuniões processadas.
**Root cause:** ~2.3GB RAM livre insuficiente para modelo `small`.
**Workaround:** `enrich_no_whisper.py` ou OpenAI Whisper API.

### Supabase TLDV Stale — ABERTO

**Sintoma:** Última sync foi 2026-03-20; reuniões de 31/03 e 01/04 não aparecem.
**Impacto:** Pipeline pode perder meetings recentes.
**Root cause:** Job de sync não executou ou falhou silenciosamente.
