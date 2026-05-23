---
type: lesson
source: github
source_ref: "living/RetailAuditInfraDashboard/pull/56"
date: 2026-05-08
subject: "PR #56 — correção do formato de data enviado ao backend"
author: unknown
cycle_time: 0m
tags: [frontend, backend, integração, refatoração]

## O que aconteceu
Foi realizado um ajuste no formato de datas enviadas ao backend, alterando de `dd/MM/yyyy` para o padrão ISO `yyyy-MM-dd`. Essa mudança visa evitar problemas de parsing no backend e melhorar a integração entre o frontend e o backend.

## Decisão / Solução
A decisão foi implementar a correção do formato de data para garantir que o backend receba as datas no formato esperado. Além disso, foi feito um leve refactor na montagem da query string para simplificar a adição dos parâmetros `startDate` e `endDate`.

## Lessons
- Sempre verifique o formato de dados esperado pelo backend antes de implementar mudanças no frontend para evitar problemas de integração.
- Refatorações leves podem melhorar a legibilidade e a manutenção do código, mesmo em partes que parecem simples.
- Testes abrangentes são essenciais após mudanças de contrato, como o formato de data, para garantir que todas as funcionalidades continuem operando corretamente.

## Source
https://github.com/living/RetailAuditInfraDashboard/pull/56
