---
type: lesson
date: 2026-05-25
subject: "Trello: [TAR-8017] - Replicação de arquivos gerados no ECB Balcão para o diretório ECB-GERAL [B3/Balcão]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3balco]
---

## O que aconteceu
Foi discutida a replicação de arquivos gerados no ECB Balcão para o diretório ECB-GERAL, permitindo que os times de negócio acessem os arquivos diretamente, sem a necessidade de zipar e enviar por e-mail.

## Decisão / Solução
A decisão foi implementar a replicação dos arquivos no caminho especificado: \nascorapp\Transfer\ECB-GERAL\Output\BALCAO\YYYYMMDD, tanto na configuração de exportação quanto nas consultas.

## Lessons
- A replicação direta de arquivos facilita o acesso e a utilização dos dados pelos times de negócio.
- A configuração adequada dos caminhos de diretório é crucial para garantir que os processos funcionem corretamente.

## Source
https://b3sa-listados.atlassian.net/browse/TAR-8017
