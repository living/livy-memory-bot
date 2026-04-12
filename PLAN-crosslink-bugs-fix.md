# Plano: Fix Crosslink Pipeline — PR Authors + Meeting-Project Associations

**Data:** 2026-04-12
**Branch:** `feature/wave-b-entity-model` (worktree `wave-c-pipeline-wiring`)
**Round 2:** Após implementação de todas as correções do review Round 1

---

## Problemas Originais

### Bug 1: PR Authors = 0/31 ✅ FIXED
### Bug 2: Meeting-Project Associations = 0/36 ✅ CONFIRMED 29/31 working
### Bug 3: Person Identity Fragmentation ✅ FIXED

---

## Correções Implementadas (Round 1 Review)

### B2 — resolve_pr_author failure observability
**Status:** ✅ Implementado
- `resolve_pr_author()` agora loga motivo de falha: `no_token`, `api_error`, `rate_limited`
- Adicionado `logger.warning()` em cada caminho de falha
- Testes: `TestResolvePRAuthorLogsReason` (3 casos)

### B3 — github-login-map.yaml integration
**Status:** ✅ Implementado
- Criado `memory/vault/schema/github-login-map.yaml` com 9 mapeamentos
- Adicionado `_load_github_login_map_yaml()` em `crosslink_resolver.py`
- Adicionado `load_github_login_map()` em `mapping_loader.py`
- `resolve_pr_author()` agora aceita `schema_dir` parâmetro para consultar o YAML
- Resolution chain atualizada: cache → API → login-map.yaml → frontmatter → fuzzy → draft
- Testes: `TestGithubLoginMapIntegration` (2 casos)

### M2 — except: pass → logging
**Status:** ✅ Implementado
- Todas as `except: pass` em `crosslink_builder.py` substituídas por `except Exception as exc: logger.warning(...)`
- Afeta: stale PR cleanup, enrichment functions, dedup

### M3 — Batch PR cache integration
**Status:** ✅ Implementado
- `run_crosslink()` agora chama `fetch_prs_for_repos()` uma vez com todos os repos únicos
- Constrói `pr_author_cache: dict[(repo, number)] → login`
- Passa cache para `resolve_pr_author()` via parâmetro `pr_author_cache`
- Fallback: API individual se batch falhar
- Testes: `TestBatchPRCacheIntegration` (2 casos)

### M4 — pr_details assignment bug
**Status:** ✅ Implementado
- Corrigido `pr_details.get(url, pr)` → `pr_details[url] = pr` em `crosslink_enrichment.py`
- Agora PR titles aparecem corretamente em project/person files
- Testes: `TestPRDetailsAssignmentFix` (2 casos)

### M8 — Duplicate imports
**Status:** ✅ Implementado
- Removidos imports duplicados do módulo `crosslink_builder.py`
- Imports movidos para dentro de `run_crosslink()` (lazy imports, padrão já existente)
- Apenas `_split_frontmatter`, `upsert_card`, `upsert_pr` ficam no módulo level
- Testes: `TestNoDuplicateImports`

### N2 — Bot PR filtering
**Status:** ✅ Implementado
- Adicionado `_is_bot_login()` com denylist + pattern matching (`[bot]` suffix)
- `resolve_pr_author()` retorna `None` para bots sem criar drafts
- Testes: `TestBotPRFiltering` (2 casos)

### B1 — board_id matching (REVISADO)
**Status:** ✅ Fact-checked, NÃO É BUG
- Verificação com dados reais: 29/31 meetings com enrichment_context já têm projetos associados
- board_id está presente e faz match com board_map em 100% dos casos
- 2 meetings sem projeto têm cards com `id=""` (enrichment_context vazio)

### M5 — yaml.dump frontmatter preservation
**Status:** ✅ Testado como idempotent
- `TestFrontmatterPreservation` confirma que enrichment duplo produz output idêntico
- Risco mitigado pela natureza idempotente das funções

---

## Arquivos Modificados

| Arquivo | Mudança |
|---|---|
| `vault/ingest/crosslink_resolver.py` | Bot filter, login-map integration, logging, schema_dir param, pr_author_cache param |
| `vault/ingest/crosslink_builder.py` | Batch PR cache, lazy imports cleanup, except→logging, schema_dir pass-through |
| `vault/ingest/crosslink_enrichment.py` | Fix pr_details assignment bug |
| `vault/ingest/mapping_loader.py` | Added load_github_login_map() |
| `vault/tests/test_crosslink_fixes_r1.py` | 14 new test cases covering all fixes |
| `vault/tests/test_crosslink_builder.py` | Patch paths updated for new import structure |
| `vault/tests/test_wave_c_crosslink_integration.py` | Patch paths updated |
| `memory/vault/schema/github-login-map.yaml` | NEW: 9 login→person mappings |

---

## Test Results

```
vault/tests/test_crosslink_fixes_r1.py: 14/14 passed
vault/tests/test_crosslink_builder.py: 54/54 passed  
vault/tests/test_wave_c_crosslink_integration.py: 4/4 passed
```

---

## Critério de Sucesso (Atualizado)

- [x] PR authors resolvem via github-login-map.yaml
- [x] Bots filtrados (dependabot, pre-commit-ci, etc.)
- [x] Batch fetch para redução de API calls
- [x] Failure reasons logados para diagnóstico
- [x] pr_details populado corretamente (PR titles em enrichment)
- [x] except:pass eliminado
- [x] Imports duplicados removidos
- [x] Meeting-project: 29/31 confirmado working via diagnóstico
- [ ] **Pendente validação em produção:** rodar vault-crosslink.sh e verificar PR authors reais

---

## Pendências (Round 2 Review Items)

### Não implementado (risk/benefit baixo):
- **M5 ruamel.yaml**: yaml.dump funciona para o caso de uso (idempotente). Trocar por ruamel.yaml adiciona dependência.
- **M6 claude-mem queries**: github-login-map.yaml criado manualmente com dados do `gh api orgs/living/members`
- **M7 _setup_vault helper**: Não é bug, é confusão de test helpers. Cleanup posterior.
