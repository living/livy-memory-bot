---
type: lesson
source: tldv
source_ref: "tldv/6a0da23911b7af0013b3fc3d"
date: 2026-05-20
subject: "Status Kaba/BAT/BOT"
project: KABA
tags: [kaba, tldv, meeting]
---
## Meeting: Status Kaba/BAT/BOT (2026-05-20)

### To-do / Action Items
- Esteves: Implementar um endpoint de health no Hydra que seja aberto para o sistema poder consultar se está ativo e o tempo de ping.

### Decisões
- Foi decidido que o endpoint de health deve ser rate limited para evitar ataques de DDoS, com um limite de 5 requisições por minuto.

### Blockers / Open Questions
- Não há blockers identificados, mas há uma preocupação sobre a implementação do rate limiting no endpoint de health.

### Deliverables / Outcomes
- Discussão sobre a nova autenticação do sistema Hydra e a necessidade de um endpoint de health.

### Participantes
- Marcio
- Esteves
- Lincoln
- Robert

## Source
Auto-generated from TLDV transcript (Azure Blob)
