# HEARTBEAT — Livy Memory Agent

_Atualizado: 2026-04-04 10:03 UTC (07:03 BRT)_

## Jobs Ativos — 18 crons

| Job | Schedule (BRT) | Status | Erros Consec. | Nota |
|---|---|---|---|---|
| **enrich-discover** | hourly :00 | ✅ ok | 0 | |
| **enrich-process** | hourly :30 | ✅ ok | 0 | timeout 600s |
| **bat-intraday** | 0,6,12,18h | ✅ ok | 0 | |
| **bat-daily** | 20h | ✅ ok | 0 | |
| **delphos-midday** | 12h | ✅ ok | 0 | |
| **delphos-daily** | 20h | ✅ ok | 0 | |
| **evo-analyze** | 02h | ✅ ok | 0 | ⬆️ recuperou |
| **evo-watchdog** | 08h | ✅ ok | 0 | |
| **autoresearch** | 21h | ✅ ok | 0 | |
| **tldv-archive-videos** | 03h | ✅ ok | 0 | |
| **memory-agent-sonhar** | 07h | 🔴 error | 3 | telegram delivery |
| **signal-curation** | */2h | 🔴 error | 4 | telegram delivery |
| **openclaw-health** | 30min | 🔴 error | 9 | telegram delivery |
| **memory-agent-feedback-learn** | 20:45 | 🔴 error | 1 | chatId missing |
| **agenda-trello-0930** | 09:30 | 🔴 error | 2 | timeout 120s |
| **agenda-trello-1230** | 12:30 | 🔴 error | 1 | timeout 120s |
| **agenda-trello-1700** | 17h | 🔴 error | 2 | timeout 120s |
| **daily-memory-save** | 17:50 | 🔴 error | 1 | timeout 120s |

**Resumo:** 10/18 ok, 8/18 em error

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

## Mudanças desde Último HEARTBEAT (2026-04-03 07:05 BRT)

| Mudança | Impacto |
|---|---|
| ✅ `evo-analyze` recuperou (estava em error) | Ciclo de evolução voltou a funcionar |
| ✅ OmniRoute upgrade 3.4.4 → 3.4.9 | Claude Code compatibility |
| ✅ Config cleanup: PremiumFirst + minimax removido | Cascade de modelos funcional |
| ✅ VPS → Living network via Tailscale Node Sharing | Acesso à rede interna |
| ✅ Whisper migration: faster-whisper → OmniRoute API | RAM liberada no VPS |
| 🆕 `openclaw-health` cron criado (30min) | 9 erros — delivery config missing |
| 🔴 Telegram delivery regression | 4 crons afetados |

## Memória

| Camada | Estado |
|---|---|
| Observations (claude-mem) | ✅ worker 37777 ativo, 3788 total, 472 novas (24h) |
| Curated (topic files) | ✅ 9 topics, 2 atualizados neste ciclo |
| Signal events | ✅ 60 processados no último ciclo |
| Consolidation | ✅ executando: 2026-04-04 10:03 UTC |

## Última Consolidação

- 472 observations analisadas (24h)
- 8 decisões destiladas para topic files
- `openclaw-gateway.md` e `tldv-pipeline-state.md` atualizados
- Whisper OOM marcado como resolvido
- Volume alto de observations (127 discoveries redundantes) — investigar noise
- Próxima: 2026-04-05 07:00 BRT
