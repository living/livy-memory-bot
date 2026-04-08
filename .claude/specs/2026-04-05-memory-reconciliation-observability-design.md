# Spec — Memory Reconciliation + Decision Observability

**Versão:** 1.0  
**Data:** 2026-04-05  
**Status:** Draft for review

---

## 1. O que estamos construindo

Um reconciliador de memória que compara **estado real atual** com **memória curada** e **contexto de transição** para manter os topic files corretos, auditáveis e úteis.

O objetivo não é apenas adicionar novas decisões, mas também:
- atualizar estado operacional atual;
- mover bugs de abertos para resolvidos/superados quando houver evidência concreta;
- preservar histórico sem deixar itens obsoletos parecerem atuais;
- registrar **por que** cada mudança foi aplicada, rejeitada ou adiada.

---

## 2. Problema atual

O pipeline atual de consolidação e curadoria falha em três pontos principais:

1. **Não reconcilia com estado canônico atual**  
   Detecta sinais textuais, mas não monta um snapshot factual por tópico.

2. **Não separa estado atual de histórico**  
   Decisões antigas, bugs já resolvidos e pendências ativas convivem sem tipagem suficiente.

3. **Não oferece trilha causal suficiente**  
   O sistema registra que mudou algo, mas não explica bem qual regra levou à decisão, qual evidência sustentou a mudança, nem qual era o estado anterior.

Sintomas já observados:
- bugs marcados como abertos mesmo após correção concreta;
- jobs/modelos/crons desatualizados nos topic files;
- duplicações no `memory/curation-log.md`;
- decisões irrelevantes ou mal mapeadas entrando em tópicos errados;
- contradições explícitas em topic files, como item resolvido ainda aparecer como aberto.

---

## 3. Fonte de verdade

A política aprovada é **híbrida por tipo**.

### 3.1 Estado operacional atual
Estas entidades seguem a verdade concreta observável:
- jobs/crons;
- modelos/config atual;
- runtime/configuração ativa;
- branches/PRs merged quando materializam estado atual.

**Regra:** quando a memória contradiz o estado atual verificável, o estado atual vence.

### 3.2 Decisões arquiteturais e históricas
Decisões não devem ser apagadas automaticamente.

**Regra:** decisões permanecem no histórico, mas podem ser reclassificadas como:
- vigente;
- superada;
- obsoleta;
- substituída por outra decisão.

### 3.3 Bugs, issues e pendências
Esses itens devem mudar de classe ao longo do tempo.

**Regra:** bugs não somem; eles transitam entre:
- aberto;
- resolução declarada, aguardando confirmação;
- resolvido;
- superado;
- conflito.

---

## 4. Papel dos meetings diários

Os daily meetings entram como **camada de contexto de transição**, não como verdade operacional única.

Eles ajudam a responder:
- por que algo mudou;
- se um item foi deliberadamente removido, adiado ou substituído;
- se uma correção foi declarada antes de aparecer claramente em logs/código.

Mas um trecho de meeting sozinho não deve promover automaticamente um item para “estado atual confirmado” quando o tipo da entidade exige validação concreta.

### Regra de uso
- **Repo/runtime/config/logs/cron real**: determinam estado atual.
- **Meetings/TLDV/feedback**: explicam intenção, motivo e transição de estado.

Exemplo:
- meeting diz “Whisper foi resolvido”; 
- PR merged e config atual confirmam a migração;
- memória final move o bug para resolvido e registra o motivo com base nas duas fontes.

---

## 5. Requisito adicional: observabilidade causal

O sistema deve registrar não apenas **o que** mudou, mas também **por que** mudou.

### Para cada decisão do reconciliador, registrar:
- entidade afetada;
- estado anterior;
- estado novo;
- motivação textual (`why`);
- evidências usadas;
- fontes das evidências;
- regra aplicada;
- confiança;
- timestamp;
- resultado da decisão (`accepted`, `rejected`, `deferred`, `conflict`).

