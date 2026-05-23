---
type: lesson
source: github
source_ref: "living/insight-funds/pull/11"
date: 2026-05-21
subject: "PR #11 — fix: salvar blob_url e local_path (blobName) em downloaded_files"
author: unknown
cycle_time: 0m
tags: [refatoração, migração, Azure]

## O que aconteceu
Este PR ajusta o pipeline de download para persistir o caminho/nome do arquivo no Azure Blob Storage (`blobName`) dentro da tabela `downloaded_files`, além de reforçar a migração para considerar apenas registros ainda não migrados (sem `blob_url`). A mudança líquida agora grava `blob_url` e `local_path` no banco, e a migração passa a filtrar por `blob_url IS NULL`.

## Decisão / Solução
Foi decidido que, além da URL pública (`blob_url`), o identificador do blob (ex.: `prefix/arquivo.ext`) seria salvo em `local_path`. Isso melhora a rastreabilidade e auditoria, além de tornar a migração mais segura, evitando retrabalho e duplicidades.

## Lessons
- A mudança na semântica de `local_path` deve ser comunicada aos consumidores para evitar confusões, já que agora representa o caminho no Azure Blob Storage.
- É importante garantir que a assinatura dos serviços que interagem com `local_path` seja atualizada para refletir a nova lógica.
- Testes rigorosos devem ser realizados após a migração para validar que apenas registros não migrados sejam processados, evitando retrabalho.

## Source
https://github.com/living/insight-funds/pull/11
