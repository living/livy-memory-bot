---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/22"
date: 2026-05-14
subject: "PR #22 — feat(sp5.5): Hydra HTTP agendamento — validado E2E contra dev"
author: unknown
cycle_time: 19h 14m
tags: [frontend, observabilidade, agendamento]

## O que aconteceu
Este PR introduz uma nova página de demonstração do fluxo Hydra de agendamento no front-end, permitindo a validação manual e operacional do pipeline de agendamento com visibilidade imediata. Além disso, foram feitas melhorias no `svdFetch` para lidar com respostas HTTP sem corpo e o CORS foi expandido para múltiplas portas de desenvolvimento.

## Decisão / Solução
Foi decidido implementar uma nova página de demonstração que facilita a seleção de vistorias e o envio de propostas, além de adicionar um componente de log para melhor observabilidade. O `svdFetch` foi aprimorado para evitar erros em respostas vazias, e o CORS foi ajustado para permitir um desenvolvimento mais fluido.

## Lessons
- Implementar componentes de observabilidade pode melhorar significativamente a experiência do usuário e a capacidade de depuração.
- É importante garantir que as funções de rede sejam robustas o suficiente para lidar com diferentes tipos de respostas HTTP, evitando falhas inesperadas.
- A expansão do CORS para múltiplas portas de desenvolvimento pode reduzir atritos e facilitar o trabalho em ambientes locais.

## Source
https://github.com/living/delphos-svd/pull/22
