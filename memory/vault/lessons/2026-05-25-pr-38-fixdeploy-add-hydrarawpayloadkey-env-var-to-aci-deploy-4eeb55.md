---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/38"
date: 2026-05-25
subject: "PR #38 — fix(deploy): add Hydra__RawPayloadKey env var to ACI deploy"
author: unknown
cycle_time: 17m
tags: [deploy, configuração, GitHub Actions]

## O que aconteceu
Este PR adiciona a configuração da chave `Hydra__RawPayloadKey` nos manifests de deploy, garantindo que o serviço `svd` receba a variável de ambiente necessária via GitHub Actions e template de ACI deploy.

## Decisão / Solução
Foi decidido injetar um novo segredo/config (`HYDRA_RAW_PAYLOAD_KEY`) no runtime, assegurando que tanto o ambiente de desenvolvimento quanto o template de ACI deploy utilizem a mesma configuração.

## Lessons
- Verifique sempre se todos os segredos necessários estão configurados no ambiente antes de realizar o deploy para evitar falhas em runtime.
- Mantenha a paridade entre as configurações em diferentes pipelines para garantir consistência e evitar erros.
- Utilize convenções de nomenclatura claras e consistentes para variáveis de ambiente, facilitando a manutenção e compreensão do código.

## Source
https://github.com/living/delphos-svd/pull/38
