---
type: lesson
source: github
source_ref: "living/RetailAuditRulesDashboard/pull/145"
date: 2026-05-15
subject: "PR #145 — feat(swagger): translate all Swagger API documentation to British Eng…"
author: unknown
cycle_time: 0m
tags: [documentação, internacionalização, API]

## O que aconteceu
Este PR padroniza e traduz para inglês as descrições da documentação Swagger/OpenAPI dos endpoints de Campaigns, Displays, SKUs e Touchpoints. A mudança é puramente documental, sem alteração de regras de negócio ou contratos de API.

## Decisão / Solução
Foi decidido realizar a internacionalização da documentação, substituindo descrições em PT-BR por equivalentes em EN, além de padronizar termos e garantir a sincronia entre a fonte e o artefato gerado.

## Lessons
- A internacionalização da documentação pode melhorar a acessibilidade da API para equipes globais e integrações externas.
- É importante garantir que o processo de geração do `swagger.json` esteja consistente para evitar drift futuro.
- Mudanças documentais não devem impactar a lógica da API, mas devem ser testadas para garantir que a documentação esteja correta.

## Source
https://github.com/living/RetailAuditRulesDashboard/pull/145
