---
type: lesson
source: github
source_ref: "living/svr-delphos/pull/20"
date: 2026-04-09
subject: "PR #20 — fix: resetar ConferenciaEncerrada no endpoint Token da API"
author: unknown
cycle_time: 44m
tags: [API, correção, usabilidade]

## O que aconteceu
Este PR ajusta o endpoint **`Token(string code)`** para reabrir automaticamente a conferência quando a vistoria ainda não está finalizada, mas aparece com **`ConferenciaEncerrada = true`**. A mudança evita que o fluxo fique “travado” por um estado inconsistente e registra um evento no Sentry para rastreabilidade.

## Decisão / Solução
Foi decidido que, ao solicitar o token, se a vistoria não estiver finalizada e a conferência estiver marcada como encerrada, o sistema irá desmarcar o encerramento e persistir essa correção. Essa abordagem reduz casos de suporte e falhas no fluxo do usuário por estados inválidos.

## Lessons
- Sempre valide estados críticos antes de permitir ações que dependem deles, para evitar inconsistências.
- Implementar logs em sistemas de produção é essencial para rastreabilidade e diagnóstico de problemas.
- Considere os efeitos colaterais de endpoints que normalmente são considerados como leitura, especialmente em sistemas que exigem consistência de estado.

## Source
https://github.com/living/svr-delphos/pull/20
