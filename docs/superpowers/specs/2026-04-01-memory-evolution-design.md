# Spec — Consolidação Autogerenciável com Evolução Contínua

**Versão:** 1.0 — 2026-04-01
**Status:** Aprovado — em implementação

---

## 1. Conceito

O processo de consolidação evolui de **detecção passiva** para **pesquisa ativa + reescrita automática**.

A cada ciclo, o agente `livy-memory` pesquisa em todas as 3 camadas (built-in search, claude-mem, curated files), detecta o que está defasado ou violando o memory-manual, e reescreve os arquivos automaticamente — com arquivo antes, relatório depois.

**Regra de segurança: se qualquer dependência estiver down, o job falha e espera o próximo ciclo. Nunca roda com contexto incompleto.**

---

## 2. Arquitetura das 3 Camadas (input)

| Camada | Fonte | Formato | Disponibilidade |
|--------|-------|---------|----------------|
| Built-in memory search | `openclaw memory search` | Trechos scored | CLI local |
| claude-mem | `curl localhost:37777/api/*` | JSON (facts, narrative) | Worker Express na porta 37777 |
| Curated files | `MEMORY.md` + `memory/curated/*.md` | Markdown | Arquivos no workspace |

---

## 3. Fluxo de Execução

```
autoresearch_cron.py (a cada ciclo)
│
├── 0. HEALTH CHECK — todas as 3 camadas devem estar disponíveis
│   ├── openclaw memory status → OK
│   ├── curl localhost:37777/api/health → {"status":"ok"}
│   └── CURATED_DIR acessível
│   SE QUALQUER UMA FALHAR → ABORTA E ESPERA PRÓXIMO CICLO
│
├── 1. run_consolidation()          — detecta stale entries (existente)
│
├── 2. run_memory_evolution()       — NOVO
│   ├── Lista todos arquivos com violações
│   ├── Prioriza: stale>60d > violações estrutura > conteúdo
│   ├── Seleciona top 5 (round-robin se >5)
│   └── Para cada arquivo:
│       openclaw agent --agent livy-memory \
│         --message "<prompt de research+rewrite>"
│
├── 3. run_feedback_learning()       — existente
├── 4. run_dream()                   — existente
├── 5. run_meetings_tldv_autoresearch() — existente
│
└── 6. Reporta no Telegram
```

---

## 4. Fase 0 — Health Check (blocoante)

Antes de qualquer coisa, verifica todas as dependências:

```python
def health_check():
    """Se qualquer dependência estiver down, aborta o ciclo inteiro."""
    errors = []

    # Camada 1: openclaw memory
    r = subprocess.run(["openclaw", "memory", "status"],
                       capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        errors.append("openclaw memory: unreachable")

    # Camada 2: claude-mem worker
    try:
        r = requests.get("http://localhost:37777/api/health", timeout=5)
        if r.status_code != 200 or r.json().get("status") != "ok":
            errors.append("claude-mem worker: unhealthy")
    except:
        errors.append("claude-mem worker: unreachable")

    # Camada 3: curated dir
    if not CURATED_DIR.exists():
        errors.append("curated dir: not found")

    if errors:
        log(f"HEALTH CHECK FAILED: {'; '.join(errors)}. Abortando.")
        return False
    return True
```

**Se health_check() retornar False, o ciclo inteiro é abortado. Nenhuma evolução é aplicada. O relatório no Telegram menciona o falha.**

---

## 5. Fase 2 — Detecção de Violações

### Regras de validação

**Estrutura (memory-manual §7):**

| Regra | Detecção |
|-------|----------|
| YAML frontmatter com `name`, `description`, `type` | Regex `^---\n.*?\n---\n` + checa campos |
| Seção `Status` | Busca literal `## Status` ou `**Status:**` |
| Seção `Decisões` | Busca literal `## Decisões` ou `**Decisões:**` |
| Seção `Pendências` ou `Bugs` (se aplicável) | Busca literais |
| Arquivo em `curated/` não é daily log | Nome não match `YYYY-MM-DD` |

