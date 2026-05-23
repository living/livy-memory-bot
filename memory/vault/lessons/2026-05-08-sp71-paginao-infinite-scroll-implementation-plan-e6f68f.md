---
type: lesson
date: 2026-05-08
subject: "Trello: SP7.1 — Paginação + Infinite Scroll Implementation Plan [Delphos/SVD]"
effort: Not specified
pr_refs: [none]
tags: [trello, delphossvd]
---

## O que aconteceu
Este cartão representa o plano de implementação de paginação e scroll infinito, substituindo o fetch completo no lado do cliente por uma abordagem baseada em offset no backend.

## Decisão / Solução
A arquitetura foi definida para que o backend retorne um objeto `VistoriasPageResponse`, contendo `Items`, `Total`, `Skip` e `Take`. O frontend utilizará `useInfiniteQuery` com `getNextPageParam` baseado em offset. Além disso, o componente `PhaseCounterBar` agora receberá as contagens diretamente do endpoint `/resumo`, em vez de calcular esses valores localmente.

## Lessons
- A transição para uma abordagem de paginação e scroll infinito melhora a eficiência do carregamento de dados no frontend.
- A centralização da lógica de contagem no backend reduz a complexidade do frontend e melhora a consistência dos dados.

## Source
https://trello.com/c/jcJjIHkQ
