---
type: lesson
source: github
source_ref: "living/RetailAuditRulesDashboard/pull/143"
date: 2026-05-13
subject: "PR #143 — fix(build): lazy-initialize AzureBlobService to avoid build-time env …"
author: unknown
cycle_time: 0m
tags: [build, Azure, lazy-initialization]

## O que aconteceu
Este PR ajusta o **AzureBlobService** para usar **inicialização tardia (lazy initialization)** das credenciais e do `BlobServiceClient`, evitando criação imediata no carregamento da classe e centralizando a validação/configuração do `AZURE_STORAGE_CONNECTION_STRING`. A mudança foi focada em **robustez** e **controle de inicialização** do serviço de Blob Storage.

## Decisão / Solução
Foi decidido implementar a inicialização tardia do cliente Azure, onde o serviço agora inicializa apenas quando necessário. Além disso, foram criados getters para garantir que o serviço foi inicializado e um novo método `ensureInitialized()` para centralizar a leitura e validação da variável de ambiente.

## Lessons
- Implementar inicialização tardia pode melhorar a flexibilidade e a robustez do serviço, evitando erros de configuração em tempo de construção.
- Encapsular a lógica de inicialização em métodos específicos ajuda a manter o código mais limpo e a evitar duplicação de lógica.
- É importante considerar o impacto em testes e ambientes, especialmente em cenários onde a configuração pode não estar presente.

## Source
https://github.com/living/RetailAuditRulesDashboard/pull/143
