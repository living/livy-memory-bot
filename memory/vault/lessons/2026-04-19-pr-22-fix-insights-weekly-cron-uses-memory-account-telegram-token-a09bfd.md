---
type: lesson
source: github
source_ref: "living/livy-memory-bot/pull/22"
date: 2026-04-19
subject: "PR #22 — fix: insights weekly cron uses memory account Telegram token"
author: unknown
cycle_time: 0m
tags: [refatoração, cron, Telegram]

## O que aconteceu
Este PR ajusta o cron de geração semanal de insights para resolver o token do bot do Telegram de forma mais robusta e permitir a configuração dinâmica dos chat IDs via variáveis de ambiente. A mudança foi feita para facilitar operações em ambientes onde o `.env` pode apontar para outro bot, evitando o envio por canais errados.

## Decisão / Solução
Foi implementada uma nova estratégia de resolução do token do Telegram, com precedência explícita para o uso do "memory bot". Adicionou-se um loader do token via OpenClaw e a possibilidade de configurar chat IDs através de variáveis de ambiente.

## Lessons
- Sempre que possível, utilize variáveis de ambiente para configurar tokens e IDs, aumentando a flexibilidade em diferentes ambientes.
- Considere a precedência de configurações ao implementar soluções que dependem de múltiplas fontes de configuração.
- Teste cenários de fallback para garantir que a aplicação se comporte conforme o esperado em diferentes configurações.

## Source
https://github.com/living/livy-memory-bot/pull/22
