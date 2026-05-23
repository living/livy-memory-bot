---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/31"
date: 2026-05-20
subject: "PR #31 — Ajuste nos testes de regressão de CSS"
author: unknown
cycle_time: 1m
tags: [CSS, testes, regressão]

## O que aconteceu
O PR ajusta os testes de regressão de CSS do Painel para refletirem mudanças recentes no seletor e nos parâmetros da animação `livepulse`. A alteração líquida é somente em testes (`css-regression.test.ts`), garantindo que a suite valide o comportamento atual do CSS.

## Decisão / Solução
Foi decidido atualizar o seletor testado de `.stat-card .live-dot::before` para `.live-dot::before`, além de ajustar os asserts da animação `livepulse` para novos valores esperados, visando uma adequação visual e UX.

## Lessons
- Sempre que um seletor CSS for alterado, verifique se a mudança impacta outros componentes ou contextos.
- Testes de regressão devem ser atualizados para refletir mudanças no design e comportamento do CSS, garantindo que a validação permaneça precisa.
- É importante validar visualmente as alterações para garantir que a experiência do usuário não seja comprometida.

## Source
https://github.com/living/delphos-svd/pull/31