**Conteúdo (memory-manual §7):**

| Regra | Detecção |
|-------|----------|
| Decisões contêm motivo | Cada linha de decisão checada: tem `porque`, `motivo`, `razão`, `since`, `because`? |
| Status usa valores válidos | Regex `(ativo\|pausado\|concluído\|cancelado)` em linhas de Status |
| Arquivo não é só descrição sem conclusões | Seção Decisões existe mas está vazia ou tem só descrições |

### Priorização (top 5 por ciclo)

| Prioridade | Critério | Peso |
|---|---|---|
| 1 | stale > 60 dias | 10 |
| 2 | Sem YAML frontmatter | 8 |
| 3 | Sem seção Decisões | 6 |
| 4 | Seções faltantes (Status, Pendências) | 4 |
| 5 | Decisões sem motivo | 3 |
| 6 | Conteúdo só descrição (sem conclusões) | 2 |

Score final = soma dos pesos. Top 5 por ciclo.

**Round-robin:** mantém-se um cursor de qual arquivo foi procesado por último. Se hoje processou top 5, amanhã começa do 6º.

---

## 6. Fase 2b — Evolução via Agente

### Delegação

```bash
openclaw agent --agent livy-memory --message "<prompt>"
```

### Prompt delegado (research → rewrite)

```
Você é o agente de consolidação da memória institucional.

TAREFA: Reescreva o arquivo memory/curated/<nome>.md segundo o memory-manual.md.

ANTES de reescrever, pesquise em todas as 3 camadas para enriquecer o conteúdo:

1. CAMADA 1 (Built-in search):
   Execute: openclaw memory search --json "<tema do arquivo>"
   Leia os resultados mais relevantes

2. CAMADA 2 (claude-mem observations):
   Execute: curl "http://localhost:37777/api/search?query=<tema>&limit=5"
   Se IDs relevantes forem encontrados:
   - Execute: curl "http://localhost:37777/api/timeline?anchor=<id>&depth_before=2&depth_after=2"
   - Execute: curl -X POST "http://localhost:37777/api/observations/batch"
     -H "Content-Type: application/json"
     -d '{"ids": [<ids relevantes>],"orderBy":"date_desc"}'

3. CAMADA 3 (curated files):
   Leia MEMORY.md e arquivos relacionados em memory/curated/

REGRAS (memory-manual.md):
- YAML frontmatter com name, description, type
- Seções: Status, Decisões (com MOTIVO da escolha), Pendências, Bugs
- Status: ativo | pausado | concluído | cancelado
- NUNCA remova conteúdo existente — só reestruture e enriqueça
- Seções Decisões devem explicar o PORQUE de cada decisão

PASSOS OBRIGATÓRIOS:
1. Execute as pesquisas nas 3 camadas
2. Leia memory-manual.md para entender o formato ideal
3. ARQUIVE a versão original ANTES de qualquer modificação:
   mkdir -p .archive/$(date +%Y%m%d%H%M)
   cp <arquivo> .archive/$(date +%Y%m%d%H%M)/
4. Reescreva o arquivo integrando o contexto das 3 camadas
5. Retorne um relatório breve do que mudou e por quê
```

### Arquivamento

Antes de reescrever qualquer arquivo, o agente **must** архивировать a versão original:

```
.archive/YYYYMMDDHHMM/curated/<arquivo>.md
```

Se o agente não arquivar, a evolução não é considerada válida.

### Retorno do agente

O agente retorna um relatório em texto. Exemplo:

```
[EVOLUCAO] memory/curated/telegram-channel-disabled.md
- Adicionado YAML frontmatter
- Adicionada seção Decisões com base em 2 observações do claude-mem
- Status mantido: pausado
```

---

## 7. Output no Telegram

### Se health check falhar:

