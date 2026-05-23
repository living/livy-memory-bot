---
type: lesson
source: github
source_ref: "living/svr-delphos/pull/21"
date: 2026-04-09
subject: "PR #21 — fix: resetar ConferenciaEncerrada no endpoint Token da API (#20)"
author: unknown
cycle_time: 1m
tags: [refatoração, observabilidade, resiliência]

## O que aconteceu
Este PR melhora o fluxo de gravação de archives da Vonage/OpenTok e a observabilidade do sistema, reduzindo falsos negativos e duplicidades, além de corrigir a persistência idempotente no `VonageAudit`.

## Decisão / Solução
As operações de start e stop foram migradas para um modelo assíncrono com retries e timeouts, melhorando a confiabilidade. O logging foi centralizado e as exceções no Sentry foram reduzidas, focando apenas em falhas após tentativas esgotadas.

## Lessons
- Implementar sempre um modelo assíncrono com retries e timeouts para operações críticas, garantindo maior resiliência.
- Centralizar o logging para facilitar a análise de falhas e reduzir o ruído em sistemas de monitoramento.
- Validar mudanças de contrato em APIs para evitar impactos em consumidores que dependem de comportamentos anteriores.

## Source
https://github.com/living/svr-delphos/pull/21
