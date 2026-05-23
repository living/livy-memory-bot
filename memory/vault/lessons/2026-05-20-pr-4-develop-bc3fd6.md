---
type: lesson
subject: "PR #4 — Develop"
author: unknown
cycle_time: 0m
tags: [migração, armazenamento, Azure, Supabase, CI/CD]

## O que aconteceu
Este PR migra as configurações de download de arquivos, que antes estavam em JSONs locais, para um banco de dados (Supabase/Postgres) e altera o armazenamento de arquivos baixados do disco para o Azure Blob Storage. Isso resulta em uma fonte única e consistente para as configurações, eliminando a dependência de volumes locais.

## Decisão / Solução
Foi decidido centralizar as configurações no banco de dados, criando uma nova tabela `download_configs` e removendo a pasta `downloads/`. Além disso, o serviço de download foi reestruturado para fazer upload diretamente para o Azure Blob Storage, armazenando a URL do blob no banco de dados em vez do caminho local.

## Lessons
- Centralizar as configurações no banco de dados pode reduzir o risco de inconsistências e facilitar a manutenção.
- A migração para serviços de armazenamento em nuvem, como o Azure Blob Storage, melhora a durabilidade e acessibilidade dos arquivos.
- É importante garantir que as credenciais e configurações de serviço estejam corretamente configuradas para evitar falhas em produção.

## Source
https://github.com/living/insight-funds/pull/4
