---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/27"
date: 2026-05-19
subject: "PR #27 — Revert 'feat(SP7.4 Bloco 1): Shell pixel-perfect (sidebar + topbar + HydraStatusCard)'"
author: unknown
cycle_time: 0m
tags: [revert, UI, manutenção]

## O que aconteceu
Este PR é um revert do PR anterior que introduziu uma implementação de shell "pixel-perfect". O objetivo é desfazer as mudanças de UI/layout que foram feitas, retornando o projeto ao seu estado anterior.

## Decisão / Solução
Foi decidido reverter a implementação anterior devido a problemas de regressão visual e funcional. O revert é uma abordagem rápida para mitigar impactos negativos causados pela nova feature.

## Lessons
- Sempre valide as mudanças antes de realizar um merge, especialmente em reverts, para evitar reintroduzir bugs antigos.
- Documente claramente os motivos para um revert, pois isso ajuda a equipe a entender as decisões tomadas.
- Realize testes abrangentes após um revert para garantir que o sistema funcione como esperado e que não haja impactos em outras partes do projeto.

## Source
https://github.com/living/delphos-svd/pull/27
