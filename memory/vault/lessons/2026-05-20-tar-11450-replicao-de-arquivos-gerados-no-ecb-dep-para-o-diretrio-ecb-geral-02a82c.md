---
type: lesson
date: 2026-05-20
subject: "Trello: [TAR-11450] - Replicação de arquivos gerados no ECB DEP para o diretório ECB-GERAL [B3/Listados]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3listados]
---

## O que aconteceu
Foi proposta a replicação de arquivos gerados no ECB DEP para o diretório ECB-GERAL, permitindo que os times de negócio acessem os arquivos diretamente, sem a necessidade de zipar e enviar por e-mail.

## Decisão / Solução
A configuração do caminho para a replicação dos arquivos foi solicitada para ser feita no adapters.PROD.config, tanto na exportação quanto nas queries, para facilitar o acesso aos dados.

## Lessons
- A replicação direta de arquivos melhora a eficiência no acesso às informações pelos times de negócio.
- A configuração adequada dos caminhos no sistema é crucial para garantir a funcionalidade desejada.

## Source
https://trello.com/c/HT5qQNdm