### Limite honesto
“Observabilidade absoluta” do passado só é possível quando a evidência foi capturada. Para eventos antigos sem rastros suficientes, o sistema deve registrar explicitamente o nível de causalidade:
- **forte** — há evidência concreta + contexto;
- **média** — há evidência concreta, mas motivo parcial;
- **fraca** — há só contradição factual, sem causa histórica clara.

---

## 6. Modelo de evidência e decisão

Separar duas camadas:

### 6.1 Evidence store
Armazena fatos observados e suas origens, por exemplo:
- PR merged;
- commit;
- cron existente;
- trecho de config;
- trecho de log;
- trecho de meeting;
- feedback humano.

### 6.2 Decision ledger
Armazena as conclusões do reconciliador, por exemplo:
- bug X movido para resolvido;
- decisão Y marcada como superada;
- modelo atual definido como Z;
- item A mantido aberto por falta de confirmação.

**Princípio:** evidência e interpretação não devem ser misturadas.

---

## 7. Arquitetura proposta

```text
Collectors / Fact Sources
    ├── runtime/config/git/cron snapshot
    ├── logs recentes
    ├── GitHub PRs/commits
    ├── meetings/TLDV
    └── feedback humano
             ↓
Evidence Normalizer
             ↓
Fact Snapshot Builder
             ↓
Reconciler
    ├── compara memória atual vs fatos vs contexto
    ├── aplica regras versionadas
    └── produz operações tipadas
             ↓
Decision Ledger
             ↓
Topic Rewriter
             ↓
Topic files reconciliados + run report
```

---

## 8. Componentes

### 8.1 `fact_snapshot_builder.py` (novo)
Responsável por montar, para cada tópico, um snapshot factual estruturado.

Exemplo de saída:

```json
{
  "topic": "tldv-pipeline-state",
  "current_jobs": [],
  "current_models": [],
  "current_config": [],
  "open_issues_from_logs": [],
  "merged_prs": [],
  "meeting_claims": []
}
```

### 8.2 `evidence_normalizer.py` (novo)
Converte diferentes origens para um formato comum:
- `entity_type`
- `entity_key`
- `claim_type`
- `source`
- `confidence`
- `evidence_ref`
- `observed_at`

### 8.3 `reconciler.py` (novo)
Compara:
- topic file atual;
- snapshot factual;
- evidências contextuais.

Produz operações tipadas:
- `set_current_state`
- `append_historical_decision`
- `mark_resolved`
- `mark_superseded`
- `remove_false_current_claim`
- `raise_conflict`
- `keep_as_is`

### 8.4 `decision_ledger.py` (novo)
Grava decisões append-only em arquivo JSONL, por exemplo:
- `memory/reconciliation-ledger.jsonl`

Cada linha contém:
- entidade;
- mudança proposta;
- evidências;
- regra aplicada;
- confiança;
- resultado.

### 8.5 `topic_rewriter.py` (novo)
Reescreve topic files por seções estruturadas em vez de fazer `replace()` textual frágil.

### 8.6 `curation_cron.py` (evolução)
Deixa de ser só um orquestrador de collectors + append de decisões. Passa a coordenar:
1. coleta factual;
2. normalização de evidências;
3. reconciliação;
4. ledger;
5. reescrita do topic file;
6. relatório da execução.

### 8.7 Componentes atuais a reduzir/substituir
- `topic_analyzer.py` atual é insuficiente para reconciliação semântica;
- `auto_curator.py` atual não tem noção de estado anterior, causalidade ou regras explícitas.

---

## 9. Regras de decisão

As regras do reconciliador devem ser explícitas, estáveis e versionadas.

Exemplos iniciais:
- `R001_current_runtime_beats_memory`
- `R002_meeting_claim_needs_operational_confirmation`
- `R003_architectural_decisions_are_preserved`
- `R004_resolved_bug_moves_to_history_not_erasure`
- `R005_missing_runtime_entity_requires_classification_not_guess`
- `R006_concrete_evidence_beats_textual_memory`

Cada decisão no ledger deve citar a regra aplicada.

---

## 10. Estrutura alvo dos topic files

Os topic files devem separar claramente presente, histórico e incerteza.

Estrutura recomendada:

