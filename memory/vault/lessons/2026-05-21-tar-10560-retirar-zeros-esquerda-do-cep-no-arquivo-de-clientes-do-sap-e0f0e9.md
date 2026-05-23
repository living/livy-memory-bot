---
type: lesson
date: 2026-05-21
subject: "Trello: [TAR-10560] Retirar zeros à esquerda do CEP no arquivo de Clientes do SAP [B3/UIF+NW+NT]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3uifnwnt]
---

## O que aconteceu
Recebemos um acionamento do time de Faturamento sobre erros na integração com a prefeitura, que começou a validar o CEP e estava recebendo dados com zeros à esquerda.

## Decisão / Solução
Após análise, foi identificado que o arquivo UFIN_CLIENTES_SAP-DELTA.txt estava enviando o CEP com zeros à esquerda. A decisão foi alterar os arquivos de integração com o SAP para que sejam enviados apenas os números do CEP, sem os zeros à esquerda.

## Lessons
- A validação de dados deve ser realizada antes da integração com sistemas externos para evitar erros.
- É importante manter uma comunicação clara entre as equipes envolvidas para resolver problemas rapidamente.

## Source
https://trello.com/c/Qg6lZNn1
