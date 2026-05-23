---
type: lesson
source: github
source_ref: "living/insight-funds/pull/5"
date: 2026-05-20
subject: "PR #5 — corrigir app-name do cronjob no workflow de homolog"
author: unknown
cycle_time: 0m
tags: [deploy, workflow, Azure]

## O que aconteceu
Este PR ajusta o workflow de deploy em homologação para apontar para o Azure App Service correto, alterando o nome do app de `dev-insightfunds-cronjob` para `dev-insightfunds-job`. A mudança foi feita para garantir que o step de deploy realize o envio para o recurso correto, evitando inconsistências.

## Decisão / Solução
Foi decidido alterar o nome do app no pipeline de CI/CD para evitar que o deploy fosse realizado em um recurso antigo. A mudança é simples, mas crucial para a consistência do ambiente de homologação.

## Lessons
- Sempre verifique se os nomes dos recursos no pipeline correspondem aos serviços corretos para evitar deploys em locais errados.
- Mantenha os secrets atualizados e renomeados conforme necessário para refletir as alterações nos recursos.
- Teste o workflow após alterações para garantir que o deploy ocorra no App Service esperado.

## Source
https://github.com/living/insight-funds/pull/5