```md
---
name: tldv-pipeline-state
description: Estado reconciliado do pipeline TLDV
type: project
status: active
last_reconciled_at: 2026-04-05
---

# TLDV Pipeline

## Status Atual
- estado operacional atual
- modelos/config ativos
- jobs/crons atuais

## Estado Operacional
- fatos recentes verificados

## Issues Abertas
- problema
  - evidências
  - última confirmação
  - por que continua aberto

## Issues Resolvidas / Superadas
- problema
  - quando mudou
  - por que mudou
  - evidências
  - regra aplicada

## Decisões Históricas
- decisão
  - motivo
  - evidências
  - status: vigente / superada / obsoleta

## Conflitos / Aguardando Confirmação
- claims ainda não reconciliados
```

Essa estrutura atende ao modelo híbrido aprovado:
- estado operacional atual fica claramente separado;
- histórico continua disponível;
- bugs e pendências podem mudar de classe sem desaparecer.

---

## 11. Fluxo de reconciliação

### Etapa 1 — Collect
Coletar evidências de:
- arquivos/config do repo;
- runtime/logs;
- GitHub;
- meetings/TLDV;
- feedback.

### Etapa 2 — Normalize
Transformar todas as observações em entidades comparáveis.

### Etapa 3 — Snapshot
Consolidar um snapshot factual por tópico.

### Etapa 4 — Reconcile
Comparar snapshot + contexto vs memória atual e gerar operações tipadas.

### Etapa 5 — Explain
Registrar no ledger por que cada decisão foi aceita, rejeitada ou adiada.

### Etapa 6 — Rewrite
Atualizar topic file por seções estruturadas.

### Etapa 7 — Report
Produzir:
- relatório legível de execução;
- ledger append-only;
- conflitos para revisão humana.

---

## 12. Saídas observáveis

### 12.1 Topic file reconciliado
Saída curta, legível e estável para humano.

### 12.2 `memory/reconciliation-ledger.jsonl`
Saída append-only de auditoria causal por item.

### 12.3 `memory/reconciliation-report.md`
Resumo por execução, por exemplo:
- 12 itens confirmados;
- 4 bugs movidos para resolvidos;
- 3 decisões marcadas como superadas;
- 2 conflitos abertos;
- 1 item rejeitado por baixa evidência.

### 12.4 `memory/conflict-queue.md`
Fila de conflitos reais, não apenas ausência de match.

---

## 13. Política de conflitos

Conflito existe quando fontes confiáveis apontam estados incompatíveis para a mesma entidade.

Exemplos:
- meeting afirma “resolvido”, mas logs recentes ainda mostram falha;
- PR merged indica migração concluída, mas cron real não existe;
- memória diz modelo atual = X, config atual mostra Y.

Quando houver conflito:
- não sobrescrever silenciosamente;
- registrar no ledger;
- adicionar à conflict queue;
- preservar contexto dos lados conflitantes.

---

## 14. Estratégia de rollout

### Fase 1 — Piloto único
Aplicar primeiro em `memory/curated/tldv-pipeline-state.md`.

Motivos:
- já apresenta contradições reais;
- tem sinais vindos de múltiplas fontes;
- concentra bugs, crons, modelos, decisões e histórico.

### Fase 2 — Generalizar para outros topic files vivos
Expandir para tópicos com maior churn operacional.

### Fase 3 — Integrar ao cron regular
Substituir progressivamente a curadoria textual simplificada pelo reconciliador estruturado.

---

## 15. Critérios de sucesso

O design será considerado bem-sucedido quando:

1. um topic file reconciliado não mantiver bug resolvido como aberto sem conflito explícito;
2. jobs/modelos/crons refletirem o estado atual verificável;
3. decisões históricas permanecerem preservadas, porém classificadas corretamente;
4. cada mudança aplicada tiver justificativa consultável no ledger;
5. o relatório de execução permitir responder “o que mudou e por quê” sem ler diff manual;
6. conflitos reais ficarem isolados para revisão, em vez de contaminarem o estado atual.

---

## 16. Fact-check com o que existe hoje

