---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/24"
date: 2026-05-18
subject: "PR #24 — polish SP7.3 demo page (accents, TODO, 404 UX)"
author: unknown
cycle_time: 1h 30m
tags: [UI, integração, documentação]

## O que aconteceu
Este PR ajusta o ambiente de integração para habilitar endpoints de demonstração via feature flag, melhora a documentação do fluxo de demo e refina a interface do usuário e os testes do front-end.

## Decisão / Solução
Foi decidido habilitar a feature flag para endpoints de demonstração no ambiente de integração, permitindo a validação dos fluxos sem expor endpoints em produção. Além disso, foram feitas melhorias na UI e na documentação para garantir clareza na experiência do usuário.

## Lessons
- Sempre documente as mudanças de configuração em produção para evitar mal-entendidos sobre o comportamento do sistema.
- Utilize mensagens de erro amigáveis para melhorar a experiência do usuário, especialmente em cenários de falha.
- Realize testes manuais e automatizados para validar alterações significativas na UI e garantir que a funcionalidade esteja intacta.

## Source
https://github.com/living/delphos-svd/pull/24
