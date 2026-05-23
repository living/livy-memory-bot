---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/9"
date: 2026-04-23
subject: "PR #9 — feat(sp5): Hydra Adapter — bidirectional commands + session-events webhook"
author: unknown
cycle_time: 2d 16h
tags: [feature, integration, webhook]

## O que aconteceu
Este PR implementa um adaptador bidirecional Hydra no SVD, permitindo que o sistema consuma comandos via Azure Service Bus e publique eventos de volta para a Hydra. Além disso, foi adicionado um webhook para eventos de sessão do Vonage.

## Decisão / Solução
Foi decidido criar um `AzureServiceBusCommandReceiver` para escutar e processar comandos, além de um `IHydraEventPublisher` que agora inclui o `tenantId` nos eventos publicados. O webhook para eventos de sessão do Vonage foi implementado para gerenciar conexões de participantes.

## Lessons
- Sempre que adicionar novos contratos de comando, documente claramente os nomes esperados para evitar erros de dead-letter.
- Considere o impacto de mudanças em interfaces públicas, como a exigência de novos parâmetros, para garantir que todas as integrações sejam atualizadas.
- Valide a segurança de webhooks antes de mover para produção, garantindo que autenticações e validações estejam ativas.

## Source
https://github.com/living/delphos-svd/pull/9
