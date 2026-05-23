---
type: lesson
source: github
source_ref: "living/bot-ai-app/pull/92"
date: 2026-05-08
subject: "PR #92 — correção na exibição de documentos na tela de atendimento"
author: unknown
cycle_time: 4h 24m
tags: [UX, melhoria, tipagem]

## O que aconteceu
Este PR implementou ajustes de tipagem e melhorias na exibição de mensagens com arquivos no Chatboard. A principal mudança foi a introdução de um nome de arquivo amigável para documentos, que agora é derivado da URL, evitando a dependência de um campo que pode não existir.

## Decisão / Solução
Decidiu-se que o sistema deve extrair o nome do arquivo a partir da URL e utilizá-lo como fallback para melhorar a experiência do usuário ao lidar com documentos. Além disso, foram realizados ajustes de formatação para padronizar o código.

## Lessons
- Sempre que possível, derive informações críticas de fontes confiáveis para evitar dependências de dados que podem não estar presentes.
- A padronização de estilo e formatação é essencial para a legibilidade e manutenção do código a longo prazo.
- É importante considerar casos de borda ao implementar funções que dependem de padrões específicos, como a extração de nomes de arquivos de URLs.

## Source
https://github.com/living/bot-ai-app/pull/92
