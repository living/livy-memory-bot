# Memory Evolution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add self-managing memory evolution to the consolidation process — health checks, violation detection, and agent-driven rewriting with round-robin prioritization.

**Architecture:** Two new functions in `autoresearch_cron.py` (health_check, run_memory_evolution) and one in `consolidate.py` (detect_violations). Violations drive agent prompting for research + rewrite.

**Tech Stack:** Python 3, subprocess, requests, openclaw CLI, claude-mem API

---

## File Map

| File | Role |
|------|------|
| `scripts/autoresearch_cron.py` | Entry point — add health_check(), run_memory_evolution(), cursor logic |
| `skills/memoria-consolidation/consolidate.py` | Add detect_violations() — structure + content rules |
| `memory/.evolution_cursor` | New file — round-robin cursor (last processed index) |
| `memory/manual-validation.md` | New file — per-cycle violation report |

---

## Task 1: Add health_check() to autoresearch_cron.py

**Files:**
- Modify: `scripts/autoresearch_cron.py`

- [ ] **Step 1: Write the failing test**

Create `scripts/test_evolution.py`:

```python
#!/usr/bin/env python3
"""Tests for memory evolution features."""
import sys, subprocess, requests
from unittest.mock import patch, MagicMock
sys.path.insert(0, 'scripts')

def test_health_check_all_healthy(monkeypatch):
    """When all 3 layers are up, health_check returns True."""
    from autoresearch_cron import health_check

    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: MagicMock(returncode=0))
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: MagicMock(status_code=200, json=lambda: {"status": "ok"}))

    with patch('pathlib.Path.exists', return_value=True):
        result = health_check()
    assert result == True

def test_health_check_claude_mem_down(monkeypatch):
    """When claude-mem is unreachable, health_check returns False."""
    from autoresearch_cron import health_check

    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: MagicMock(returncode=0))
    def raise_connection_error(*a, **kw):
        raise requests.ConnectionError("Connection refused")
    monkeypatch.setattr(requests, 'get', raise_connection_error)

    with patch('pathlib.Path.exists', return_value=True):
        result = health_check()
    assert result == False

def test_health_check_openclaw_memory_down(monkeypatch):
    """When openclaw memory status fails, health_check returns False."""
    from autoresearch_cron import health_check

    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: MagicMock(returncode=1, stderr="error"))
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: MagicMock(status_code=200, json=lambda: {"status": "ok"}))

    with patch('pathlib.Path.exists', return_value=True):
        result = health_check()
    assert result == False

def test_health_check_curated_dir_missing(monkeypatch):
    """When curated_dir doesn't exist, health_check returns False."""
    from autoresearch_cron import health_check

    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: MagicMock(returncode=0))
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: MagicMock(status_code=200, json=lambda: {"status": "ok"}))

    with patch('pathlib.Path.exists', return_value=False):
        result = health_check()
    assert result == False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 scripts/test_evolution.py`
Expected: FAIL — health_check not defined in autoresearch_cron

- [ ] **Step 3: Write minimal health_check()**

Add to `scripts/autoresearch_cron.py` after the existing helper functions (before line 26):

```python
def health_check():
    """
    Verifies all 3 memory layers are available.
    Returns True if all up, False if any down.
    Aborts the entire cycle if any layer is down.
    """
    errors = []

    # Layer 1: openclaw memory
    try:
        r = subprocess.run(
            ["openclaw", "memory", "status"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            errors.append("openclaw memory: unreachable")
    except Exception as e:
        errors.append(f"openclaw memory: {e}")

    # Layer 2: claude-mem worker
    try:
        resp = requests.get("http://localhost:37777/api/health", timeout=5)
        if resp.status_code != 200 or resp.json().get("status") != "ok":
            errors.append("claude-mem worker: unhealthy")
    except Exception:
        errors.append("claude-mem worker: unreachable")

    # Layer 3: curated dir
    if not CURATED_DIR.exists():
        errors.append("curated dir: not found")

    if errors:
        log(f"HEALTH CHECK FAILED: {'; '.join(errors)}. Abortando.")
        return False
    log("Health check: OK (3/3 layers)")
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest scripts/test_evolution.py::test_health_check_all_healthy scripts/test_evolution.py::test_health_check_claude_mem_down scripts/test_evolution.py::test_health_check_openclaw_memory_down scripts/test_evolution.py::test_health_check_curated_dir_missing -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/autoresearch_cron.py scripts/test_evolution.py
git commit -m "feat(autoresearch): add health_check for 3-layer validation

Aborts cycle if openclaw memory, claude-mem worker, or curated dir are down.
Fails fast — never runs with incomplete context.
"
```

