---
name: openclaw-gateway
description: Gateway daemon do OpenClaw que gerencia canais, cron jobs e roteamento de mensagens
type: infrastructure
date: 2026-03-31
project: openclaw
status: ativo
decision: Gateway crítico para operação do agente de memória — qualquer falha impacta consolidação e watchdog
---

# OpenClaw Gateway

## Comandos Úteis

```bash
openclaw gateway status
openclaw gateway start
openclaw gateway stop
openclaw gateway restart
openclaw channels status
openclaw cron list
```

## Status do Gateway Atual

[executar `openclaw gateway status` para verificar]

## Configuração

- Config: `~/.openclaw/`
- Docs: `/home/lincoln/.openclaw/workspace-livy-memory/docs`
- Mirror: https://docs.openclaw.ai

## Channel

- Bot: `@livy_agentic_memory_bot`
- Grupo: `-5158607302`

## Cross-references

- Relacionado: [livy-memory-agent.md](livy-memory-agent.md) — gateway é a infraestrutura que hospeda o agente de memória
