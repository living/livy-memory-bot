---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/37"
date: 2026-05-25
subject: "PR #37 — feat(SP8-B): Hydra Event Feed — telemetria unificada + webhook inbound"
author: unknown
cycle_time: 2d 19h
tags: [telemetria, webhook, segurança, idempotência]

## O que aconteceu
Este PR implementa o Hydra Event Feed unificado com telemetria persistida, introduzindo um webhook inbound que garante idempotência, redação de PII e armazenamento opcional de payload criptografado. O endpoint do painel foi refatorado para retornar uma nova lista de eventos.

## Decisão / Solução
Foi decidido criar uma tabela específica para registrar eventos de telemetria, garantindo uma fonte única de verdade. A implementação de idempotência no webhook inbound e a segurança no armazenamento de dados sensíveis foram priorizadas. O frontend foi atualizado para consumir a nova API, melhorando a experiência do usuário.

## Lessons
- Sempre que implementar um novo endpoint, considere a possibilidade de breaking changes e comunique as alterações aos consumidores da API.
- A segurança deve ser uma prioridade; sempre que possível, implemente práticas como a comparação de tokens em tempo constante para evitar ataques de timing.
- Testes automatizados são essenciais para garantir que novas funcionalidades não quebrem o comportamento esperado, especialmente em sistemas que lidam com dados sensíveis.

## Source
https://github.com/living/delphos-svd/pull/37
