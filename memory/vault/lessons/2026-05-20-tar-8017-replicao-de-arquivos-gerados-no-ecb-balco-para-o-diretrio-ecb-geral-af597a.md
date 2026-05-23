---
type: lesson
date: 2026-05-20
subject: "Trello: [TAR-8017] - Replicação de arquivos gerados no ECB Balcão para o diretório ECB-GERAL [B3/Balcão]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3balco]
---

## O que aconteceu
Foi proposta a replicação de arquivos gerados no ECB Balcão para o diretório ECB-GERAL, permitindo que os times de negócio acessem os arquivos diretamente, sem a necessidade de zipar e enviar por e-mail.

## Decisão / Solução
A decisão foi implementar a replicação dos arquivos para facilitar o acesso e utilização das bases em futuros Dashboards. O caminho para o diretório foi configurado no adapters.PROD.config.

## Lessons
- A replicação de arquivos melhora a eficiência do acesso às informações pelos times de negócio.
- A configuração adequada do caminho de diretório é crucial para o sucesso da implementação.

## Source
https://b3sa-listados.atlassian.net/browse/TAR-8017