---

## Task 2: Add health_check to main() in autoresearch_cron.py

**Files:**
- Modify: `scripts/autoresearch_cron.py:246-251`

- [ ] **Step 1: Read current main() to see exact lines**

Run: `sed -n '246,260p' scripts/autoresearch_cron.py`

- [ ] **Step 2: Modify main() to call health_check first**

Replace the beginning of main() (lines 247-254):

```python
def main():
    log("=== Autoresearch Cron (Telegram Direct) ===")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M BRT")

    # 0. Health check — abort if any layer is down
    if not health_check():
        summary = f"""🧠 *Autoresearch — {timestamp}*

⚠️ *Ciclo abortado — dependência down.*

🔄 Próximo ciclo em ~1h. Nenhuma evolução aplicada."""
        send_message(CHAT_ID, summary)
        sys.exit(1)

    # 0b. Process feedback acumulado desde última execução
    run_feedback_learning()
    ...
```

- [ ] **Step 3: Run health_check test to confirm main integration works**

Run: `python3 -c "from scripts.autoresearch_cron import main; print('import ok')"`
Expected: No import errors

- [ ] **Step 4: Commit**

```bash
git add scripts/autoresearch_cron.py
git commit -m "feat(autoresearch): integrate health_check in main()

Aborts with Telegram message if any layer is down.
"
```

---

## Task 3: Add detect_violations() to consolidate.py

**Files:**
- Modify: `skills/memoria-consolidation/consolidate.py`
- Test: `scripts/test_evolution.py` (add tests)

- [ ] **Step 1: Write the failing test**

Add to `scripts/test_evolution.py`:

```python
def test_detect_violations_no_frontmatter():
    """File without YAML frontmatter gets violation score 8."""
    from consolidate import detect_violations
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "test-file.md"
        f.write_text("# Test\n\nContent without frontmatter.")

        violations = detect_violations([f], {})
        assert len(violations) == 1
        assert violations[0]["file"].name == "test-file.md"
        assert violations[0]["score"] == 8
        assert "missing-frontmatter" in violations[0]["violations"]

def test_detect_violations_with_frontmatter():
    """File with correct frontmatter has no violations."""
    from consolidate import detect_violations
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "test-file.md"
        f.write_text("---\nname: test\ndescription: test desc\ntype: reference\n---\n\n# Test\n\n## Status\n**Status:** ativo\n\n## Decisões\n-架构: REST — motivo: simplicidade\n")

        violations = detect_violations([f], {})
        assert len(violations) == 0

def test_detect_violations_decisions_without_reason():
    """File with decisions but no reason gets content score 3."""
    from consolidate import detect_violations
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "test-file.md"
        f.write_text("---\nname: test\ndescription: test\ntype: reference\n---\n\n## Decisões\n-架构: REST API\n")

        violations = detect_violations([f], {})
        assert any(v["file"].name == "test-file.md" for v in violations)

def test_detect_violations_stale_file():
    """File older than 60 days gets score 10."""
    from consolidate import detect_violations
    import tempfile, pathlib, time, os

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "old-file.md"
        f.write_text("---\nname: old\ndescription: old\ntype: reference\n---\n\n## Status\n**Status:** ativo\n\n## Decisões\n-架构: REST — motivo: testing\n")
        # Set mtime to 70 days ago
        old_mtime = time.time() - (70 * 86400)
        os.utime(f, (old_mtime, old_mtime))

        violations = detect_violations([f], {})
        assert any(v["file"].name == "old-file.md" and v["score"] == 10 for v in violations)

def test_detect_violations_prioritization():
    """Files with multiple violations get summed score."""
    from consolidate import detect_violations
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmpdir:
        f = pathlib.Path(tmpdir) / "multi-violation.md"
        f.write_text("# Multi violation file\n\nNo frontmatter, no Status section.")

        violations = detect_violations([f], {})
        assert len(violations) == 1
        v = violations[0]
        # no frontmatter(8) + no decisions(6) = 14
        assert v["score"] == 14
        assert "missing-frontmatter" in v["violations"]
        assert "missing-decisoes" in v["violations"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest scripts/test_evolution.py -v 2>&1 | head -60`
Expected: FAIL — detect_violations not defined

