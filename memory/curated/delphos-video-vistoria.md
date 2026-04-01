---
name: delphos-video-vistoria
description: Delphos — Vonage/OpenTok video inspection monitoring via MongoDB Atlas, crons midday/daily com entrega Telegram
type: pipeline
date: 2026-04-01
project: livy-delphos-jobs
status: OK
---

# Delphos — Video Vistoria

## Repo

`living/livy-delphos-jobs`
- Path local: `operacional/delphos/`

## Sistema

**Sistema:** Vonage/OpenTok video inspection monitoring
**Destinatário:** Equipe de vistorias — alertas via Telegram
**Banco:** MongoDB Atlas

## Stack

- Python 3
- MongoDB Atlas (`MONGO_URI`, `MONGO_DB` via cron inline)
- Jinja2 (templating)
- Vonage/OpenTok API
- Telegram delivery

## Estrutura do Projeto

```
operacional/delphos/
├── jobs/
│   ├── daily.py          # cron: 0 20 * * * BRT
│   └── midday.py         # cron: 0 12 * * * BRT
└── lib/
    └── (módulos de monitoramento)
```

## Cron Jobs

| Job | ID | Schedule (BRT) | Status | Model |
|---|---|---|---|---|
| `delphos-midday` | `a443d078-...` | `0 12 * * *` | ✅ ok | github-copilot/gpt-5-mini |
| `delphos-daily` | `36988e7a-...` | `0 20 * * *` | ✅ ok | github-copilot/gpt-5-mini |

Run manual:
```bash
python jobs/daily.py [--dry-run]
python jobs/midday.py [--dry-run]
```

## Coleções MongoDB Relevantes

| Coleção | Conteúdo |
|---|---|
| `VonageRoomEvents` | Eventos do pipeline de gravação (ArchiveStartRequested/Confirmed/StopConfirmed/Failed) |
| `VistoriaArquivos` | Arquivos de vídeo gerados (MediaType=1, Url) |
| `Vonage-Audit` | Sessões de videochamada + tempos de archive |
| `Vistorias` | Vistorias em andamento (SessionId) |

## Cross-references

- [bat-conectabot-observability.md](bat-conectabot-observability.md) — ambos são pipelines de observabilidade da Living
- [tldv-pipeline-state.md](tldv-pipeline-state.md) — pipeline de meetings

---

## Status

**OK** — 2026-04-01

- ✅ Cron jobs executando corretamente (delphos-midday + delphos-daily)
- ✅ Sem problemas conhecidos
- ✅ HEARTBEAT tracking delphos jobs

---

## Decisões

### 2026-03-30 — MongoDB Atlas como banco de dados do Delphos

**Decisão:** Usar MongoDB Atlas (`MONGO_URI`, `MONGO_DB`) para armazenar eventos e sessões de video.

**MOTIVO:** O Delphos precisa de um banco para armazenar eventos de gravação (VonageRoomEvents), arquivos de vídeo (VistoriaArquivos), audit trails (Vonage-Audit) e estado das vistorias (Vistorias). MongoDB Atlas é a escolha已有的 — fornecendo persistence e queries flexíveis sem necessidade de schema fixo.

### 2026-03-30 — Cron jobs midday + daily para reports

**Decisão:** Executar reports duas vezes ao dia (12h e 20h BRT).

**MOTIVO:** Equipe de vistorias precisa de visibilidade sobre o pipeline de gravação em tempo útil. Report midday (12h) cobre manhã; report daily (20h) faz fechamento. Jinja2 renderiza templates HTML para entrega via Telegram.

---

## Pendências

Nenhuma pendência registrada.

---

## Bugs

Nenhum bug registrado.

---

## Regras Aprendidas

- `cron_model`: jobs de script simples usam `github-copilot/gpt-5-mini`
- `mongodb_atlas`: credenciais via variáveis de ambiente (`MONGO_URI`, `MONGO_DB`) não hardcoded