### Já existe hoje

O design não parte do zero. Os seguintes componentes já existem no workspace:
- `skills/memoria-consolidation/curation_cron.py` — orquestra coleta, persistência de sinais, análise, auto-cura, log e resumo Telegram;
- `skills/memoria-consolidation/signal_bus.py` — modelo `SignalEvent` + persistência JSONL;
- `skills/memoria-consolidation/conflict_detector.py` — detecção inicial de conflitos;
- `skills/memoria-consolidation/conflict_queue.py` — fila em Markdown;
- `skills/memoria-consolidation/topic_analyzer.py` — geração de candidate changes;
- `skills/memoria-consolidation/auto_curator.py` — aplicação automática de mudanças simples;
- collectors TLDV, logs, GitHub e feedback.

### O que o sistema atual realmente faz

Hoje o pipeline:
1. coleta sinais de múltiplas fontes;
2. persiste eventos em `memory/signal-events.jsonl`;
3. agrupa por `topic_ref`;
4. gera mudanças candidatas;
5. aplica `add_decision` / `deprecate_entry` quando houver evidência;
6. escreve `memory/curation-log.md`;
7. envia resumo por Telegram.

### Lacunas confirmadas por leitura do código e dos artefatos atuais

1. **Ainda não existe snapshot factual por tópico**  
   Nenhum componente atual monta uma visão consolidada do estado real antes da reconciliação.

2. **Ainda não existe ledger causal append-only**  
   `signal-events.jsonl` hoje guarda sinais, não decisões explicadas do reconciliador.

3. **A reescrita atual é frágil**  
   `auto_curator.py` usa inserção simples e `replace()` textual, sem parser estrutural por seções.

4. **A análise semântica ainda é rasa**  
   `topic_analyzer.py` trata só `decision`, `failure` e `topic_mentioned`; não reconcilia estado atual, histórico e transições.

5. **A detecção de conflitos é limitada**  
   `conflict_detector.py` depende de regras estreitas e overlap simples de palavras-chave.

6. **Já existem sinais de baixa precisão operacional**  
   `memory/curation-log.md` contém entradas duplicadas e decisões evidentemente irrelevantes para certos tópicos.

7. **Há contradições reais em topic files**  
   Exemplo já observado: `memory/curated/tldv-pipeline-state.md` marca Whisper como resolvido e ainda o mantém como bug aberto.

8. **Há problemas concretos de implementação atual**  
   - `signal_bus.py` sobrescreve `memory/signal-events.jsonl` a cada execução, então o arquivo atual não funciona como histórico append-only;  
   - `conflict_queue.py` calcula `CONFLICT_QUEUE_FILE` a partir de `parents[1] / "memory"`, o que aponta para o diretório errado a partir de `skills/memoria-consolidation/`;  
   - `conflict_queue.py:list_pending()` usa regex que retorna apenas IDs, então o parsing de topic/status não funciona como esperado.

### Conclusão do fact-check

O design proposto é **compatível com a base existente**, mas precisa ser tratado como **evolução arquitetural** e não como ajuste pequeno. Há infraestrutura reaproveitável, porém as partes centrais de verdade factual, explicabilidade e reescrita robusta ainda não existem.

---

## 17. Riscos e mitigações

| Risco | Como aparece | Mitigação proposta |
|---|---|---|
| Falso positivo de reconciliação | Item é marcado como resolvido/superado sem base suficiente | Exigir evidência concreta por tipo de entidade + registrar confiança + permitir `deferred` |
| Falso negativo | Item continua aberto/obsoleto porque a evidência não foi correlacionada | Regras híbridas por tipo + meetings como contexto de transição + fila de conflito |
| Reescrita destrutiva | Topic file perde contexto valioso ao ser reformatado | Arquivar versão anterior + escrever em arquivo temporário + validação estrutural antes de substituir |
| Conflito silencioso | Fontes discordam e o sistema escolhe uma sem registrar | Regra obrigatória: toda discordância relevante gera ledger + conflict queue |
| Ruído de meetings | Fala provisória vira “verdade atual” cedo demais | `R002_meeting_claim_needs_operational_confirmation` |
| Acúmulo de duplicatas | Mesma evidência reaplicada em ciclos diferentes | Idempotência por `entity_key` + hash de evidência + regra aplicada |
| Explicação fraca | Sistema muda algo mas o motivo fica opaco | Ledger obrigatório com `why`, evidências, regra, confiança e estado anterior |
| Escalonamento excessivo para revisão humana | Muitos conflitos irrelevantes saturam a fila | Taxonomia melhor de entidades + limiar de confiança + filtros por severidade |

