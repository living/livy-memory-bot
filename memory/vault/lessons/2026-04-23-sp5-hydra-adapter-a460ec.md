---
type: lesson
date: 2026-04-23
subject: "Trello: SP5: Hydra Adapter [Delphos/SVD]"
effort: Not specified
pr_refs: [none]
tags: [trello, delphossvd]
---

## O que aconteceu
O cartão representa a implementação do adaptador bidirecional Hydra, que envolve a recepção de comandos via Azure Service Bus, processamento com lógica de domínio e emissão de eventos, além da adição de webhooks.

## Decisão / Solução
A solução envolve a criação de um `BackgroundService` para consumir comandos e despachar para um processador de comandos, além da implementação de novos webhooks e eventos relacionados ao sistema Hydra.

## Lessons
- A integração com o Azure Service Bus permite uma comunicação assíncrona eficiente entre os componentes do sistema.
- A utilização de handlers para processar comandos facilita a manutenção e a escalabilidade da lógica de negócios.

## Source
https://trello.com/c/PBrGql0E
