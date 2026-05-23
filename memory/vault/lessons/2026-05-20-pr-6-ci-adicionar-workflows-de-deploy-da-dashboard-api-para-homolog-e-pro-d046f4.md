---
type: lesson
source: github
source_ref: "living/insight-funds/pull/6"
date: 2026-05-20
subject: "PR #6 — ci: adicionar workflows de deploy da dashboard-api para homolog e pro…"
author: unknown
cycle_time: 0m
tags: [ci, deploy, automation]

## O que aconteceu
Este PR adiciona pipelines de deploy via GitHub Actions para o dashboard-api em dois ambientes: Homolog e Production. A ideia é automatizar o build (Node.js) e o deploy para Azure App Service a cada push nas branches de ambiente.

## Decisão / Solução
Foi implementada a automação de CI/CD para garantir consistência no processo de build e deploy, reduzindo o risco de erro humano. Os workflows foram separados por ambiente, com um para homologação e outro para produção, e padronizados para empacotar o código e publicá-lo no Azure.

## Lessons
- Sempre valide a configuração de secrets necessárias antes de realizar o deploy automático.
- Utilize placeholders nos workflows para indicar onde ajustes são necessários, como o nome do App Service de produção.
- Confirme a compatibilidade das versões do Node.js com o ambiente de produção para evitar falhas durante o deploy.

## Source
https://github.com/living/insight-funds/pull/6