---

## 18. Resiliência

O reconciliador deve nascer com proteções explícitas.

### 18.1 Execução segura
- lock por execução para evitar corridas;
- health check das dependências antes de reconciliar;
- processamento por tópico com isolamento de falhas;
- modo shadow/dry-run no início do rollout.

### 18.2 Escrita segura
- gerar snapshot e decisões antes de tocar no topic file;
- arquivar versão anterior;
- escrever em arquivo temporário;
- validar estrutura mínima do resultado;
- substituir via rename atômico apenas se válido.

### 18.3 Idempotência
- cada operação deve ter chave estável (`entity_key` + `rule_id` + `evidence_hash`);
- reexecutar o mesmo ciclo não deve duplicar decisão nem gerar diffs espúrios.

### 18.4 Degradação controlada
- se faltar fonte contextual (ex.: meetings), ainda é possível reconciliar parcialmente fatos operacionais;
- se faltar fonte canônica necessária para um tipo de entidade, o resultado deve ser `deferred`, nunca chute.

### 18.5 Observabilidade do próprio reconciliador
- correlação por `correlation_id`;
- relatório por execução;
- ledger append-only;
- contadores de aplicadas, adiadas, rejeitadas e conflituosas.

---

## 19. Métricas qualitativas

Além de contagens brutas, acompanhar sinais de qualidade da memória reconciliada.

### 19.1 Trustworthiness do topic file
Pergunta: “alguém consegue ler este arquivo e confiar no estado atual sem abrir cinco fontes?”

Indicadores:
- ausência de contradições internas;
- estado atual claramente separado do histórico;
- mudanças recentes com explicação legível.

### 19.2 Causal completeness
Pergunta: “para cada mudança relevante, o sistema responde o porquê?”

Indicadores:
- % de decisões com `why` suficiente;
- % de decisões com regra explícita;
- % de decisões com evidência concreta + contexto.

### 19.3 Freshness factual
Pergunta: “o estado atual do topic file acompanha a realidade?”

Indicadores:
- divergências detectadas entre topic file e fontes canônicas;
- idade da última confirmação de itens em `Status Atual`;
- % de jobs/modelos/crons confirmados no último ciclo.

### 19.4 Hygiene histórica
Pergunta: “o histórico continua útil sem contaminar o presente?”

Indicadores:
- bugs resolvidos ainda marcados como abertos;
- decisões superadas ainda tratadas como vigentes;
- pendências órfãs sem confirmação recente.

### 19.5 Review burden
Pergunta: “o sistema escala bem ou só empurra tudo para o humano?”

Indicadores:
- % de itens indo para conflito;
- % de conflitos considerados ruído na revisão;
- taxa de override humano das decisões automáticas.

### 19.6 Relevância das mudanças
Pergunta: “as mudanças automáticas melhoram o arquivo ou inserem ruído?”

Indicadores:
- taxa de entradas revertidas manualmente;
- taxa de duplicação detectada;
- percepção subjetiva do usuário sobre utilidade do arquivo reconciliado.

---

## 20. Recomendação final

Não evoluir apenas as heurísticas atuais.

A recomendação é introduzir um reconciliador estruturado com:
- snapshot factual por tópico;
- evidência normalizada;
- regras explícitas e versionadas;
- ledger causal append-only;
- reescrita por seções;
- meetings como contexto de transição e motivação.

Esse desenho resolve o problema central: a memória deixa de ser apenas um acúmulo textual e passa a ser uma representação reconciliada, auditável e explicável do que continua verdadeiro.
