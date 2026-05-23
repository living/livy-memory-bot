---
type: lesson
date: 2026-04-09
subject: "Trello: Atualizar o documento de procedimento de deploy [B3/BancoB3]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3bancob3]
---

## O que aconteceu
Foi necessário atualizar o documento de procedimento de deploy para incluir etapas adicionais de verificação antes do passo 2.

## Decisão / Solução
Adicionou-se a instrução para verificar se o disco D:\ das VMs secundárias está acessível via UNC a partir da máquina principal. Em caso de falha, o pacote deve ser copiado manualmente para as VMs secundárias. Além disso, deve-se verificar a comunicação entre as VMs secundárias e a VM principal, registrando qualquer falha no arquivo hosts.

## Lessons
- A documentação deve ser constantemente atualizada para refletir as melhores práticas e procedimentos operacionais.
- Verificações de conectividade e acessibilidade são cruciais para evitar falhas durante o processo de deploy.

## Source
https://trello.com/c/B9vhxHWv
