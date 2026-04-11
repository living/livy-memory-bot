# Living Memory Vault — Documentação Técnica

> Última atualização: 2026-04-11

## Visão Geral

O Living Memory Vault é um sistema de memória agêntica para a Living Consultoria. Captura reuniões do TLDV, pessoas participantes e seus relacionamentos, persistindo como arquivos Markdown consumíveis pelo Obsidian (humano) e pelo pipeline agêntico (máquina).

## Arquitetura

```
Supabase (TLDV) ──→ external_ingest.py ──→ entities/meetings/*.md
                   │                     → entities/persons/*.md
                   │                     → relationships/person-meeting.json
                   │                     → index.md (dashboard)
                   │
                   └──→ enrich_github.py → decisions/*.md
```

### Stack

| Componente | Tecnologia | Papel |
|---|---|---|
| Fonte de reuniões | Supabase (tabelas `meetings`, `summaries`) | Dados brutos do TLDV pipeline |
| Fonte de participantes | TLDV API (`gw.tldv.io`) | Nomes, emails, IDs |
| Armazenamento | Markdown + JSON (filesystem) | Obsidian-compatible vault |
| Vídeo | Azure Blob Storage | `livingnetopenclawstorage.blob.core.windows.net` |
| Lint/validação | `vault_lint_scanner.py` | Órfãos, stale, contradições |
| Index | `index_manager.py` | Dashboard regenerado a cada ingest |

### Pipeline de Ingest

**Arquivo:** `vault/ingest/external_ingest.py`

Estágios:
1. **Fetch** — Busca reuniões do Supabase (`fetch_meetings_from_supabase`)
2. **Resolve participants** — Para cada reunião, busca participantes via TLDV API
3. **Build entities** — Normaliza meetings e persons (`normalize_meeting_record`, `build_person_entity`)
4. **Persist persons** — `upsert_person` com fuzzy merge de nomes
5. **Persist meetings** — `upsert_meeting` com wiki-links para participantes
6. **Build relationships** — Gera edges `person↔meeting` em JSON
7. **Enrich person files** — Atualiza cada person com `## Reuniões` section
8. **GitHub enrichment** — Opcional, busca PRs/commits
9. **Rebuild index** — Regenera `index.md` como dashboard estruturado

## Estrutura do Vault

```
memory/vault/
├── index.md                          # Dashboard (auto-gerado)
├── entities/
│   ├── meetings/                     # 36 reuniões
│   │   ├── 2026-02-20 Daily Operações - Infra - Suporte B3.md
│   │   ├── 2026-03-18 Processo NW + Roadmap Futuro.md
│   │   └── ...
│   └── persons/                      # 18 pessoas
│       ├── Lincoln Quinan Junior.md
│       ├── Robert Urech.md
│       └── ...
├── relationships/
│   └── person-meeting.json           # 172 edges
├── decisions/                        # Decisões do GitHub enrichment
├── .cursors/                         # Cursors de idempotência
└── schema/                           # Schemas e configs
```

## Templates

### Meeting File

```markdown
---
entity: "Processo NW + Roadmap Futuro"
type: meeting
id_canonical: meeting:69baa3584c2ca20012ea399f
meeting_id_source: 69baa3584c2ca20012ea399f
confidence: medium
started_at: 2026-03-18T13:06:32.612+00:00
source_keys:
  - tldv:69baa3584c2ca20012ea399f
---

# Processo NW + Roadmap Futuro

> [!info] 2026-03-18 · 99 min · 4 participantes
> 🎥 [Assistir gravação](https://livingnetopenclawstorage.blob.core.windows.net/...)
> 📝 [Transcrição](https://livingnetopenclawstorage.blob.core.windows.net/...)

## Participantes
- [[Robert Urech]]
- [[Lincoln Quinan Junior]]
- [[Sergio Fraga]]
- [[Jaime dos Santos Jr]]

## Resumo
<!-- Enriquecimento TLDV -->

## Decisões
<!-- Decisões da reunião -->

## Metadados
- **ID:** `69baa3584c2ca20012ea399f`
- **Início:** 2026-03-18T13:06:32.612+00:00
```

**Campos key no frontmatter:**
- `id_canonical` — ID canônico para lookup programático (`meeting:{tldv_id}`)
- `meeting_id_source` — ID original no TLDV
- `source_keys` — Chaves de idempotência (evita reprocessamento)
- `confidence` — Confiança da extração (low/medium/high)

**Body sections (parseáveis por regex):**
- `## Participantes` — Wiki-links para persons
- `## Resumo` — Tópicos/pontos-chave (preenchido por enrichment futuro)
- `## Decisões` — Decisões da reunião (preenchido por enrichment futuro)
- `## Metadados` — Dados técnicos

### Person File

```markdown
---
entity: "Robert Urech"
type: person
id_canonical: "person:tldv:645e7c3236d05500131efcb0"
confidence: medium
email: robert@livingnet.com.br
---

# Robert Urech

**Email:** robert@livingnet.com.br

## Reuniões
- [[2026-04-10 Status Kaba - BAT - BOT]]
- [[2026-03-18 Processo NW + Roadmap Futuro]]
- [[2026-02-20 Daily Operações - Infra - Suporte B3]]
```

