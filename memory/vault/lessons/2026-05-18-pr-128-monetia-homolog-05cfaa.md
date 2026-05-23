---
type: lesson
subject: "PR #128 — Monetia homolog"
author: unknown
cycle_time: 3m
tags: [API, agendamentos, cron, refatoração, segurança]

## O que aconteceu
Este PR adiciona agendamentos (cron jobs) dentro da API usando `node-cron`, cria uma estrutura central de configuração de tarefas e inclui um novo endpoint para finalizar atendimento de um usuário do Chatboard. Também traz ajustes de robustez e uma grande normalização/refatoração de estilo no serviço do Supabase, além de correções para cenários onde certas tabelas do Supabase não existem.

## Decisão / Solução
Foi decidido implementar um scheduler dentro do NestJS utilizando `node-cron`, centralizando as tarefas em um novo arquivo. Um novo endpoint foi criado para finalizar atendimentos no Chatboard, melhorando a robustez do sistema em contextos sem requisições autenticadas e realizando uma refatoração significativa no serviço do Supabase.

## Lessons
- Evite o uso de `eval()` em rotinas agendadas para aumentar a segurança e a manutenibilidade do código.
- Sempre revise e rotacione credenciais expostas em URLs para evitar vazamentos de segurança.
- Certifique-se de que variáveis de ambiente necessárias estejam definidas para evitar falhas em agendamentos.

## Source
https://github.com/living/bot-ai-api/pull/128