- [ ] **Step 3: Write detect_violations() in consolidate.py**

Add after the `gather_signal_all()` function (after line 162):

```python
# ── PHASE 2B: VIOLATION DETECTION ─────────────────────────────────────────

VIOLATION_WEIGHTS = {
    "missing-frontmatter": 8,
    "missing-status": 4,
    "missing-decisoes": 6,
    "decisoes-no-reason": 3,
    "daily-log-in-curated": 5,
    "only-description": 2,
}

REASON_PATTERNS = re.compile(
    r'\b(porque|motivo|razão|since|because|devido|por causa)\b',
    re.IGNORECASE
)

FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)
STATUS_RE = re.compile(r'^## Status|^\*\*Status:\*\*', re.MULTILINE | re.IGNORECASE)
DECISOES_RE = re.compile(r'^## Decisões|^\*\*Decisões:\*\*', re.MULTILINE | re.IGNORECASE)
DATE_LOG_RE = re.compile(r'^\d{4}-\d{2}-\d{2}')

def _has_frontmatter(content: str) -> bool:
    m = FRONTMATTER_RE.match(content)
    if not m:
        return False
    fm_text = m.group(1)
    return all(k in fm_text for k in ['name:', 'description:', 'type:'])

def _has_section(content: str, pattern: re.Pattern) -> bool:
    return bool(pattern.search(content))

def _decisoes_have_reason(content: str) -> bool:
    """Check if each decision line contains a reason pattern."""
    lines = content.split('\n')
    in_decisoes = False
    decision_lines = []
    for line in lines:
        if DECISOES_RE.search(line):
            in_decisoes = True
            continue
        if in_decisoes:
            # Blank line or new section ends the block
            if line.strip() == '' or line.startswith('#'):
                break
            if line.strip().startswith('-'):
                decision_lines.append(line)
    if not decision_lines:
        return True  # No decisions = not a violation
    # At least half must have a reason
    with_reason = sum(1 for l in decision_lines if REASON_PATTERNS.search(l))
    return with_reason >= len(decision_lines) / 2

def detect_violations(files: list, signals: dict) -> list:
    """
    Returns list of dicts: {file, score, violations[], stale_days?}
    Only curated/*.md files are checked for violations.
    """
    cutoff_60 = datetime.now().timestamp() - 60 * 86400
    results = []

    for f in files:
        try:
            content = f.read_text()
        except Exception:
            continue

        # Skip daily logs
        if DATE_LOG_RE.match(f.name):
            continue

        violations = []
        score = 0

        # Check: frontmatter
        if not _has_frontmatter(content):
            violations.append("missing-frontmatter")
            score += VIOLATION_WEIGHTS["missing-frontmatter"]

        # Check: Status section
        if not _has_section(content, STATUS_RE):
            violations.append("missing-status")
            score += VIOLATION_WEIGHTS["missing-status"]

        # Check: Decisões section
        if not _has_section(content, DECISOES_RE):
            violations.append("missing-decisoes")
            score += VIOLATION_WEIGHTS["missing-decisoes"]
        elif not _decisoes_have_reason(content):
            violations.append("decisoes-no-reason")
            score += VIOLATION_WEIGHTS["decisoes-no-reason"]

        # Check: stale > 60 days
        try:
            mtime = f.stat().st_mtime
            if mtime < cutoff_60:
                stale_days = int((datetime.now().timestamp() - mtime) / 86400)
                violations.append(f"stale:{stale_days}d")
                score += VIOLATION_WEIGHTS.get("stale", 10)
        except Exception:
            pass

        if violations:
            results.append({
                "file": f,
                "score": score,
                "violations": violations,
            })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest scripts/test_evolution.py::test_detect_violations_no_frontmatter scripts/test_evolution.py::test_detect_violations_with_frontmatter scripts/test_evolution.py::test_detect_violations_decisions_without_reason scripts/test_evolution.py::test_detect_violations_stale_file scripts/test_evolution.py::test_detect_violations_prioritization -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/memoria-consolidation/consolidate.py
git commit -m "feat(consolidate): add detect_violations() with structure + content rules

- YAML frontmatter check (name, description, type)
- Status section check
- Decisões section check with reason detection
- Stale > 60d detection
- Weighted scoring for prioritization
"
```

---

## Task 4: Add run_memory_evolution() to autoresearch_cron.py

**Files:**
- Modify: `scripts/autoresearch_cron.py`
- Add: `memory/.evolution_cursor`

