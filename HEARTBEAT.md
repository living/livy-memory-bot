# HEARTBEAT — Livy Memory Agent

_Atualizado: 2026-04-18 15:18 UTC (12:18 BRT)_

## Jobs Ativos — 17 crons

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
| **tldv-archive-videos** | 03h | ✅ ok | 0 | |
| **vault-crosslink** | 01h | ✅ ok | 0 | 729 edges, 31 PR authors |
| **vault-ingest** | 10h,14h,20h | ✅ ok | 0 | delivery telegram ativo |
| **vault-lint** | 21h | ✅ ok | 0 | delivery telegram ativo |
| **vault-insights-weekly-validate** | seg 06:30 | ✅ ok | 0 | sintaxe + imports |
| **vault-insights-weekly-generate** | seg 07h | ✅ ok | 0 | geração + envio resumo |
| **agenda-trello-0930** | 09:30 | 🔴 error | 3 | billing provider/model |
| **agenda-trello-1230** | 12:30 | 🔴 error | 2 | billing provider/model |
| **agenda-trello-1700** | 17h | 🔴 error | 3 | billing provider/model |

**Resumo:** 14/17 ok, 3/17 em error

## Alertas

| Severidade | Alerta | Ação Necessária |
|---|---|---|
| 🔴 CRÍTICO | `agenda-trello-*` com falha recorrente por billing (neo/anthropic) | Trocar model para provider ativo (ex: fastest/copoly) ou reativar billing |
| 🟡 | Jobs legados desabilitados (openclaw-health, sonhar, signal-curation, daily-memory-save) | Manter desabilitados ou replanejar com configuração nova |
| 🟢 | Vault insights semanal operacional | Manter monitoramento das segundas 06:30/07:00 |

## Mudanças desde Último HEARTBEAT

| Mudança | Impacto |
|---|---|
| ✅ PR #13 mergeada (`bccbef7`) — 6 quick wins de insights | Pipeline de insights incorporado ao master |
| ✅ PR #14 mergeada (`a8f3626`) — envio real Telegram no `envia_resumo.py` | Resumo semanal automatizado com dedupe |
| ✅ PR #15 mergeada (`6ea8005`) — fallback `TELEGRAM_TOKEN` | Compatibilidade com ambiente de produção atual |
| 🆕 Cron `vault-insights-weekly-validate` | Validação preventiva semanal antes da geração |
| 🆕 Cron `vault-insights-weekly-generate` | Geração + envio semanal para `7426291192` |
| ✅ Smoke test manual dos 2 crons novos | Ambos com `lastRunStatus=ok`, `lastDeliveryStatus=delivered` |

## Memória

| Camada | Estado |
|---|---|
| Observations (claude-mem) | ✅ worker 37777 ativo |
| Curated (topic files) | ✅ atualizado com Vault Insights + PRs #13/#14/#15 |
| Operational (crons) | ✅ 2 novos jobs operacionais adicionados |

## Incident Playbook

### `agenda-trello-*` — billing error em neo/anthropic (recorrente)

**Sintoma:** `FallbackSummaryError: All models failed (2): anthropic/claude-sonnet-4-6: Provider anthropic has billing issue`

**Verificar primeiro:**
```bash
gh api graphql -f query='{ marketplacePurchases(first:5) { nodes { plan { name } } } }'
```

**Mitigação imediata:**
1. Listar job IDs: `openclaw cron list | grep agenda-trello`
2. Trocar model de `fastest`/`github-copilot/gpt-5-mini` para provider ativo:
   ```bash
   # Exemplo: trocar model nos 3 jobs
   openclaw cron update <job-id> --model omniroute/fastest
   ```
3. Alternativas testadas em produção: `omniroute/PremiumFirst`, `zai/glm-5.1`

**Root cause provável:** provider anthropic sem créditos/billing ativo na conta neo.

**Resolução definitiva:** reativar billing em claude.ai/admin ou migrar para provider sem billing (omniroute/zai).

**Jobs afetados:**
- `agenda-trello-0930` (id: `24514a66`)
- `agenda-trello-1230` (id: `1a0e180b`)
- `agenda-trello-1700` (id: `23bc1aba`)

---

## Última Consolidação

- Sessão de implementação/documentação: 2026-04-18
- Alterações aplicadas: merge PRs #13, #14, #15 + criação de 2 crons
- Próxima consolidação: 2026-04-19 07:00 BRT
