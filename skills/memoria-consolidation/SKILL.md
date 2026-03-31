# Skill: memoria-consolidation

Usa scripts Python para executar Auto Dream adaptado e consolidação de memória.

## Scripts Disponíveis

```bash
# Consolidação básica (datas, stale, orphans)
python3 skills/memoria-consolidation/consolidate.py

# Métricas de qualidade
python3 skills/memoria-consolidation/autoresearch_metrics.py --all

# Dream — processa TODAS as memórias (memory-agent + main)
python3 skills/memoria-consolidation/dream_all.py
```

## Quando rodar

- **Manual**: a qualquer momento via cron ou sob demanda
- **Automático**:
  - `dream-memory-consolidation` (cron `dream`) — às 07h BRT, via main agent
  - `autoresearch-hourly` (cron `autoresearch`) — a cada hora, melhora qualidade
  - `memory-agent sonhar` — quando quiser processar todas as memórias

## Validação

Verificar `memory/consolidation-log.md` ou `memory/dream-signal.json` após execução.
