---
type: lesson
source: github
source_ref: "living/livy-memory-bot/pull/19"
date: 2026-04-18
subject: "PR #19 — GitHub Rich PR Events + import shadowing fix"
author: lincolnqjunior
tags: [github, import-shadowing, python, bugfix]

## O que aconteceu
PR #19 adicionou suporte a eventos ricos de PR GitHub (body, reviews, comments, labels, crosslinks). Durante a validação E2E pós-merge de PR #18, um bug preexistente foi descoberto e corrigido: `vault/lint/` (package directory) sombreava `vault/lint.py` (module file), fazendo `from vault.lint import Linter` falhar silenciosamente ou importar o package errado.

## Decisão / Solução
- **Fix via re-export**: `vault/lint/__init__.py` agora faz re-export explícito via `importlib.reload()` para garantir que o module é usado em vez do package.
- **Import shadowing é um anti-pattern em Python**: um diretório com o mesmo nome de um ficheiro `.py` no mesmo nível causa prioridade ambígua na resolução de imports.
- **Validação E2E apanhou bug que testes unitários não apanharam**: os testes passavam porque testavam módulos isolados; o bug só se manifestava em condições de integração real.

## Lessons
- Import shadowing em Python: nunca criar um diretório `vault/lint/` se já existe `vault/lint.py` — o package sombreia o module silenciosamente.
- Quando um package e module coexistem, usar re-export explícito no `__init__.py` do package para garantir que o módulo certo é importado.
- Testes unitários não capturam bugs de integração: validação E2E com contexto real é insubstituível.
- Bug de shadowing pode passar despercebido em CI se os testes não carregarem o módulo da mesma forma que a produção.

## Source
https://github.com/living/livy-memory-bot/pull/19
