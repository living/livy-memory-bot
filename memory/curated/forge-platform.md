---
name: forge-platform
description: Living Forge Platform — ESP32 IoT simulator web com canvas visual, wokwi-react-flow, deploy via Render, Supabase Auth
type: platform
date: 2026-04-01
project: livy-forge-platform
status: em_progresso
---

# Forge Platform

## Repo

`living/livy-forge-platform`
- **Deploy frontend:** https://living-forge.onrender.com
- **API:** `srv1405423:3030` — systemd user service `forge-api` (auto-start)
- **API pública:** `https://openclaw.tail7185ba.ts.net:10000` (Tailscale Funnel → localhost:3030)

## Contexto

Plataforma visual IoT — canvas interativo para montar e simular circuitos ESP32 antes do hardware. Permite que engenheiros testem lógica e componentes antes de deploy físico.

## Stack

| Camada | Tecnologia |
|---|---|
| **Frontend** | React 18 + TypeScript + `@xyflow/react@^12` + `@wokwi/elements@^1.9.2` + Zustand 4 + Tailwind + Vite |
| **Backend** | Node.js/Fastify + WebSocket (GPIO simulation) |
| **Auth** | Google OAuth `@livingnet.com.br` via Supabase |
| **Banco** | Supabase Forge (`kwxakmbkdgwjyrtijjwd`, sa-east-1) |
| **Gráfico** | uPlot v1.6.32 (imperativo) |

## Arquitetura

```
Frontend (React + @xyflow/react)
    ↓ WebSocket
forge-api (Node.js/Fastify, srv1405423:3030)
    ↓
Supabase (Auth + Banco)
    ↓
Tailscale Funnel → pública
```

## M1a — Componentes Implementados

| Componente | Descrição |
|---|---|
| `EspC3Node` | ESP32 DevKit V1 (GPIO8/9/GND) |
| `LedNode` | LED com estado digital |
| `ButtonNode` | Botão com pull-down |
| `ResistorNode`, `GndNode`, `BreadboardNode` | Componentes básicos |
| `InspectorPanel` | Painel de inspeção |
| `SidePanel` | Painel lateral |
| `circuitAnalyzer.ts` | BFS topologia do circuito |

## Issues e PRs

| Issue | Status | Descrição |
|---|---|---|
| #3 — Boiler Demo (Robert) | ✅ PR #4 merged | NTC sensor, relay, uPlot 24h |
| #5 — Janela configurável | ✅ PR #6 awaiting merge | Múltiplas janelas, modo 24h |

## Decisões Técnicas

- [2026-04-01] PR #4: feat(boiler): simulacao de boiler IoT com NTC, Relay e grafico uPlot (#3) [https://github.com/living/livy-forge-platform/pull/4] — via github
- [2026-04-01] PR #6: feat(boiler): janela de operação configurável — múltiplas janelas + modo 24h (#5) [https://github.com/living/livy-forge-platform/pull/6] — via github
- [2026-04-01] PR #10: feat(backend): multi-usuário — project_members + endpoints de memberships (#7) [https://github.com/living/livy-forge-platform/pull/10] — via github
- [2026-04-01] PR #11: feat(frontend): multi-usuário — share modal + realtime sync (#8) [https://github.com/living/livy-forge-platform/pull/11] — via github
- [2026-04-01] PR #12: fix(frontend): BoilerStatusCard labels dinâmicos por janelas configuradas (#9) [https://github.com/living/livy-forge-platform/pull/12] — via github
| Decisão | Escolha | MOTIVO |
|---|---|---|
| Tag ESP32 | `wokwi-esp32-devkit-v1` | Simula exatamente o hardware usado |
| Breadboard | SVG nativo | Sem dependência externa |
| Estado digital | `gpioState: Record<number, 0\|1>` | Simples, serializável |
| Gráfico | uPlot v1.6.32 | Performance em tempo real |

## Credenciais

- **⚠️ NÃO usar `~/.openclaw/.env`** — credenciais Forge em `operacional/forge/.env`
- **user_id Lincoln:** `f4c65183-1e0d-4568-8056-8527f5470a4f`
- **Conta Supabase:** `forge@livingnet.com.br`

