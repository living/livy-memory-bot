---
type: lesson
subject: "PR #13 — Persistência de transcrições em Azure com artefato tl;dv"
author: unknown
date: 2026-04-09
cycle_time: 39m
tags: [armazenamento, Azure, transcrições, pipeline]

## O que aconteceu
Este PR implementa o armazenamento de transcrições em Azure Blob Storage, adicionando um ponteiro no Supabase e ajustando o pipeline de enriquecimento para persistir e ler transcrições via blob quando disponível. Também melhora a robustez de retries/recovery no processo de enriquecimento e altera o enriquecimento do GitHub para não bloquear quando não há repositórios relacionados.

## Decisão / Solução
Foi decidido implementar a persistência das transcrições no Azure para reduzir a dependência de armazenamento legado no Supabase, permitindo uma migração gradual. O fluxo de leitura foi ajustado para tentar acessar o blob primeiro e, em caso de falha, fazer fallback para o armazenamento legado. Além disso, melhorias foram feitas na recuperação de contexto e na lógica de enriquecimento do GitHub para evitar falhas desnecessárias.

## Lessons
- Sempre que implementar uma nova dependência, como o Azure Storage, documente claramente as variáveis de ambiente necessárias para evitar problemas de configuração.
- Ao realizar migrações de dados, utilize estratégias de dual-read para garantir a continuidade do serviço e evitar quebras de compatibilidade.
- Testes automatizados são essenciais para validar mudanças complexas, especialmente em sistemas que dependem de múltiplas fontes de dados.

## Source
https://github.com/living/livy-tldv-jobs/pull/13