```
🧠 *Autoresearch — 2026-04-01 07:00 BRT*

⚠️ *Ciclo abortado — dependência down:*
• claude-mem worker: unreachable

🔄 Próximo ciclo em ~1h. Nenhuma evolução aplicada.
```

### Se health check passar e evoluções forem aplicadas:

```
🧠 *Autoresearch — 2026-04-01 07:00 BRT*

📊 *Métricas:* completeness 67.2 → 71.8 | crossrefs 12 → 15

🔄 *Evoluções aplicadas (5):*
• `memory/curated/telegram.md` — frontmatter adicionado + decisões com motivo
• `memory/curated/meetings-tldv.md` — reescrito com base em 3 claude-mem observations
• `memory/2026-03-15.md` — migrado para daily log (estava em curated)
• `memory/curated/agent-config.md` — consolidadas 2 entries duplicadas
• `memory/curated/openclaw-cli.md` — enriquecido com comandos descobertos

📋 *Resumo:* completeness +4.6 | crossrefs +3 | evoluções 5
🔄 *Próximo ciclo:* arquivos 6-10

📁 *3 arquivos para revisar:* [botões]
```

### Se nenhuma violação for encontrada:

```
🧠 *Autoresearch — 2026-04-01 07:00 BRT*

✅ *Health check: OK*
📊 *Métricas:* completeness 71.8 | crossrefs 15
✅ *Nenhuma violação detectada — nenhuma evolução necessária.*
```

---

## 8. Riscos e Mitigações

| Risco | Prob | Mitigação |
|---|---|---|
| claude-mem worker down | Média | Health check.aborta antes de qualquer coisa |
| openclaw memory down | Baixa | Health check.aborta |
| Agente reescreve com viés | Média | Regra "nunca remova conteúdo" + archive obrigatório antes |
| 5 arquivos por ciclo é muito | Baixa | Métricas no Telegram mostram impacto; cursor ajustável |
| Agent timeout (~60s por arquivo) | Média | 5 arquivos × 60s = 5min max; dentro do cron timeout |
| Cursor round-robin se perde após restart | Baixa | Cursor persiste em arquivo em `memory/.evolution_cursor` |

---

## 9. Resiliência

| Mecanismo | Como |
|---|---|
| **Fail-fast on dependency down** | Health check abrange as 3 camadas antes de qualquer coisa |
| **Lock file** | consolidate.py lock existente impede execuções concorrentes |
| **Per-file try/except** | Erro em um arquivo não para o loop dos outros 4 |
| **Archive antes de reescrever** | Obrigatório no prompt do agente; verificado no relatório |
| **Dry-run mode** | consolidate.py já suporta; evoluções podem ser testadas antes de aplicar |

---

## 10. Mudanças por Arquivo

| Arquivo | Mudança |
|---|---|
| `autoresearch_cron.py` | Nova função `run_memory_evolution()` + health check em `main()` |
| `consolidate.py` | Nova função `detect_violations()` com regras estrutura + conteúdo |
| `skills/memoria-consolidation/` | Nenhuma — o agente usa as ferramentas existentes dele |

---

## 11. Métricas de Sucesso

| Métrica | Como medir |
|---|---|
| completeness | autoresearch_metrics.py (já existente) |
| crossrefs | autoresearch_metrics.py (já existente) |
| violações resolvidas | Count de arquivos com violações antes vs depois |
| evoluções por ciclo | Log do agente |
| Health failures | Log do autoresearch_cron |

---

## 12. Checklist de Implementação

- [ ] `health_check()` em `autoresearch_cron.py`
- [ ] `detect_violations()` em `consolidate.py`
- [ ] `run_memory_evolution()` em `autoresearch_cron.py`
- [ ] Cursor round-robin com persistência
- [ ] Teste: claude-mem down → verifica que ciclo aborta
- [ ] Teste: arquivo com violações → verifica archive + reescrita
- [ ] Teste: 6+ violações → verifica que só top 5 é processado
