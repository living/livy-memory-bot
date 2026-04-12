# HEARTBEAT — Livy Memory Agent

_Atualizado: 2026-04-12 14:06 UTC (11:06 BRT)_

## Jobs Ativos — 21 crons

| Job | Schedule (BRT) | Status | Erros Consec. | Nota |
|---|---|---|---|---|
| **enrich-discover** | hourly :00 | ✅ ok | 0 | |
| **enrich-process** | hourly :30 | ✅ ok | 0 | timeout 600s |
| **bat-intraday** | 0,6,12,18h | ✅ ok | 0 | |
| **bat-daily** | 20h | ✅ ok | 0 | |
| **delphos-midday** | 12h | ✅ ok | 0 | |
| **delphos-daily** | 20h | ✅ ok | 0 | |
| **evo-analyze** | 02h | ✅ ok | 0 | |
| **evo-watchdog** | 08h | ✅ ok | 0 | |
| **autoresearch** | 21h | ✅ ok | 0 | |
| **tldv-archive-videos** | 03h | ✅ ok | 0 | |
| **vault-crosslink** | 04h | ✅ ok | 0 | 729 edges, 31 PR authors |
| **vault-ingest** | 04:30 | ✅ ok | 0 | |
| **vault-lint** | 05h | ✅ ok | 0 | |
| **memory-agent-sonhar** | 07h | 🔴 error | 3 | telegram delivery |
| **signal-curation** | */2h | 🔴 error | 4 | telegram delivery |
| **openclaw-health** | 30min | 🔴 error | 9 | telegram delivery |
| **memory-agent-feedback-learn** | 20:45 | 🔴 error | 1 | chatId missing |
| **agenda-trello-0930** | 09:30 | 🔴 error | 2 | timeout 120s |
| **agenda-trello-1230** | 12:30 | 🔴 error | 1 | timeout 120s |
| **agenda-trello-1700** | 17h | 🔴 error | 2 | timeout 120s |
| **daily-memory-save** | 17:50 | 🔴 error | 1 | timeout 120s |

**Resumo:** 13/21 ok, 8/21 em error

## Alertas

| Severidade | Alerta | Ação Necessária |
|---|---|---|
| 🔴 CRÍTICO | Telegram delivery quebrado para 3+ crons | Corrigir outbound config no gateway |
| 🔴 | `openclaw-health` — 9 erros consecutivos desde criação | Mesmo root cause: "Outbound not configured for channel: telegram" |
| 🟡 | `agenda-trello-*` — 3 jobs timing out (120s) | Aumentar timeout para 300s |
| 🟡 | `daily-memory-save` timeout | Aumentar timeout |
| 🟡 | `memory-agent-feedback-learn` — chatId missing | Adicionar `to: "7426291192"` no delivery |
| ⚠️ | OmniRoute sem OPENAI_API_KEY — whisper/rerank/moderation bloqueados | Configurar via dashboard |
| ⚠️ | 9 decisões TLDV sem topic_ref | Curadoria manual pendente |

## Mudanças desde Último HEARTBEAT (2026-04-04 07:03 BRT)

| Mudança | Impacto |
|---|---|
| ✅ `vault-crosslink` cron ativo — 729 edges, 31 PR authors | Pipeline de crosslink operacional |
| ✅ `vault-ingest` + `vault-lint` crons ativos | Ingest pipeline completo |
| ✅ PR author resolution via `github-login-map.yaml` | Esteves (top contributor, 16 PRs), 31 autores resolvidos |
| ✅ Crosslink resolver + builder fixados (R3 review) | Merge sem conflitos |
| ✅ Bot account PR filtering implementado | Evita auto-referência nas arestas |
| ✅ Batch cache + identity resolution | Pipeline stages completados |
| 🆕 `vault-crosslink`, `vault-ingest`, `vault-lint` crons adicionados | 3 novos jobs na tabela |
| ✅ Pipeline wiring stages 1-5 implementados | Crosslink pipeline merged |
| 🔴 Telegram delivery ainda quebrado | 4 crons afetados (semanas em error) |

## Memória

| Camada | Estado |
|---|---|
| Observations (claude-mem) | ✅ worker 37777 ativo, 50 obs session, 212k tokens work |
| Curated (topic files) | ✅ 9 topics, 2 atualizados neste ciclo |
| Signal events | ✅ 60 processados no último ciclo |
| Consolidation | ✅ executando: 2026-04-04 10:03 UTC |

## Última Consolidação

- 50 observations na sessão atual (Apr 12)
- Decisões Apr 12: crosslink resolver fix, PR author identity resolution, bot filtering, pipeline wiring stages
- 729 crosslink edges gerados (vault-crosslink OK)
- Próxima consolidação: 2026-04-13 07:00 BRT
