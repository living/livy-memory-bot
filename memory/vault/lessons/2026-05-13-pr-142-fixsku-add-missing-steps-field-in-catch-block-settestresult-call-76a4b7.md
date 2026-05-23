---
type: lesson
source: github
source_ref: "living/RetailAuditRulesDashboard/pull/142"
date: 2026-05-13
subject: "PR #142 — fix(sku): add missing steps field in catch block setTestResult call"
author: unknown
cycle_time: 0m
tags: [bugfix, API, UI]

## O que aconteceu
Foi realizado um ajuste no modal de integração com a API de SKU para garantir que o estado de resultado de teste (`testResult`) sempre inclua o campo `steps` no bloco de captura de erro (`catch`). Isso evita inconsistências que poderiam causar falhas na interface do usuário.

## Decisão / Solução
A decisão foi padronizar o formato do objeto `testResult`, assegurando que tanto em casos de sucesso quanto de erro, o campo `steps` esteja presente, mesmo que como uma lista vazia. Essa mudança reduz o risco de erros de renderização na UI.

## Lessons
- Sempre que um objeto de estado for manipulado, assegure-se de que todos os campos necessários estejam presentes para evitar erros de renderização.
- Padronizar a estrutura de dados retornados em diferentes cenários (sucesso e erro) ajuda a manter a consistência e a estabilidade da aplicação.
- Testes de integração devem incluir cenários que geram erros para validar que a UI se comporta corretamente em todas as situações.

## Source
https://github.com/living/RetailAuditRulesDashboard/pull/142
