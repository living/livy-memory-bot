# Design: Autoresearch + RLHF para o Agente de Memória Livy

## Problema

O agente de memória atual opera de forma reativa: decisões são tomadas uma vez e nunca revisitadas. O consolidation script roda, mas não "aprende" com o resultado das suas ações. Não há mecanismo para o usuário corrigir o comportamento do agente ao longo do tempo.

## Solução

Autoresearch + RLHF simplificado: um cron noturno executa iterações de melhoria com metricas mecânicas, o usuário fornece feedback via Telegram (botões 👍/👎), e o agente usa esse feedback como sinal para decidir o que manter ou desfazer.

## Arquitetura

### 3 Camadas de Memória (existente)

| Camada | Fonte | Formato |
|---|---|---|
| Observations | `~/.claude-mem/claude-mem.db` | SQLite |
| Curated | `MEMORY.md` + `memory/curated/*.md` | Markdown |
| Operational | `HEARTBEAT.md` + `memory/consolidation-log.md` | Markdown |

### Nova Camada: Feedback

```
memory/
├── feedback-log.jsonl          # Novo: todas as avaliações do usuário
├── learned-rules.md            # Novo: regras extraídas do feedback
└── .archive/
```

### Fluxo de Execução

```
CRON (07h BRT, dream-memory-consolidation)
│
├─1. MEDIR
│   python3 skills/memoria-consolidation/autoresearch_metrics.py
│   → gera metrics.json com scores por dimensão
│
├─2. MELHORAR (se score < threshold)
│   /autoresearch
│   Goal: Improve memory agent quality score
│   Scope: memory/curated/*.md, skills/memoria-consolidation/consolidate.py, HEARTBEAT.md
│   Metric: python3 skills/memoria-consolidation/autoresearch_verify.py --metric <dim>
│   Direction: Higher is better
│   Iterations: 10
│
├─3. REPORTAR
│   Mensagem enviada via DM (Telegram, bot @livy_agentic_memory_bot)
│   Usuário: Lincoln (tg:7426291192)
│   Verbose: todas as ações do loop
│
├─4. RECEBER FEEDBACK
│   Usuario clica 👍 ou 👎 nos botoes inline
│   Handler processa callback_query
│   Grava em feedback-log.jsonl
│
└─5. APRENDER
    Na proxima iteração, o agente:
    - Lê feedback-log.jsonl
    - Calcula score por tipo de ação
    - Ações com score negativo → evita ou muda approach
    - Ações com score positivo → prioriza padrão similar
```

## Métricas e Verificação

### Dimensões de Qualidade

| Dimensao | Metrica | Script | Direcao |
|---|---|---|---|
| Completude da curadoria | Score de checklist por topic file (0-10) | `autoresearch_metrics.py --metric completeness` | Higher is better |
| Cobertura de contexto | Cross-refs entre topic files | `autoresearch_metrics.py --metric crossrefs` | Higher is better |
| Consolidação automática | Ações automáticas por execução | `autoresearch_metrics.py --metric consolidation_actions` | Higher is better |
| Performance operacional | Intervenções manuais necessárias | `autoresearch_metrics.py --metric interventions` | Lower is better |

### Completude de Topic File (checklist 0-10)

Cada topic file recebe score de 0 a 10:
- +2: frontmatter com `name`, `description`, `type` preenchidos
- +2: campo `date` presente
- +2: pelo menos uma decisão registrada
- +2: pelo menos uma cross-reference para outro topic file
- +2: mtime < 30 dias

### Cross-references

Contagem de links `[nome](path)` que apontam para outros topic files em `memory/curated/`.

## Feedback do Usuario

### Formato do Log

```jsonl
{"ts":"2026-03-31T10:00:00Z","action":"add_frontmatter","target":"memory/curated/forge-platform.md","rating":"up","note":null}
{"ts":"2026-03-31T10:05:00Z","action":"consolidate_stale","target":"memory/curated/tldv-pipeline.md","rating":"down","note":"arquivou cedo demais"}
{"ts":"2026-03-31T10:10:00Z","action":"add_crossref","target":"memory/curated/bat-conectabot.md","rating":null}
```
> Nota: `rating: null` significa que o usuário não respondeu (inconclusivo). Ações com `null` não afetam o score.

### Tipos de Acao

| Action | Descricao |
|---|---|
| `add_frontmatter` | Adicionou frontmatter a topic file |
| `add_crossref` | Adicionou link para outro topic file |
| `remove_stale` | Removeu stale entry (TODO, FIXME, etc.) |
| `archive_file` | Moveu arquivo para .archive/ |
| `unarchive_file` | Restaurou arquivo do .archive/ |
| `consolidate` | Executou consolidação |
| `healed_heartbeat` | Preencheu secao vazia no HEARTBEAT |

### Regras Aprendidas

