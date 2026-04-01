---
name: openclaw-gateway
description: Gateway daemon do OpenClaw que gerencia canais, cron jobs, agentes e roteamento de mensagens — infraestrutura crítica para operação dos agentes Living
type: infrastructure
date: 2026-04-01
project: openclaw
status: ativo
---

# OpenClaw Gateway

## Comandos Úteis

```bash
openclaw gateway status          # status do daemon
openclaw gateway start           # iniciar
openclaw gateway stop            # parar
openclaw gateway restart         # reiniciar
openclaw channels status         # canais Telegram
openclaw cron list               # lista de cron jobs
openclaw status                  # health probes
openclaw agents list             # agentes registrados
```

## Status Atual (2026-04-01 11:57 UTC)

| Item | Valor |
|---|---|
| Service | systemd (enabled) |
| PID | 1466238 |
| Bind | loopback (127.0.0.1) — **não exposto externamente** |
| Port | 18789 |
| Dashboard | http://127.0.0.1:18789/ |
| RPC probe | ok |
| Plugin | claude-mem v1.0.0 (worker 127.0.0.1:37777) |

**⚠️ Gateway é loopback-only.** Apenas clientes locais podem conectar. Tailscale Funnel é usado para exposição pública quando necessário (ver decisão de hardening).

## Canais Telegram Configurados

| Channel | Bot | Status | Modo |
|---|---|---|---|
| `memory` (Livy Memory) | `@livy_agentic_memory_bot` | ✅ running | polling |
| `livy-deep` (Livy Deep) | — | ✅ running | polling |
| `livy-chat` (Livy Chat) | — | ✅ running | polling |
| `neo` (Neo) | — | ✅ running | polling |
| `iot-sandbox` (IoT Sandbox) | — | ✅ running | polling |
| Telegram default | — | ⛔ stopped | — |

**Canais pertencentes a este workspace:** `memory` (grupo `-5158607302`)

## Cron Jobs Ativos

| Job | Schedule | Agent | Status |
|---|---|---|---|
| `autoresearch-hourly` | 0 * * * * BRT | memory-agent | ✅ ok |
| `memory-agent-feedback` | 45 * * * * | memory-agent | ✅ ok |
| `memory-agent-sonhar` | 0 7 * * * BRT | memory-agent | 🔴 **error** |
| `memory-watchdog` | a cada 4h | memory-agent | (via cron) |
| `dream-memory-consolidation` | 0 7 * * * BRT | memory-agent | (via cron) |
| `enrich-discover` | 0 * * * * | main | ✅ ok |
| `enrich-process` | 30 * * * * | main | ✅ ok |
| `evo-analyze` | 0 2 * * * BRT | livy-evo | ✅ ok |
| `evo-watchdog` | 0 8 * * * BRT | livy-evo | ✅ ok |
| `bat-intraday` | 0 0,6,12,18 * * * | main | ✅ ok |
| `delphos-midday` | 0 12 * * * | main | ✅ ok |
| `tldv-archive-videos` | 0 3 * * * BRT | — | ✅ ok |

**ALERTA:** `memory-agent-sonhar` em estado `error` — investigar.

## Configuração

| Item | Path |
|---|---|
| Config CLI | `~/.openclaw/openclaw.json` |
| Config service | `~/.openclaw/openclaw.json` |
| Service file | `~/.config/systemd/user/openclaw-gateway.service` |
| Docs local | `/home/lincoln/.openclaw/workspace-livy-memory/docs` |
| Docs online | https://docs.openclaw.ai |

## Arquitetura de Agentes

| Agente | Workspace | Agent ID real | Notas |
|---|---|---|---|
| Livy Memory | `workspace-livy-memory` | `memory-agent` | ⚠️ não usar `livy-memory` |
| Livy Evo | `workspace-evo` | `livy-evo` | — |
| Livy Deep | (root) | `main` | — |

**Delegação:** `openclaw agent -m "<mensagem>" --agent <agent-id>` é o mecanismo de delegação via CLI (descoberto em #1751). Agentes são isolados por workspace — não há comunicação agent-to-agent direta.

## Skills

Skills de workspace em `workspace/skills/` têm precedência sobre skills bundled. SKILL.md com YAML frontmatter é o formato padrão. Configurações por skill (API keys, endpoints) podem ser sobrescritas via `openclaw.json`.

## Cross-references

- [livy-memory-agent.md](livy-memory-agent.md) — gateway hospeda o agente de memória
- [claude-mem-observations.md](claude-mem-observations.md) — plugin que observa tool calls

---

## Status

**ativo** — 2026-04-01

- ✅ Gateway rodando em systemd (PID 1466238)
- ✅ Plugin claude-mem carregado (v1.0.0)
- ✅ 5 canais Telegram configurados + rodando
- ✅ 12 cron jobs ativos (1 em error: `memory-agent-sonhar`)
- ✅ Hardening de segurança aplicado (2026-03-04)
- ✅ Canal `memory` (`-5158607302`) configurado e funcional

---

## Decisões

### 2026-03-04 — Hardening de segurança do Gateway

**Decisão:** Aplicar hardening de segurança no OpenClaw Gateway — elevated tools, allowFrom para Telegram, webchat rules.

**MOTIVO:** O gateway expunha superfície de ataque desnecessária. O hardening incluiu:
- `tools.elevated.allowFrom.telegram: tg:7426291192` — apenas o Telegram ID de Lincoln pode usar elevated
- Webchat com rule correta (`webchat: ["webchat:lincoln"]`)
- 0 CRITICALs após hardening

**Resultado:** Confirmação de que o ID Telegram de Lincoln (`7426291192`) estava correto.

### 2026-03-04 — Gateway exposto via Tailscale Funnel (GitHub Webhooks)

**Decisão:** Usar Tailscale Funnel para expor o gateway publicamente sem abrir firewall.

**MOTIVO:** Arquitetura anterior usava n8n como middleware para GitHub webhooks. Substituir por Funnel elimina o middleware, simplificando o pipeline para GitHub App → Funnel → OpenClaw `/hooks/agent`. Tailscale já estava instalado no VPS — não exigiu nova ferramenta.

### 2026-03-02 — Habilitar plugin openclaw-mem0

**Decisão:** Adicionar `openclaw-mem0` ao `plugins.allow` no `openclaw.json`.

**MOTIVO:** Aviso de segurança `plugins.allow is empty` indicando que plugins não estavam explicitamente permitidos. Adicionar à allowlist suprime o aviso e explicita confiança no plugin mem0.

### 2026-04-01 — Gateway loopback-only (bind=127.0.0.1)

**Decisão:** Manter gateway em loopback, não expô-lo diretamente à rede.

**MOTIVO:** Segurança por default — o gateway gerencia credenciais e canais. Exposição pública por Tailscale Funnel é controlada e explícita, não implícita.

---

## Pendências

- [ ] Investigar `memory-agent-sonhar` em estado **error** — cron job das 07h BRT com falha
- [x] Verificar se chat ID `-5158607302` é o grupo correto para o canal `memory` — ✅ CONFIRMADO: Living Memory Observation, ativo
- [ ] Simlink `~/.claude/skills/meetings-tldv` pendente (referenciado em #1661)

---

## Bugs

Nenhum bug registrado para o gateway.

---

## Regras Aprendidas

- `gateway_loopback`: manter bind em 127.0.0.1 por segurança
- `agents_list`: sempre verificar agent ID com `openclaw agents list` antes de delegar
- `cron_error`: jobs em error precisam de investigação antes de ignorar
- `funnel_vs_firewall`: usar Tailscale Funnel em vez de abrir portas de firewall
