---
type: lesson
source: github
source_ref: "living/bot-ai-api/pull/133"
date: 2026-05-22
subject: "PR #133 — correção para caso a AI retorne um telefone inválido"
author: unknown
cycle_time: 0m
tags: [validação, integração, código]

## O que aconteceu
Este PR ajusta o serviço **`N8NBackendService.getUserData`** para melhorar a **validação do telefone** e padronizar o código, além de tornar mais segura a busca de dados na integração com a **Superlógica** e no **Supabase**. A mudança principal foi a implementação de um retorno imediato de lista vazia quando o telefone é inválido ou curto, evitando chamadas desnecessárias a serviços externos.

## Decisão / Solução
Foi decidido implementar uma validação preventiva do parâmetro `phone`, retornando uma lista vazia caso o telefone tenha menos de 8 dígitos. Além disso, foram mantidas as validações de configuração da Superlógica e realizado um trabalho de padronização de estilo e legibilidade do código.

## Lessons
- Implementar validações preventivas pode reduzir chamadas desnecessárias a serviços externos e melhorar a performance do sistema.
- A padronização de estilo e legibilidade do código facilita a manutenção e a colaboração entre os desenvolvedores.
- É importante considerar o impacto de mudanças de comportamento em fluxos existentes, especialmente em integrações com APIs externas.

## Source
https://github.com/living/bot-ai-api/pull/133
