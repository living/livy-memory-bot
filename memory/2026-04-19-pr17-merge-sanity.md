# 2026-04-19 — PR #17 merge + sanity check

## Contexto
- Solicitação: verificar viabilidade de merge da PR #17, executar merge se viável e rodar sanity check de ponta a ponta.
- PR: https://github.com/living/livy-memory-bot/pull/17

## Ações executadas
1. Verificação de mergeabilidade da PR #17 (`mergeable=true`, `mergeable_state=clean`).
2. Merge realizado via squash:
   - Merge commit: `842852c86916eff5cf20b68cfc762a7a3f20872e`
3. Workspace sincronizado com `origin/master` (`git reset --hard origin/master`).
4. Sanity check pós-merge:
   - `python3 -m pytest tests/research/ -q`
   - Resultado: **321 passed**
5. Sanity operacional do cron `research-trello`:
   - Run manual via cron tool concluído com summary: `processed=390, skipped=0, status=success`
   - Observação: status final do job permanece `error` por **delivery** (`Delivering to Telegram requires target <chatId>`), não por falha no pipeline.

## Ajustes bloqueantes de review (já incorporados)
- Namespace em event key Trello: `trello:{action_id}`
- `state/identity-graph/self_healing_metrics.json` removido do versionamento (mantido como runtime artifact)

## Evidências
- PR merged: estado `MERGED` em `gh pr view 17`
- Testes: `321 passed in 2.81s`
- Cron runs: última execução manual registrada em `cron.runs(jobId=49d1d21e...)`
