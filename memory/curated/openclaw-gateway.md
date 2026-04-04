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

## Status Atual (2026-04-04 10:03 UTC)

| Item | Valor |
|---|---|
| Service | systemd (enabled) |
| Bind | loopback (127.0.0.1) — **não exposto externamente** |
| Port | 18789 |
| Dashboard | http://127.0.0.1:18789/ |
| RPC probe | ok |
| Plugin | claude-mem v1.0.0 (worker 127.0.0.1:37777) |
| OmniRoute | v3.4.9 — localhost:20128 (PremiumFirst combo) |
| Tailscale | VPS + Living network (ts-dmz-2.potoroo-ladon.ts.net) |

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

## Cron Jobs Ativos (18 jobs — 2026-04-04)

| Job | Schedule | Agent | Status | Notas |
|---|---|---|---|---|
| `enrich-discover` | hourly :00 | main | ✅ ok | |
| `enrich-process` | hourly :30 | main | ✅ ok | timeout 600s |
| `bat-intraday` | 0,6,12,18h BRT | main | ✅ ok | |
| `bat-daily` | 20h BRT | main | ✅ ok | |
| `delphos-midday` | 12h BRT | main | ✅ ok | |
| `delphos-daily` | 20h BRT | main | ✅ ok | |
| `evo-analyze` | 02h BRT | livy-evo | ✅ ok | recuperou |
| `evo-watchdog` | 08h BRT | livy-evo | ✅ ok | |
| `autoresearch` | 21h BRT | memory-agent | ✅ ok | |
| `tldv-archive-videos` | 03h BRT | — | ✅ ok | |
| `memory-agent-sonhar` | 07h BRT | memory-agent | 🔴 error (3x) | delivery telegram |
| `signal-curation` | */2h | memory-agent | 🔴 error (4x) | delivery telegram |
| `openclaw-health` | 30min | — | 🔴 error (9x) | delivery telegram |
| `memory-agent-feedback-learn` | 20:45 BRT | memory-agent | 🔴 error (1x) | chatId missing |
| `agenda-trello-0930` | 09:30 BRT | — | 🔴 error (2x) | timeout 120s |
| `agenda-trello-1230` | 12:30 BRT | — | 🔴 error (1x) | timeout 120s |
| `agenda-trello-1700` | 17h BRT | — | 🔴 error (2x) | timeout 120s |
| `daily-memory-save` | 17:50 BRT | — | 🔴 error (1x) | timeout 120s |

**ALERTA SISTÊMICO:** 8 de 18 jobs em error. Dois root causes:
1. **Telegram delivery**: jobs com `delivery.mode: "announce"` + `channel: "telegram"` falham com "Outbound not configured for channel: telegram"
2. **Timeout 120s**: agenda-trello e daily-memory-save timeout (iCal fetch + API lento)

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

**ativo** — 2026-04-04

- ✅ Gateway rodando em systemd
- ✅ Plugin claude-mem carregado (v1.0.0)
- ✅ OmniRoute v3.4.9 operacional (PremiumFirst combo)
- ✅ 5 canais Telegram configurados + rodando
- 🔴 18 cron jobs, 8 em error (delivery telegram + timeouts)
- ✅ Hardening de segurança aplicado (2026-03-04)
- ✅ VPS conectado a Living network via Tailscale Node Sharing

---

## Decisões

### 2026-04-03 — OpenClaw Config Cleanup: PremiumFirst + minimax-portal removido

**Decisão:** Padronizar `omniroute/PremiumFirst` como modelo para todos os agentes (exceto neo). Remover plugin `minimax-portal-auth`.

**MOTIVO:** Agentes estavam quebrando com "Context overflow: prompt too large for the model" — cascata de fallback encontrava modelos inexistentes (`minimax-m2.7`). Fix: limpar fallbacks, remover plugin stale, usar PremiumFirst (combo com 7 modelos em cascade).

### 2026-04-03 — OmniRoute upgrade 3.4.4 → 3.4.9 (Claude Code compatibility)

**Decisão:** Upgrade OmniRoute para v3.4.9 com Claude Code como proxy via `ANTHROPIC_BASE_URL=http://localhost:20128/v1`.

**MOTIVO:** PRs #921 (CC-compatible streaming), #937 (Claude OAuth), #943 (GitHub Copilot combo fix). Cascade com 7 modelos funcional: antigravity/claude-opus-4-6-thinking → cc/claude-opus-4-6 → glm/glm-5.1 → etc.

### 2026-04-03 — VPS conectado a Living network via Tailscale Node Sharing

**Decisão:** Aceitar invite Node Sharing de `luiz@` na tailnet `potoroo-ladon.ts.net`.

**MOTIVO:** Nó `ts-dmz-2` (100.92.23.115) dá acesso à rede Living. VPS mantém conexão original à tailnet pessoal (4 nós) + nova rota Living.

### 2026-04-03 — openclaw-health cron criado

**Decisão:** Novo cron job `openclaw-health` com intervalo de 30min rodando `openclaw-health.sh --all`.

**MOTIVO:** Monitoramento proativo do gateway. **Status: 🔴 9 erros consecutivos** — delivery para Telegram não configurado. O job em si roda OK, mas a entrega falha.

- [2026-04-01] Confirmar com Paulo a exclusão do email do Rafael para liberar custo e criar novo email (Livin) [https://tldv.io/meeting/69b160414270ef0013141f26] — via tldv

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

- [ ] **CRÍTICO:** Corrigir Telegram outbound — 4 crons falhando com "Outbound not configured for channel: telegram"
- [ ] **ALTO:** Aumentar timeout dos agenda-trello jobs (120s → 300s) — 3 jobs timing out
- [ ] Investigar `memory-agent-sonhar` delivery error (3 consecutivos)
- [ ] Corrigir `memory-agent-feedback-learn` — chatId missing no delivery
- [x] Verificar se chat ID `-5158607302` é o grupo correto para o canal `memory` — ✅ CONFIRMADO
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