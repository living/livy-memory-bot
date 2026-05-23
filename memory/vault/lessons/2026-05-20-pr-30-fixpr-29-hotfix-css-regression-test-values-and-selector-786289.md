---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/30"
date: 2026-05-20
subject: "PR #30 — correção de valores e seletor de teste de regressão CSS"
author: unknown
cycle_time: 1m
tags: [testes, CSS, regressão]

## O que aconteceu
Foi realizado um ajuste nos testes de regressão de CSS do Painel para refletir mudanças recentes no seletor e nos parâmetros da animação `livepulse`. A alteração foi focada apenas nos testes, sem mudanças diretas no código de UI.

## Decisão / Solução
O seletor alvo no teste da animação do indicador “ao vivo” foi atualizado para ser mais permissivo, e as expectativas do keyframe `livepulse` foram ajustadas para refletir uma mudança visual desejada, tornando a animação mais sutil.

## Lessons
- Ao atualizar seletores em testes, é importante considerar o impacto em outros contextos onde o seletor possa ser aplicado.
- Mudanças em animações visuais devem ser validadas para garantir que atendem às intenções de design e acessibilidade.
- Sempre que um teste é ajustado, deve-se confirmar que ele ainda está alinhado com o comportamento esperado do sistema para evitar falsos positivos.

## Source
https://github.com/living/delphos-svd/pull/30
