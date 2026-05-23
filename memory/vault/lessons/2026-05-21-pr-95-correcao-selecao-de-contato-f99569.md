---
type: lesson
source: github
source_ref: "living/bot-ai-app/pull/95"
date: 2026-05-21
subject: "PR #95 — correcao selecao de contato"
author: unknown
cycle_time: 0m
tags: [bugfix, ui, chat]

## O que aconteceu
Foi realizado um ajuste no **Chatboard / Panel** para garantir que a lista de mensagens seja sempre atualizada, mesmo quando o webhook/socket retornar uma lista vazia ou `null`. A alteração remove uma condição que impedia a atualização do datasource quando não havia mensagens.

## Decisão / Solução
A decisão foi normalizar a resposta do backend para um array vazio, garantindo que a UI sempre reflita o estado atual, mesmo que não haja mensagens. Essa mudança evita a exibição de mensagens antigas quando o backend retorna 0 mensagens.

## Lessons
- Sempre normalize a resposta do backend para evitar estados inconsistentes na UI.
- Utilize `markForCheck()` em componentes com `ChangeDetectionStrategy.OnPush` para garantir que a interface reflita corretamente o estado atualizado.
- Considere o impacto visual das mudanças na lógica de exibição, especialmente em casos onde a lista pode ficar vazia.

## Source
https://github.com/living/bot-ai-app/pull/95
