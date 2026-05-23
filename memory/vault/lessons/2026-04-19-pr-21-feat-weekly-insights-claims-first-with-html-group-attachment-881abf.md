---
type: lesson
source: github
source_ref: "living/livy-memory-bot/pull/21"
date: 2026-04-19
subject: "PR #21 — feat: weekly insights claims-first with HTML group attachment"
author: unknown
cycle_time: 25m
tags: [insights, claims, HTML, Telegram]

## O que aconteceu
Este PR realiza um rework completo do cron `vault-insights-weekly-generate` para ser claims-first, priorizando a extração de insights a partir de `state["claims"]` e implementando um fallback inteligente para markdown blobs quando a janela semanal não está coberta. Além disso, agora entrega dois tipos de relatórios: um pessoal em texto e um grupo em HTML.

## Decisão / Solução
A decisão foi implementar um sistema que prioriza a fonte única de verdade (SSOT) através de claims, com um fallback que considera a cobertura temporal. A entrega dos relatórios foi adaptada para atender a dois públicos distintos, garantindo que a informação seja apresentada de forma adequada e rica em HTML para o grupo.

## Lessons
- Priorizar a fonte única de verdade (SSOT) melhora a robustez e a confiabilidade dos dados extraídos.
- Implementar um fallback inteligente é crucial para garantir a continuidade do serviço mesmo em situações de dados incompletos.
- A segmentação da entrega de relatórios para diferentes públicos (pessoal e grupo) aumenta a eficácia da comunicação.

## Source
https://github.com/living/livy-memory-bot/pull/21
