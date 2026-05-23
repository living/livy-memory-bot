---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/25"
date: 2026-05-18
subject: "PR #25 — fix(pr-24): add Features__DemoEndpoints to CI deploy yaml"
author: unknown
cycle_time: 4m
tags: [deploy, CI, features]

## O que aconteceu
Este PR corrige o workflow de deploy do ambiente `develop` para garantir que o container da API seja provisionado com a flag de feature `Features__DemoEndpoints=true`. O workflow anterior estava gerando um manifesto sem essa variável de ambiente, resultando na desabilitação dos endpoints de demo durante os deploys via CI.

## Decisão / Solução
Foi decidida a inclusão da variável de ambiente `Features__DemoEndpoints: "true"` no arquivo `.github/workflows/deploy-develop.yml`, garantindo que o comportamento do deploy via workflow fique consistente com o manifesto de referência.

## Lessons
- Sempre valide as variáveis de ambiente necessárias no manifesto gerado para evitar falhas em produção.
- Mantenha a consistência entre os manifests de referência e os gerados pelo CI para evitar comportamentos inesperados.
- Ao habilitar features em ambientes de desenvolvimento, verifique as políticas de segurança para evitar exposições indevidas.

## Source
https://github.com/living/delphos-svd/pull/25
