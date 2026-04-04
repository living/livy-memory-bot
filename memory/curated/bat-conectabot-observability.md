---
name: bat-conectabot-observability
description: BAT/ConectaBot — Pipeline de observabilidade de erros com Azure App Insights, crons intraday e daily, entrega via Telegram e SendGrid
type: observability
date: 2026-04-01
project: livy-bat-jobs
status: ativo
---

# BAT / ConectaBot — Observabilidade de Erros

## Repo

`living/livy-bat-jobs`
- Path local: `operacional/bat/`

## Sistema

**Cliente/Sistema:** ConectaBot — bot de atendimento (BAT PROD)
**Destinatário:** Grupo Telegram `-4642190095` via `@livy_chat_bot`
**E-mail daily:** `bat-brasil@livingnet.com.br` (BCC: `lincoln@livingnet.com.br`)

## Stack

- Python 3 + Azure Application Insights REST API (`x-api-key`)
- Jinja2 + premailer (HTML email)
- Chart.js CDN (intraday sem JS, daily com JS)
- Delivery: Telegram `sendDocument` (.html) + SendGrid v3

## Estrutura do Projeto

```
operacional/bat/
├── jobs/
│   ├── intraday.py        # cron: 0 0,6,12,18 * * * BRT
│   └── daily.py           # cron: 0 20 * * * BRT
├── lib/
│   ├── azure_client.py   # KQL queries
│   ├── aggregator.py      # métricas, alertas
│   ├── renderer.py        # Jinja2 templates
│   └── delivery.py        # Telegram grupo + SendGrid
└── templates/
```

## Cron Jobs

| Job | ID | Schedule (BRT) | Status | Model |
|---|---|---|---|---|
| `bat-intraday` | `e8b741ae-...` | `0 0,6,12,18 * * *` | ✅ ok | github-copilot/gpt-5-mini |
| `bat-daily` | `6efd359a-...` | `0 20 * * *` | ✅ ok | github-copilot/gpt-5-mini |

Both: `--session isolated`, `--agent main`, `--exact`, `--no-deliver`

## Schema — Azure App Insights

- `severityLevel`: 0=verbose, 1=info, 2=warning, 3=error, 4=critical
- `message`: `<Estabelecimento> [API] - erro ao executar requisicao => <url>`

## Alertas — Sev2

| Data | Volume | Causa | Status |
|---|---|---|---|
| 2026-03-31 21:36 BRT | ~2200 erros/ciclo | Webhook do ConectaBot (comportamento esperado) | ⚠️ Monitorando |

**Nota:** Os 2200 Sev2 erros por ciclo de 6h são dados do sistema monitorado (ConectaBot), não falhas nos cron jobs. Os jobs `bat-intraday` e `bat-daily` executam corretamente — o Sev2 reflete erros no ConectaBot, que são o objeto da observabilidade.

## Cross-references

- [tldv-pipeline-state.md](tldv-pipeline-state.md) — ambos são pipelines de jobs com monitoramento
- [livy-memory-agent.md](livy-memory-agent.md) — agente que monitora pipelines via cron jobs

---

## Status

**ativo** — 2026-04-01

- ✅ Cron jobs executando corretamente (bat-intraday + bat-daily)
- ⚠️ Sev2 elevado (~2200 erros/ciclo 6h) no ConectaBot — comportamento do sistema monitorado, não dos jobs
- ✅ Delivery Telegram + SendGrid funcionando
- ✅ HEARTBEAT tracking bat jobs

---

## Decisões

- [2026-04-02] OpenRouter: plano da Living mantém-se (5 credits obrigatórios, 100 USD) — custo será tratado depois [https://tldv.io/meeting/69cbb73298acd80013fa20ce] — via tldv
- [2026-04-01] PR #1: docs: PRD e Spec para erros de dependência customizados [https://github.com/living/livy-bat-jobs/pull/1] — via github
- [2026-04-01] Participar da reunião de arquitetura RetailOud às 10h30 para conhecer diretrizes globais [https://tldv.io/meeting/69b00ec37bc9a50013f30a7c] — via tldv
### 2026-03-30 — Sev2 Elevado é Comportamento Esperado do ConectaBot

**Decisão:** Manter monitoramento sem intervir nos jobs.

**MOTIVO:** Os 2200 erros Sev2 por ciclo de 6h não indicam falha nos cron jobs de observabilidade — refletem erros reais no ConectaBot (webhook disparando requests que falham). Isso é exatamente o que o pipeline de observabilidade deve capturar e reportar. Intervir nos jobs não resolveria os erros no sistema monitorado.

### 2026-03-30 — HTML auto-contido para delivery

**Decisão:** Usar HTML auto-contido (sem PDF, sem Gotenberg) para os relatórios.

**MOTIVO:** O pipeline precisa funcionar sem dependência de serviços externos de conversão. HTML com CSS inline é entregue diretamente via Telegram `sendDocument` e renderiza corretamente no e-mail.

### 2026-03-30 — Imagens base64 inline em vez de URLs externas

**Decisão:** Codificar imagens como base64 inline nos templates HTML.

**MOTIVO:** URLs externas não carregam no contexto do Telegram (preview de HTML) ou no e-mail. Base64 inline garante que as imagens apareçam independentemente de onde o HTML é renderizado.

### 2026-03-30 — Tabela para deps, Chart.js para tendência temporal

**Decisão:** Usar tabela para dependencies (mobile-friendly) e Chart.js para gráficos de tendência temporal.

**MOTIVO:** O relatório diário vai para mobile (Telegram). Tabelas são mais legíveis em telas pequenas. Gráficos de tendência são úteis apenas em contexto desktop/web — Chart.js com CDN é suficiente.

---

## Pendências

- [ ] Avaliar se volume de 2200 Sev2/ciclo justifica ajuste no threshold de alertas
- [ ] Verificar se há padrão nos erros do ConectaBot que possa ser automatizado (auto-remediação)

---

## Bugs

Nenhum bug registrado — o pipeline está operacional. Os Sev2 são dados do sistema monitorado, não falhas do observability pipeline.

---

## Regras Aprendidas

- `sev2_alert`: Sev2 nos dados ≠ Sev2 nos jobs. Alerta indica problema no monitorado, não no monitoramento
- `html_inline`: imagens externas não carregam no Telegram/email — usar base64 inline
- `cron_model`: jobs de script simples usam `github-copilot/gpt-5-mini` (não Sonnet)