Ao final de cada dia, um script processa o feedback-log.jsonl e gera `memory/learned-rules.md`:

```markdown
# Learned Rules — 2026-03-31

## Regras com score positivo (manter padrao)
- add_frontmatter: score +3 → **Manter**: frontmatter completo e date presente
- add_crossref: score +2 → **Manter**: links entre projetos relacionados

## Regras com score negativo (evitar)
- archive_file: score -1 → **Evitar**: não arquivar arquivos com 30-60 dias
  - Razão: 2x thumbs down citing "arquivou cedo demais"

## Regras neutras (experimentar aborduras alternativas)
- consolidate: score 0 → **Neutro**: ajustar limiar de stale
```

## Interface no Telegram

### Inline Keyboard Buttons

Cada ação reportada individualmente no Telegram:

```
🧠 [Livy Memory] Iteration 3 — 10:00 BRT

📝 add_frontmatter: forge-platform.md
   → Adicionei frontmatter name/description/type
   [👍] [👎]

📝 add_crossref: forge-platform.md → bat-conectabot-observability.md
   → Linkei projetos relacionados
   [👍] [👎]

📝 archive_file: livy-evo.md
   → Movi para .archive/ (stale, >60d)
   [👍] [👎]
```

> ⚠️ Itens sem resposta em 1 hora são marcados como inconclusivos no log.
> 📱 Enviado via DM para @lincoln — não aparece no grupo.

### Mensagens de Resumo (cron)

```
🧠 [Livy Memory] Consolidacao Noturna — 2026-03-31

📱 Enviado via DM

Métricas antes:
- Completude: 7.2/10
- Cross-refs: 4
- Ações auto: 3
- Intervenções: 2

Métricas depois:
- Completude: 7.8/10 (+0.6)
- Cross-refs: 7 (+3)
- Ações auto: 5 (+2)
- Intervenções: 1 (-1)

Feedback pendente: 2 ações aguardando avaliação
[👍] [👎] para cada ação acima
```

## Componentes a Implementar

### 1. scripts/autoresearch_metrics.py

Executado no inicio de cada iteração. Calcula scores para as 4 dimensões.

```bash
python3 skills/memoria-consolidation/autoresearch_metrics.py --metric <dim>
python3 skills/memoria-consolidation/autoresearch_metrics.py --all  # todas as metricas
```

### 2. scripts/autoresearch_verify.py

Executado pelo autoresearch loop para verificar resultado de cada mudança.

```bash
python3 skills/memoria-consolidation/autoresearch_verify.py --metric completeness
```

### 3. handlers/feedback_handler.py

Handler de callback_query do Telegram. Processa cliques em 👍/👎.

### 4. scripts/learn_from_feedback.py

Executado daily. Consome feedback-log.jsonl, gera learned-rules.md.

```bash
python3 skills/memoria-consolidation/learn_from_feedback.py
```

### 5. Integration com OpenClaw

O bot `@livy_agentic_memory_bot`:
- Recebe callback_query com dados `action:target:rating`
- Grava no feedback-log.jsonl
- Responde ao callback para remover loading state
- **DM direto para Lincoln** (tg:7426291192) — não no grupo

## Cron Jobs

| Cron | Horario | Acao |
|---|---|---|
| dream-memory-consolidation | A cada 1 hora | Metrics + autoresearch loop (ate estabilizar) |
| memory-feedback-learn | 23h BRT | Processa feedback do dia, gera learned-rules.md |

**Nota:** Frequencia inicial de 1 hora ate o sistema estabilizar. Depois aumentar para 4h, depois 8h, ate chegar em nightly (07h BRT).

## Feedback Inconclusivo

Ações sem feedback do usuário são tratadas como **inconclusivas** (score não afetado, não entra na contagem). Apenas ações com 👍 ou 👎 explícito são usadas para aprendizado.

Feedback inconclusivo não é坏事 — significa que o agente está funcionando bem o suficiente para não precisar correção.

## Dependências

- OpenClaw com Telegram channel configurado
- Bot `@livy_agentic_memory_bot` com callback handler
- `openclaw memory` configurado (memória agêntica)
- Cron jobs configurados no OpenClaw

## Escopo da Implementação (v1)

**Primeira versão focada em:**
1. scripts/autoresearch_metrics.py (metricas mecânicas)
2. scripts/autoresearch_verify.py (verificacao por dimensao)
3. handlers/feedback_handler.py (receber 👍/👎 do Telegram)
4. scripts/learn_from_feedback.py (gerar learned-rules.md)
5. Integração autoresearch → Telegram (report.verbose)
6. Configuração de cron jobs

**NÃO está na v1:**
- Dashboard visual no Telegram
- Feedback com notas de texto
- Agregação temporal avançada (média móvel)
- Aprendizado por topic file específico
