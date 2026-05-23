---
type: lesson
source: github
source_ref: "living/RetailAuditProcessFunc/pull/24"
date: 2026-04-08
subject: "PR #24 — corrigindo deploy"
author: unknown
cycle_time: 1m
tags: [CI/CD, GitHub Actions, Azure Functions]

## O que aconteceu
Este PR corrige o deploy ajustando o workflow do GitHub Actions para evitar problemas na publicação da Azure Function. A mudança líquida no diff é a normalização de quebras de linha (CRLF ➜ LF) no arquivo `.github/workflows/master_retailaudit-process-func.yml`.

## Decisão / Solução
O YAML do workflow foi regravado com line endings compatíveis com Linux, reduzindo o risco de falhas em parsing e melhorando a consistência do repositório. O deploy continua usando `Azure/functions-action@v1`, mantendo o pré-processamento do `requirements.txt` para evitar conflitos de dependências.

## Lessons
- Normalizar quebras de linha em arquivos de workflow é crucial para evitar problemas em ambientes Linux.
- A configuração de `.gitattributes` pode prevenir a reintrodução de quebras de linha indesejadas.
- Testar o workflow após alterações é essencial para garantir que não haja falhas na execução.

## Source
https://github.com/living/RetailAuditProcessFunc/pull/24
