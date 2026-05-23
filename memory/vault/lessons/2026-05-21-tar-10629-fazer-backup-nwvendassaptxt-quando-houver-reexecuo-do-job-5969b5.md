---
type: lesson
source: trello
source_ref: "trello/69f35dc0e4daa2a523dcdeec"
date: 2026-05-21
subject: "Trello: [TAR-10629] - Fazer backup NW_VENDAS_SAP.txt quando houver reexecução do Job [B3/UIF+NW+NT]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3uifnwnt]
---

## O que aconteceu
Foi solicitado que, ao final da execução do script Copy_file_NW_MetraNet_Vendas.ps1, um backup do arquivo NW_VENDAS_SAP.txt seja realizado. O backup deve seguir um padrão de nomenclatura que inclui a data e hora da execução.

## Decisão / Solução
A solução proposta foi utilizar a mesma lógica de backup já implementada para outros arquivos, garantindo consistência no processo. Além disso, foi decidido ajustar o script Copy_file_NT_MetraNet_Vendas.ps1 para que ele utilize a data operacional de um arquivo específico, simplificando o fluxo de execução.

## Lessons
- A padronização na nomenclatura de backups facilita a identificação e recuperação de arquivos.
- A reutilização de lógicas de scripts existentes pode acelerar o desenvolvimento e reduzir erros.

## Source
https://trello.com/c/EGygQ9xa