### Index (Dashboard)

Gerado por `rebuild_index()`. Seções:
- `👥 Pessoas` — Lista alfabética com wiki-links
- `📅 Reuniões` — Calendário agrupado por mês (labels em PT-BR)
- `📊 Stats` — Contadores

## Relacionamentos

`relationships/person-meeting.json` contém edges no formato:

```json
{
  "edges": [
    {
      "from_id": "person:tldv:645903ff864f0800133dc9fa",
      "to_id": "meeting:69d8e63a03320100137ebeb0",
      "role": "participant",
      "confidence": "high",
      "sources": [...]
    }
  ]
}
```

## Módulos do Pipeline

| Módulo | Arquivo | Função |
|---|---|---|
| Meeting ingest | `vault/ingest/meeting_ingest.py` | Fetch Supabase, normalizar, build entity |
| Person ingest | `vault/ingest/person_ingest.py` | Extrair persons de reuniões |
| Entity writer | `vault/ingest/entity_writer.py` | Persistir meetings/persons/cards como .md |
| External ingest | `vault/ingest/external_ingest.py` | Orquestrar pipeline completo |
| TLDV API client | `vault/ingest/tldv_api_client.py` | Chamadas HTTP para TLDV |
| Index manager | `vault/ingest/index_manager.py` | Gerar dashboard index.md |
| Lint scanner | `vault/ingest/vault_lint_scanner.py` | Validar qualidade do vault |
| GitHub enrich | `vault/enrich_github.py` | Enriquecer com PRs/commits |
| Relationship builder | `vault/domain/relationship_builder.py` | Construir edges person↔meeting |

## Idempotência

O pipeline é idempotente — rodar múltiplas vezes produz o mesmo resultado:
- **Cursors** em `.cursors/tldv.json` — tracking de última execução
- **`upsert_meeting/upsert_person`** — Skip se arquivo já existe
- **Fuzzy merge** — Persons com nomes similares são mergeados (ex: "Robert Urech" + "Robert U." → mesmo arquivo)
- **Lock** em `vault.lock` — Previne concorrência

## Fuzzy Merge de Nomes

O `upsert_person` busca arquivos existentes com nome similar usando:
1. Normalização (`_fuzzy_name_key`) — lowercase, sem acentos, sem sufixos
2. Prefix matching (`_is_name_prefix`) — "Robert" match "Robert Urech"
3. Pick richer name (`_pick_richer_name`) — Prefere nome mais completo

Quando mergeia, atualiza o frontmatter e o título sem reescrever o arquivo do perdedor.

## Lint

```bash
python3 -c "
from pathlib import Path
from vault.ingest.vault_lint_scanner import run_lint_scans
report = run_lint_scans(Path('memory/vault'))
print(f'Orphans: {len(report[\"orphans\"])}')
print(f'Stale: {len(report[\"stale\"])}')
print(f'Contradictions: {len(report[\"contradictions\"])}')
print(f'Relationships: {report[\"metrics\"][\"total_relationships\"]}')
"
```

## Rodar o Pipeline

```bash
python3 -c "
import os
from pathlib import Path
env_path = Path.home() / '.openclaw' / '.env'
for line in env_path.read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        os.environ.setdefault(k, v.strip())

from vault.ingest.external_ingest import run_external_ingest
result = run_external_ingest(
    meeting_days=55,
    card_days=55,
    tldv_token=os.environ.get('TLDV_JWT_TOKEN', ''),
    dry_run=False,
)
print(result)
"
```

## Testes

```bash
python3 -m pytest vault/tests/ -q --tb=short
```

Cobertura: deduplicação de nomes, resolução de participantes, pipeline end-to-end, lock/cursors, index.

## Evolução (Futuro)

| Item | Status | Notas |
|---|---|---|
| Enriquecer `## Resumo` com TLDV summaries | 🔜 pendente | Dados já disponíveis no Supabase `summaries` |
| Enriquecer `## Decisões` com TLDV decisions | 🔜 pendente | Dados já disponíveis no Supabase `summaries.decisions` |
| Inline transcript excerpt | 🔜 pendente | `whisper_transcript` disponível para 32/67 reuniões |
| Cards do Trello | 🔜 pendente | `fetch_cards` implementado, aguarda API key |
| Entidades de repo | 🔜 pendente | `entities/repos/` preparado |
| Dataview queries no Obsidian | 🔜 pendente | `date` no frontmatter habilita queries |

## Decisões Técnicas

1. **Azure blob URLs** (não TLDV) para vídeo — SAS token válido até 2028, sem dependência de auth TLDV
2. **Subdiretórios por tipo** — `meetings/` e `persons/` para organização no Obsidian
3. **Wiki-links por filename** — Obsidian resolve `[[Nome]]` independente do path
4. **Slug com espaços** — `_slugify()` preserva acentos e espaços para legibilidade
5. **Index rebuild (não incremental)** — Evita stale entries, mais simples de manter
6. **Frontmatter YAML + body Markdown** — Máquina lê frontmatter, humano lê body
7. **Obsidian callouts (`> [!info]`)** — Formatação nativa para data/duração/vídeo