## Deploy

| Componente | Plataforma | Auto-deploy |
|---|---|---|
| Frontend | Render Static Site | ✅ main branch |
| forge-api | srv1405423 systemd | ✅ sim |

**⚠️ Tailscale Funnel:** só portas 443, 8443, 10000 são expostas.

## Cross-references

- [livy-memory-agent.md](livy-memory-agent.md) — memória agêntica referencia Forge
- [openclaw-gateway.md](openclaw-gateway.md) — gateway pode ser componente da plataforma
- Repo `living/livy-forge-platform`

---

## Status

**em_progresso** — 2026-04-01

- ✅ Frontend em deploy (living-forge.onrender.com)
- ✅ API rodando (srv1405423:3030, systemd)
- ✅ M1a implementado (ESP32 + componentes básicos)
- ✅ 2 PRs merged/awaiting merge
- ⚠️ Arquivo forge-platform.md não evoluído no último ciclo (timeout — obs #1813)

---

## Decisões

### 2026-03-11 — Plataforma visual IoT (Forge v2)

**Decisão:** Evoluir o IoT Sandbox de TDD por terminal para plataforma visual com canvas interativo.

**MOTIVO:** Testar circuitos fisicamente é demorado e oneroso. Um canvas visual com simulação ESP32 permite que engenheiros iterem rapidamente antes de pasar para hardware. A plataforma multi-projeto com canvas 2D clicável e observabilidade em tempo real é significativamente mais produtiva.

### 2026-03-11 — Stack React + @xyflow/react + @wokwi/elements

**Decisão:** Usar React com @xyflow/react (anteriormente react-flow) para canvas de nodes e @wokwi/elements para componentes ESP32.

**MOTIVO:** @xyflow/react é a biblioteca mais madura para canvas de nodes em React. @wokwi/elements fornece componentes ESP32 pré-construídos (LEDs, botões, resistores) que funcionam no browser via WebGL/WASM. Juntos cobrem o canvas de wiring e os componentes simulados.

### 2026-03-11 — Supabase para Auth e Banco

**Decisão:** Usar Supabase (Google OAuth restrito a `@livingnet.com.br`) para autenticação e persistência.

**MOTIVO:** Forge é plataforma interna da Living. Supabase com Google Auth restrito a `@livingnet.com.br` garante que apenas membros da equipe acessem. Supabase também fornece banco PostgreSQL para estado de projetos sem precisar de serviço separado.

### 2026-03-11 — Fastify + WebSocket para API

**Decisão:** Backend em Node.js com Fastify e WebSocket para GPIO simulation em tempo real.

**MOTIVO:** Fastify é mais performático que Express para APIs modernas. WebSocket é essencial para update em tempo real do estado dos pinos GPIO — o frontend precisa saber quando um botão é pressionado ou LED muda de estado instantaneamente.

### 2026-03-13 — Tailscale Funnel para expor API

**Decisão:** Expor forge-api via Tailscale Funnel em vez de abrir firewall.

**MOTIVO:** O srv1405423 já tem Tailscale instalado. Funnel permite expor localhost:3030 como HTTPS público sem configurar firewall. Funcionalidade built-in do Tailscale — simples e seguro.

---

## Pendências

- [ ] Merge PR #6 (Janela configurável)
- [ ] Evoluir forge-platform.md (arquivo com timeout no último ciclo — obs #1813)
- [ ] Avaliar integração com Telegram via OpenClaw ( Forge ↔ Telegram)
- [ ] Estudar flux.ai e Arduino Cloud como inspiração (sugerido por Esteves)

---

## Bugs

Nenhum bug registrado.

---

## Regras Aprendidas

- `forge_credentials`: nunca usar `~/.openclaw/.env` — Forge tem `.env` próprio em `operacional/forge/`
- `wokwi_esp32_tag`: usar tag `wokwi-esp32-devkit-v1` (não `esp32-c3-devkitm-1` — não existe)
- `supabase_upsert`: upsert requer UNIQUE constraint, não só índice
- `Tailscale_Funnel_ports`: só 443, 8443, 10000 são expostas — não 3030 diretamente