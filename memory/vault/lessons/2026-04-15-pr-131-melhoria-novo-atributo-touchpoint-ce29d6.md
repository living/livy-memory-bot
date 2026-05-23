---
type: lesson
source: github
source_ref: "living/RetailAuditRulesDashboard/pull/131"
date: 2026-04-15
subject: "PR #131 — melhoria: novo atributo touchpoint"
author: unknown
cycle_time: 0m
tags: [melhoria, touchpoint, dashboard]

## O que aconteceu
Este PR ajusta os dados estáticos e seeds do banco do dashboard, reduzindo a lista de países para apenas Argentina, Brasil, Chile, Paraguai e Peru, e incluindo uma nova área de touchpoints chamada “Novas Categorias” com novas classificações. Também foram feitos ajustes de formatação e indentação para padronização.

## Decisão / Solução
Decidiu-se simplificar o cadastro de países para focar apenas nos utilizados no produto, evitando inconsistências. Além disso, foram criadas novas classificações de touchpoints para permitir melhor segmentação e agrupamento no dashboard.

## Lessons
- Sempre que for realizar mudanças significativas em dados estáticos, como listas de países, é importante considerar o impacto em funcionalidades existentes e comunicar as alterações claramente.
- A inclusão de novas categorias e classificações deve ser acompanhada de testes rigorosos para garantir que a interface do usuário e relatórios estejam alinhados com as novas estruturas.
- Padronizar a formatação do código e a estrutura de dados ajuda na legibilidade e manutenção futura, evitando ruídos em diffs.

## Source
https://github.com/living/RetailAuditRulesDashboard/pull/131