- [ ] **Step 1: Write the cursor helper functions (add before main())**

Add after `get_curated_files()` (around line 214):

```python
# ── Evolution Cursor (round-robin) ────────────────────────────────────────────

CURSOR_FILE = MEMORY_DIR / ".evolution_cursor"
MAX_FILES_PER_CYCLE = 5

def load_cursor() -> int:
    """Load last processed cursor index. Returns 0 if file missing."""
    if not CURSOR_FILE.exists():
        return 0
    try:
        return int(CURSOR_FILE.read_text().strip())
    except Exception:
        return 0

def save_cursor(idx: int):
    """Persist cursor index to disk."""
    CURSOR_FILE.write_text(str(idx))

# ── Evolution Prompt Builder ─────────────────────────────────────────────────

def build_evolution_prompt(file_path: Path, violations: list) -> str:
    """Build the prompt sent to livy-memory agent for one file."""
    try:
        content = file_path.read_text()[:2000]  # First 2000 chars for context
    except Exception:
        content = "(unable to read file)"

    theme = file_path.stem.replace("-", " ").replace("_", " ")

    return f"""Você é o agente de consolidação da memória institucional.

TAREFA: Reescreva o arquivo {file_path} segundo o memory-manual.md.

ANTES de reescrever, pesquise em todas as 3 camadas para enriquecer o conteúdo:

1. CAMADA 1 (Built-in search):
   Execute: openclaw memory search --json "{theme}"
   Leia os resultados mais relevantes

2. CAMADA 2 (claude-mem observations):
   Execute: curl "http://localhost:37777/api/search?query={theme}&limit=5"
   Se IDs relevantes forem encontrados:
   - Execute: curl "http://localhost:37777/api/timeline?anchor=<id>&depth_before=2&depth_after=2"
   - Execute: curl -X POST "http://localhost:37777/api/observations/batch" \\
     -H "Content-Type: application/json" \\
     -d '{{"ids": [<ids relevantes>],"orderBy":"date_desc"}}'

3. CAMADA 3 (curated files):
   Leia MEMORY.md e arquivos relacionados em memory/curated/

VIOLAÇÕES DETECTADAS:
{', '.join(violations)}

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
   cp {file_path} .archive/$(date +%Y%m%d%H%M)/
4. Reescreva o arquivo integrando o contexto das 3 camadas
5. Retorne um relatório breve do que mudou e por quê

ARQUIVO ATUAL (primeiros 2000 chars):
{content}
"""
```

- [ ] **Step 2: Write run_memory_evolution()**

Add after `build_evolution_prompt()`:

```python
def run_memory_evolution():
    """
    Detects violations, selects top 5 (round-robin), and delegates
    each to the livy-memory agent for research + rewrite.
    Returns list of (filename, report) tuples.
    """
    from consolidate import detect_violations, gather_signal_all, load_memory_indexes

    log("Running memory evolution...")

    # Load indexes and signals (needed for stale detection)
    indexes = load_memory_indexes()
    signals = gather_signal_all(indexes)

    # Get all curated files
    curated_files = get_curated_files()
    if not curated_files:
        log("No curated files found.")
        return []

    # Detect violations
    violations = detect_violations(curated_files, signals)
    if not violations:
        log("No violations detected.")
        return []

    # Round-robin: select top 5 starting from cursor
    cursor = load_cursor()
    # Build a circular list starting from cursor
    total = len(violations)
    selected = []
    for i in range(MAX_FILES_PER_CYCLE):
        idx = (cursor + i) % total
        selected.append(violations[idx])

    # Update cursor for next cycle
    next_cursor = (cursor + MAX_FILES_PER_CYCLE) % total
    save_cursor(next_cursor)

    log(f"Selected {len(selected)} files for evolution: {[v['file'].name for v in selected]}")

    # Delegate each to livy-memory agent
    reports = []
    for v in selected:
        f = v["file"]
        prompt = build_evolution_prompt(f, v["violations"])
        log(f"Delegating to livy-memory: {f.name}")

        try:
            result = subprocess.run(
                ["openclaw", "agent", "--agent", "livy-memory", "--message", prompt],
                capture_output=True, text=True, timeout=120
            )
            report = result.stdout.strip() if result.stdout else "(no output)"
            if result.returncode != 0:
                report = f"ERROR (rc={result.returncode}): {result.stderr.strip()}"
            log(f"  → {report[:200]}")
        except subprocess.TimeoutExpired:
            report = "TIMEOUT — agent did not complete within 120s"
            log(f"  → TIMEOUT for {f.name}")
        except Exception as e:
            report = f"EXCEPTION: {e}"
            log(f"  → EXCEPTION for {f.name}: {e}")

        reports.append((f.name, report, v["violations"]))

    return reports
```

