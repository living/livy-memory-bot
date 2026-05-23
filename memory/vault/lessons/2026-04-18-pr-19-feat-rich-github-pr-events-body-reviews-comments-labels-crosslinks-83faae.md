---
type: lesson
source: github
source_ref: "living/livy-memory-bot/pull/19"
date: 2026-04-18
subject: "PR #19 — feat: rich GitHub PR events (body, reviews, comments, labels, crosslinks)"
author: unknown
cycle_time: 18m
tags: [GitHub, PR, enrichment, pipeline]

## O que aconteceu
Este PR adiciona suporte a “GitHub Rich PR Events” no pipeline de research, expandindo a ingestão de Pull Requests de um modelo leve para um modelo rico com diversas informações adicionais. A mudança é aditiva, introduzindo um novo `GitHubRichClient` e integrando o enriquecimento no `ResearchPipeline`.

## Decisão / Solução
Foi decidido criar um novo cliente que busca informações completas de PRs, reviews e comentários via REST e GraphQL, mantendo duas visões dos dados. A integração no pipeline foi realizada para enriquecer os eventos GitHub e gerar páginas de evidência com as informações extraídas.

## Lessons
- Sempre valide a autenticação e permissões necessárias para chamadas de API externas, como o `gh` CLI, para evitar falhas silenciosas no pipeline.
- Utilize heurísticas com cautela, pois podem gerar falsos positivos; sempre que possível, implemente validações adicionais.
- Documente claramente as alterações e a lógica de enriquecimento para facilitar a manutenção e entendimento do código por outros desenvolvedores.

## Source
https://github.com/living/livy-memory-bot/pull/19