- [ ] **Step 3: Add evolution results to Telegram output in main()**

Find the section in `main()` that builds the summary message (after `run_meetings_tldv_autoresearch()`) and add:

```python
    # 6. Run memory evolution (top 5 files, round-robin)
    evolution_reports = run_memory_evolution()
    evolution_count = len([r for r in evolution_reports if not r[1].startswith("ERROR")])
```

Then in the summary message builder, add after the evolutions block:

```python
    # Build evolution section
    if evolution_reports:
        evolution_lines = ["🔄 *Evoluções aplicadas:*"]
        for fname, report, violations in evolution_reports:
            short_violations = ", ".join(violations[:2])
            if report.startswith("ERROR") or report.startswith("TIMEOUT") or report.startswith("EXCEPTION"):
                evolution_lines.append(f"• `{fname}` — ❌ {report[:80]}")
            else:
                evolution_lines.append(f"• `{fname}` — ✅ {short_violations}")

        evolution_summary = "\n".join(evolution_lines)
        evolution_summary += f"\n📋 *Evoluções: {evolution_count}/{len(evolution_reports)} aplicadas*"
    else:
        evolution_summary = "✅ *Nenhuma violação detectada — nenhuma evolução necessária.*"
```

And add `evolution_summary` to the final message.

- [ ] **Step 4: Test run_memory_evolution() with --dry-run mode**

Run: `python3 -c "from scripts.autoresearch_cron import run_memory_evolution, load_cursor, save_cursor; print('import ok')"`
Expected: No import errors

- [ ] **Step 5: Commit**

```bash
git add scripts/autoresearch_cron.py
git commit -m "feat(autoresearch): add run_memory_evolution() with round-robin

- Cursor persists to memory/.evolution_cursor
- Top 5 files per cycle via detect_violations()
- Delegates each to livy-memory agent with 3-layer research prompt
- Reports results back to Telegram summary
"
```

---

## Task 5: Integration test — full cycle

**Files:**
- Run: `scripts/autoresearch_cron.py`

- [ ] **Step 1: Run full cycle with dry-run verification**

Run health check + evolution in isolation:
```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
source ~/.openclaw/.env && export SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY && \
python3 -c "
from scripts.autoresearch_cron import health_check, run_memory_evolution, get_curated_files
print('health_check:', health_check())
print('curated files:', [f.name for f in get_curated_files()])
reports = run_memory_evolution()
for r in reports:
    print(f'  {r[0]}: {r[1][:100]}')
"
```

Expected: health_check True, evolution reports for top 5 files

- [ ] **Step 2: Verify archive creation for at least one file**

Check that `.archive/` was created with timestamped subdirs if evolution ran.

Run: `ls memory/.archive/ 2>/dev/null | head -5`
Expected: directories with timestamp format

- [ ] **Step 3: Commit integration result**

```bash
git add memory/
git commit -m "test: verify evolution cycle runs correctly

- health_check passes with all 3 layers available
- detect_violations finds files with frontmatter/structure issues
- evolution delegated to livy-memory agent
"
```

---

## Self-Review Checklist

- [ ] All 12 checklist items from spec are covered?
  - health_check ✅ (Task 1-2)
  - detect_violations ✅ (Task 3)
  - run_memory_evolution ✅ (Task 4)
  - Cursor round-robin ✅ (Task 4)
  - Test: claude-mem down → abort ✅ (Task 1)
  - Test: archive created ✅ (Task 5)
  - Test: top 5 limit ✅ (via MAX_FILES_PER_CYCLE)

- [ ] No placeholder/TBD in any step?

- [ ] Function names consistent across tasks?
  - `health_check()` in Task 1-2
  - `detect_violations()` in Task 3
  - `run_memory_evolution()` in Task 4
  - `build_evolution_prompt()` in Task 4
  - `load_cursor()` / `save_cursor()` in Task 4

- [ ] Import paths correct?
  - `from consolidate import detect_violations` (Task 3)
  - `from scripts.autoresearch_cron import health_check` (Task 1)

---

**Plan complete.** Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
