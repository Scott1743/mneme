# Mneme Skill v2.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip the v2 independent-agent layer (Strands `@tool` decorators + `tools.py`/`ingest.py`/`query.py`/`lint.py`). Host agent (any skill-protocol LLM runtime) drives mneme via `SKILL.md`'s 6 scenarios using native tools. Thin `mneme.py` to `init` + `reindex` only.

**Architecture:** `SKILL.md` = single interface. Host agent reads it; per scenario, calls `okflib` / `indexlib` / `mneme.py` via native tools (Read/Write/Edit/Bash/Glob/Grep). L2 (sqlite-vec + fastembed) kept — solves context overflow. `mneme.py` keeps `init` + `reindex`. Dream cycle = scheduled host-agent session running the dream SKILL.md chapter with git snapshot/validate/dream-report guards.

**Tech Stack:** Python 3.10+, stdlib (okflib, mneme.py, validate_okf.py), sqlite-vec + fastembed (indexlib, dev/test extras), pytest.

## Global Constraints

- **No independent agent runtime.** Delete `skills/mneme/scripts/tools.py`, `ingest.py`, `query.py`, `lint.py` and their tests. No Strands `@tool`, no `Agent(...)`, no separate agent processes.
- **`mneme.py` keeps only `init` and `reindex`.** Remove `cmd_ingest/query/lint`. Tests adapt accordingly.
- **`SKILL.md` rewritten:** 6 scenarios (init / reindex / ingest / query / lint / dream) guiding the host agent with native tools only (`Read`/`Write`/`Edit`/`Bash`/`Glob`/`Grep`).
- **`pyproject.toml` `[agents]` extra removed.** Keep `[dev]`, `[index]` (sqlite-vec + fastembed), `[all]` = `[index]` only.
- **dream is fully automatic** (it's a scheduled task, no user interaction). Soft cap `max_dream_changes_per_run = 20`. Git is the safety net — pre-dream snapshot, post-dream validate, `dream-report-<date>.md`. Graceful degradation when bundle isn't a git repo (warn, continue without git ops).
- **Branch:** `feat/skill-v2_1` (from `main`). Keep `upstream/` in `.research/` read-only.
- **Test discipline:** keep `tests/test_okflib.py`, `tests/test_indexlib.py`, `tests/test_integration.py`. Delete `tests/test_tools.py`, `tests/test_agents_smoke.py`, `tests/test_cli.py` (rewrite as init/reindex-only).

## File Structure

```
skills/mneme/
├── SKILL.md                           # REWRITE (Phase D, Tasks D1–D2)
├── scripts/
│   ├── okflib.py                      # keep (L1)
│   ├── indexlib.py                    # keep (L2)
│   ├── validate_okf.py                # keep (L1 CLI)
│   ├── mneme.py                       # SIMPLIFY (Phase A, Task A2)
│   ├── tools.py                       # DELETE (Phase A, Task A1)
│   ├── ingest.py                      # DELETE (Phase A, Task A1)
│   ├── query.py                       # DELETE (Phase A, Task A1)
│   └── lint.py                        # DELETE (Phase A, Task A1)
└── references/
    ├── workflow-ingest.md             # REWRITE (Phase E, Task E1)
    ├── workflow-query.md              # REWRITE (Phase E, Task E1)
    ├── workflow-lint.md               # REWRITE (Phase E, Task E1)
    ├── type-vocab.md                  # keep
    ├── wiki-structure.md              # keep
    └── index-design.md                # keep
tests/
├── test_okflib.py                     # keep
├── test_indexlib.py                   # keep
├── test_integration.py                # keep
├── conftest.py                        # keep (sys.path bootstrap)
├── test_cli.py                        # REWRITE for init+reindex (Phase A, Task A2)
├── test_tools.py                      # DELETE (Phase A, Task A1)
└── test_agents_smoke.py               # DELETE (Phase A, Task A1)
pyproject.toml                        # EDIT (Phase A, Task A1 — drop `[agents]`)
```

**Responsibilities:**
- `SKILL.md`: 6 prose scenarios guiding host agent.
- `okflib.py`: stdlib, OKF parse/validate/list — adds `.mneme/` skip (already done in v2 A0).
- `indexlib.py`: sqlite-vec + fastembed, chunk/upsert/remove/search/reindex (kept from v2).
- `validate_okf.py`: thin CLI on okflib.
- `mneme.py`: CLI dispatcher. `init` scaffolds OKF bundle + writes config. `reindex` rebuilds L2.
- `references/`: ingest/query/lint workflows rewritten as host-agent guidance (no `mneme <cmd>`).

---

<!-- PLAN-V2-1-PART-2 -->

## Phase A — remove independent-agent layer

### Task A1: delete Strands agent scripts + their tests; drop `[agents]` extra

**Files:** delete `skills/mneme/scripts/tools.py`, `ingest.py`, `query.py`, `lint.py`, `tests/test_tools.py`, `tests/test_agents_smoke.py`. Edit `pyproject.toml`.

- [ ] **Step 1: delete the four Strands agent scripts**

```bash
cd /Users/scott1743/opc/mneme
rm -f skills/mneme/scripts/tools.py \
      skills/mneme/scripts/ingest.py \
      skills/mneme/scripts/query.py \
      skills/mneme/scripts/lint.py
rm -f tests/test_tools.py \
      tests/test_agents_smoke.py
```

- [ ] **Step 2: confirm deletion**

```bash
ls skills/mneme/scripts/
ls tests/
```

Expected: `scripts/` has only `okflib.py`, `indexlib.py`, `validate_okf.py`, `mneme.py`. `tests/` has `test_okflib.py`, `test_indexlib.py`, `test_integration.py`, `conftest.py`, `test_cli.py` (the old v2 cli test, to be rewritten in A2).

- [ ] **Step 3: drop `[agents]` from `pyproject.toml`**

```bash
grep -nE "agents" pyproject.toml
```

If a line containing `agents = ["strands-agents", "strands-agents-tools"]` exists under `[project.optional-dependencies]`, delete it. Update `[all]` from `"sqlite-vec", "fastembed", "strands-agents", "strands-agents-tools"` to `"sqlite-vec", "fastembed"`. Final state:

```toml
[project.optional-dependencies]
dev = ["pytest"]
index = ["sqlite-vec", "fastembed"]
all = ["sqlite-vec", "fastembed"]
```

Use the `Edit` tool on `pyproject.toml` to make this change.

- [ ] **Step 4: run full test suite**

```bash
cd /Users/scott1743/opc/mneme
.venv/bin/pytest -q 2>&1 | tail -5
```

Expected: tests fail to collect or run because `test_cli.py` imports modules that referenced deleted files. Expect failures / collection errors at this point — this is expected; Task A2 rewrites `test_cli.py` to match the new `mneme.py` shape.

- [ ] **Step 5: commit the deletions + pyproject edit**

```bash
git checkout -b feat/skill-v2_1
git add -A
git commit -m "refactor: remove Strands agent layer (tools/ingest/query/lint) + drop [agents] extra

All write paths now flow through the host agent driven by SKILL.md's
6 scenarios. Independent agent runtime + Strands @tool decorators
removed. pyproject.toml drops strands-agents (kept only in local
dev/test installs, not as a runtime extra).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### Task A2: simplify `mneme.py` to `init` + `reindex`; rewrite `tests/test_cli.py`

**Files:** Edit `skills/mneme/scripts/mneme.py`. Replace `tests/test_cli.py`.

- [ ] **Step 1: replace `mneme.py`**

Write `skills/mneme/scripts/mneme.py` to contain **only** `init` and `reindex` (delete `cmd_ingest`, `cmd_query`, `cmd_lint`, and the dict dispatch over them):

```python
#!/usr/bin/env python3
"""mneme CLI: init / reindex.

The other operations (ingest / query / lint / dream) are SKILL.md-driven
host-agent workflows — they don't need CLI subcommands. This CLI is for
manual / scripted use of the two stateful operations only.
"""
from __future__ import annotations

import sys
from pathlib import Path

CONFIG_DEFAULT = Path.home() / ".config" / "mneme" / "config.toml"


def _write_config(bundle_path: Path, config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(f'bundle_path = "{bundle_path}"\n', encoding="utf-8")


def cmd_init(args) -> int:
    if not args:
        print("usage: mneme init <path> [--config <cfg>]", file=sys.stderr)
        return 2
    bundle = Path(args[0])
    config = Path(args[args.index("--config") + 1]) if "--config" in args else CONFIG_DEFAULT
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "sources").mkdir(exist_ok=True)
    (bundle / "sources" / ".gitkeep").write_text("")
    if not (bundle / "index.md").exists():
        (bundle / "index.md").write_text('---\nokf_version: "0.1"\n---\n\n# Concepts\n', encoding="utf-8")
    if not (bundle / "log.md").exists():
        (bundle / "log.md").write_text("# Directory Update Log\n", encoding="utf-8")
    _write_config(bundle, config)
    print(f"initialized bundle at {bundle}; recorded in {config}")
    return 0


def cmd_reindex(args) -> int:
    config = Path(args[args.index("--config") + 1]) if "--config" in args else CONFIG_DEFAULT
    sys.path.insert(0, str(Path(__file__).parent))
    from tools_helpers import resolve_bundle  # see note below
    bundle = resolve_bundle(config_path=config)
    if bundle is None:
        print("no bundle found", file=sys.stderr)
        return 1
    import indexlib
    n = indexlib.reindex_bundle(str(bundle), indexlib.default_embed_fn())
    print(f"indexed {n} concepts into {bundle}/.mneme/index.db")
    return 0
```

> **Implementation note on `resolve_bundle`:** The previous v2 implementation imported `resolve_bundle` from `tools.py`. Since `tools.py` is deleted in A1, extract `resolve_bundle` into a tiny helper module — see Task A3.

- [ ] **Step 2: write failing `test_cli.py`**

Replace `tests/test_cli.py` entirely:

```python
import sys
from pathlib import Path

import mneme


def test_init_scaffolds_bundle_and_config(tmp_path):
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "mywiki"
    rc = mneme.main(["init", str(bundle), "--config", str(cfg)])
    assert rc == 0
    assert (bundle / "index.md").exists()
    assert (bundle / "log.md").exists()
    assert (bundle / "sources").is_dir()
    assert "okf_version" in (bundle / "index.md").read_text()
    assert f'bundle_path = "{bundle}"' in cfg.read_text()


def test_reindex_uses_injected_embed(tmp_path, monkeypatch):
    sample = Path(__file__).parent.parent / "sample-bundle"
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'bundle_path = "{sample}"\n')
    import indexlib
    from test_indexlib import fake_embed
    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: (lambda ts: fake_embed(ts, 8)))
    rc = mneme.main(["reindex", "--config", str(cfg)])
    assert rc == 0
    assert (sample / ".mneme" / "index.db").exists()


def test_unknown_command_returns_2(tmp_path):
    rc = mneme.main(["bogus", "arg"])
    assert rc == 2


def test_no_args_returns_2():
    rc = mneme.main([])
    assert rc == 2
```

- [ ] **Step 3: run `test_cli.py` — expect IMPORT ERROR** because `mneme.py` imports `from tools_helpers import resolve_bundle` (doesn't exist yet).

```bash
cd /Users/scott1743/opc/mneme
.venv/bin/pytest tests/test_cli.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'tools_helpers'`. (Task A3 creates it.)

- [ ] **Step 4: write failing `test_tools_helpers.py`**

Create `tests/test_tools_helpers.py`:

```python
from pathlib import Path
from tools_helpers import resolve_bundle, slug_from_path


def test_resolve_bundle_from_config(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('bundle_path = "/tmp/mywiki"\n')
    assert resolve_bundle(config_path=cfg) == Path("/tmp/mywiki")


def test_resolve_bundle_env_fallback(tmp_path, monkeypatch):
    cfg = tmp_path / "none.toml"
    monkeypatch.setenv("MNEME_BUNDLE", "/env/wiki")
    assert resolve_bundle(config_path=cfg) == Path("/env/wiki")


def test_slug_from_path():
    assert slug_from_path("My Note.md") == "my-note"
```

- [ ] **Step 5: create `skills/mneme/scripts/tools_helpers.py`** (extracted from old `tools.py`)

```python
"""Plain helper functions used by mneme.py. No Strands @tool decorators.

(Old tools.py mixed these plain helpers with @tool-decorated wrappers.
The @tool wrappers were removed when independent agents were deleted in v2.1;
the helpers are still needed by mneme.py CLI dispatch.)
"""
from __future__ import annotations

import os
import re
from pathlib import Path


def slug_from_path(path) -> str:
    base = Path(path).stem
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")


def resolve_bundle(config_path=None):
    if config_path is None:
        config_path = Path.home() / ".config" / "mneme" / "config.toml"
    config_path = Path(config_path)
    if config_path.exists():
        for line in config_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("bundle_path"):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return Path(val)
    env = os.environ.get("MNEME_BUNDLE")
    if env:
        return Path(env)
    import okflib
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        idx = d / "index.md"
        if idx.exists():
            parsed = okflib.parse_frontmatter(idx.read_text(encoding="utf-8"))
            if parsed and parsed[0].get("okf_version"):
                return d
    wiki = Path.cwd() / "wiki"
    return wiki if wiki.exists() else None
```

- [ ] **Step 6: run full suite — all green**

```bash
cd /Users/scott1743/opc/mneme
.venv/bin/pytest -q 2>&1 | tail -5
```

Expected: 30 + 3 skipped = 33 tests pass (existing okflib 15 + indexlib 9 + integration 1 + new test_cli 4 + test_tools_helpers 3 + 3 agent smoke skipped). Actually 32 + 3 skipped.

- [ ] **Step 7: commit**

```bash
git add skills/mneme/scripts/mneme.py skills/mneme/scripts/tools_helpers.py tests/test_cli.py tests/test_tools_helpers.py
git commit -m "refactor: thin mneme.py to init + reindex; extract plain helpers

tools_helpers.py holds the resolve_bundle / slug_from_path helpers
formerly in tools.py. mneme.py keeps only init + reindex (ingest/query/lint
moved to SKILL.md as host-agent workflows). test_cli.py rewritten for the
two remaining subcommands.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### Task A3: cleanup transient artifacts + verify

- [ ] **Step 1: ensure no stray references to deleted modules**

```bash
cd /Users/scott1743/opc/mneme
grep -rln "from tools import\|from ingest import\|from query import\|from lint import" skills/mneme/ tests/ docs/ 2>/dev/null || echo "(clean)"
grep -rln "@tool\|strands" skills/mneme/ tests/ docs/ 2>/dev/null || echo "(clean)"
```

Expected: both `(clean)`.

- [ ] **Step 2: final A-phase test run**

```bash
cd /Users/scott1743/opc/mneme
.venv/bin/pytest -q 2>&1 | tail -3
```

Expected: 32 + 3 skipped, all green.

## Phase B–C — skipped (no change)

The L1 (`okflib.py`) and L2 (`indexlib.py`) modules from v2 are unchanged in v2.1. No B/C tasks.

## Phase D — rewrite SKILL.md (6 scenarios)

### Task D1: write the 6-scenario SKILL.md (part 1: frontmatter + intro + 4 scenarios)

**Files:** Replace `skills/mneme/SKILL.md`.

- [ ] **Step 1: write the new SKILL.md**

Write `skills/mneme/SKILL.md`:

```markdown
---
name: mneme
description: "Maintain a local, OKF-conformant LLM knowledge wiki of research/learning notes. Use when the user wants to ingest a source into their wiki, query the wiki, lint it for OKF conformance, run a scheduled maintenance cycle (dream), or initialize a new wiki. Triggers: 'mneme', 'my wiki', 'ingest this', 'query my notes', 'lint the wiki', 'dream', 'knowledge base', '查 wiki', '摄入笔记', '知识库'."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

# mneme — lightweight LLM wiki

You drive all mneme operations through native tools (Read/Write/Edit/Bash/Glob/Grep) plus a thin CLI (`mneme init` / `mneme reindex`). **Never** call any independent agent SDK or `@tool` framework — your native tools ARE the agent runtime.

mneme keeps an external OKF v0.1 wiki of research/learning notes. The skill has 6 scenarios; pick the one matching the user's intent.

## Step 0: resolve the bundle (EVERY scenario)

Find the wiki bundle in this order; use the first hit:
1. `~/.config/mneme/config.toml` key `bundle_path`.
2. `MNEME_BUNDLE` env var.
3. An explicit path the user gave.
4. Auto-discover: walk up from cwd for a root `index.md` whose frontmatter contains `okf_version`.
5. `./wiki` if it exists.
6. None found → ask the user for the path, or offer to run `init`.

Helper: `Bash: python3 -c "import sys; sys.path.insert(0,'./skills/mneme/scripts'); from tools_helpers import resolve_bundle; print(resolve_bundle())"`

> **Skill-relative paths:** paths like `scripts/validate_okf.py` are relative to this skill's own directory (the folder containing this SKILL.md). Run them from there.

## OKF v0.1 conformance (hard rules — never violate on write)

1. Every non-reserved `.md` MUST have a `---`-delimited YAML frontmatter block.
2. Every frontmatter MUST have a non-empty `type`.
3. Reserved `index.md` (no frontmatter except root `okf_version`) and `log.md` (date-prefixed timeline) follow their structure.

Do NOT reject unknown `type` values, extra frontmatter keys, or broken links — warnings only.

## type vocab (recommended, non-registered)

`Concept` (idea/topic) · `Reference` (distilled external source) · `Summary` (synthesis) · `Source` (raw doc in sources/).

## Scenario: init <path>

Scaffold an OKF bundle + record its location:

1. `Bash: python3 skills/mneme/scripts/mneme.py init <path> [--config <cfg>]` (paths relative to cwd; if absent, `--config` defaults to `~/.config/mneme/config.toml`).
2. Verify: `<path>/index.md` has `okf_version: "0.1"`, `<path>/log.md` exists, `<path>/sources/.gitkeep` exists.
3. Confirm to the user; the bundle path is now discoverable via Step 0.

## Scenario: reindex [--config <cfg>]

Rebuild the L2 sqlite-vec index from scratch:

1. `Bash: python3 skills/mneme/scripts/mneme.py reindex [--config <cfg>]`
2. Confirm the output: `indexed N concepts into <bundle>/.mneme/index.db`.

After every `ingest` or `dream` that adds/removes/merges pages, run `reindex`.

## Scenario: ingest <source path>

Distill a source (paper/article/note) into OKF concept pages:

1. `Read <source path>` to get the full text.
2. Decide how to decompose into concept pages (one page per atomic idea; one source may yield 1–15 pages).
3. For each page:
   - `Write <bundle>/concepts/<slug>.md` with frontmatter (`type`/`title`/`description`/`tags`/`timestamp`/`resource`) + body.
   - Cross-link related pages with absolute bundle-relative paths (`/concepts/other.md`).
4. `Edit <bundle>/index.md` — add `* [Title](path) - description` under the right section (use `update_index_md`-style logic if a section already exists; otherwise append under `# Concepts`).
5. `Edit <bundle>/log.md` — append `## YYYY-MM-DD ingest | <source title>` + one-line note.
6. `Bash: python3 skills/mneme/scripts/mneme.py reindex` (or directly `python3 -c "import sys,indexlib; sys.path.insert(0,'skills/mneme/scripts'); ...; indexlib.reindex_bundle(bundle, indexlib.default_embed_fn())"`).
7. **Fallback:** if `fastembed` cannot download the model, retry with the **fake embed_fn** pattern from `tests/test_indexlib.py` (hash-based, no model). Only acceptable for tests — surface to the user that production reindex needs `pip install 'mneme[index]'`.

See `references/workflow-ingest.md` for the detailed checklist.

## Scenario: query <question>

Naive RAG: embed → KNN → top-k → read pages → synthesize answer with citations:

1. `Bash: python3 -c "import sys; sys.path.insert(0,'skills/mneme/scripts'); import indexlib; c = indexlib.open_index('<bundle>/.mneme/index.db'); print(indexlib.search(c, '<question>', k=10, embed_fn=indexlib.default_embed_fn()))"`
2. For each top chunk, `Read <bundle>/<chunk.path>` (use `concept_id` from the search result to derive path: `concepts/foo` → `concepts/foo.md`).
3. Synthesize an answer with **inline citations** as bundle-relative markdown links: `[/concepts/foo.md]([/concepts/foo.md)`.
4. If the answer is broadly useful and no page covers it, OFFER (do not auto-write) to backfill it as a new `Summary` page.
5. Honest about gaps: if the wiki lacks coverage, say so and suggest an `ingest`.

See `references/workflow-query.md`.

## Scenario: lint

Curate + report (do **not** auto-modify):

1. `Bash: python3 skills/mneme/scripts/validate_okf.py <bundle>` — read ERRORs (must fix) and WARNings.
2. `Bash: python3 -c "import sys; sys.path.insert(0,'skills/mneme/scripts'); import okflib; print(okflib.find_orphans('<bundle>'))"` — orphan concept IDs (not linked from anywhere).
3. Read a sample of pages; look for contradictions / stale timestamps / missing cross-links.
4. Write a curated report to `<bundle>/lint-report-<date>.md` (do **not** modify files; let the user decide).

See `references/workflow-lint.md`.

## Scenario: dream (scheduled, fully automatic)

Auto-curate + maintain quality. **No user interaction** — this is a scheduled task.

**Pre-guard:**
1. `Bash: git rev-parse --git-dir --git-dir 2>/dev/null || echo NOGIT`. If not a git repo, log a warning and skip git ops (still run curation + report).
2. If git: `Bash: git add -A && git commit -m "pre-dream $(date +%Y-%m-%dT%H:%M)" --allow-empty` (capture the commit SHA into a variable for the report).
3. Resolve the bundle (Step 0).

**Core loop (cap: `max_dream_changes_per_run=20` — soft env var; default 20):**

| Action | Implementation |
|---|---|
| Merge duplicates | `Bash: python3 -c "import sys; sys.path.insert(0,'skills/mneme/scripts'); ..."` calling `indexlib.search(... k=20)` then grouping pairs with cosine distance ≤ 0.08 (i.e. similarity ≥ 0.92). Pick the merge target per pair. |
| Archive orphans | Call `okflib.find_orphans`. For each orphan with `timestamp` ≥ 90 days ago and zero log references: move to `archive/YYYY/`. |
| Add cross-links | For each orphan or low-link page, find the most-similar linked page via `indexlib.search`; add `[/concepts/X.md](/concepts/X.md)` to its body. |
| Build Summary | For each topic with ≥ 5 concepts, `Write` a new `<bundle>/summaries/<topic>.md` (type: Summary) with synthesized overview + links. |
| Reindex | `Bash: python3 skills/mneme/scripts/mneme.py reindex` (after all writes). |

**Atomic write protocol:** write every new/modified file to `<bundle>/.mneme/dream-pending/` first, then `Bash: cp` (or `git mv`) into place. If anything fails, the pending dir is the audit trail; the bundle stays unchanged.

**Post-guard:**
1. `Bash: python3 skills/mneme/scripts/validate_okf.py <bundle>` — must be 0 ERROR. If ERRORs, abort the commit and write a critical section to the report.
2. `Bash: git add -A && git commit -m "dream: $(date +%Y-%m-%d) [skip ci]" --author="mneme dream <dream@localhost>"` — commit the changes.
3. Capture the new commit SHA.

**Report:** `Write <bundle>/dream-report-<date>.md`:

```markdown
# dream report — YYYY-MM-DD

## Summary
- Changes: N (cap was 20)
- pre-dream SHA: <sha>
- post-dream SHA: <sha>

## Changes
1. [merge] concepts/foo.md + concepts/bar.md → concepts/foo.md (similarity 0.94)
2. [archive] concepts/old.md → archive/2025/old.md (timestamp 245d, no log refs)
3. [link] concepts/x.md ↔ concepts/y.md
4. ...

## Validation
- validate: 0 ERROR / N WARN
- reindex: <bundle>/.mneme/index.db (M concepts)

## Revert
git revert <post-dream-SHA>
```

**If git is unavailable:** skip the commit step; the report still gets written; warn the user that there's no easy rollback.

## references (load on demand)

`scripts/validate_okf.py` (validator) · `references/workflow-ingest.md` · `references/workflow-query.md` · `references/workflow-lint.md` · `references/type-vocab.md` · `references/wiki-structure.md` · `references/index-design.md`.

OKF spec: <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>.
```

- [ ] **Step 2: verify SKILL.md has all six scenarios**

```bash
cd /Users/scott1743/opc/mneme
grep -c "^## Scenario:" skills/mneme/SKILL.md
grep -E "^## Scenario:" skills/mneme/SKILL.md
```

Expected: count `6`; the six headings: `init`, `reindex`, `ingest`, `query`, `lint`, `dream`.

- [ ] **Step 3: commit**

```bash
git add skills/mneme/SKILL.md
git commit -m "feat(skill): rewrite SKILL.md for v2.1 (host-agent driven, 6 scenarios)

Removes the mneme ingest/query/lint CLI forwarding; host agent now
drives ingest/query/lint directly via native tools (Read/Write/Edit/Bash)
plus okflib/indexlib Python modules. Adds dream scenario with git
pre-snapshot + validate post-guard + dream-report-<date>.md + soft cap
max_dream_changes_per_run=20.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

## Phase E — rewrite workflow reference docs

### Task E1: rewrite `workflow-ingest.md`, `workflow-query.md`, `workflow-lint.md`

**Files:** Modify the three reference docs.

- [ ] **Step 1: rewrite `skills/mneme/references/workflow-ingest.md`**

```markdown
---
type: Reference
title: mneme ingest workflow (host-agent)
description: Detailed checklist for the ingest scenario in SKILL.md.
---
# ingest workflow (host-agent)

The ingest scenario in SKILL.md guides the host agent through these steps. This doc is the detailed checklist — read it before doing a non-trivial ingest.

1. **Read** the source file end-to-end.
2. **Decompose** into concept pages:
   - One page per atomic idea (one source can yield 1–15 pages).
   - Choose `type` per page (Concept / Reference / Summary / Source).
   - Slug = lowercase, non-alnum→hyphen.
3. **Write** each page to `<bundle>/concepts/<slug>.md`:
   ```yaml
   ---
   type: Concept
   title: <display>
   description: <one-line>
   tags: [<t1>, <t2>]
   timestamp: <ISO 8601>
   resource: <source path>
   ---
   <body>
   ```
4. **Cross-link** related pages with `/concepts/<slug>.md`.
5. **Edit `<bundle>/index.md`** — add `* [Title](path) - description` under `# Concepts`.
6. **Edit `<bundle>/log.md`** — append `## YYYY-MM-DD ingest | <source title>` + one-line note.
7. **Reindex**: `Bash: python3 skills/mneme/scripts/mneme.py reindex`.
8. **Validate**: `Bash: python3 skills/mneme/scripts/validate_okf.py <bundle>` — must be 0 ERROR.

If `fastembed` model download fails, see `references/index-design.md` §Embedding for the fake-embed-fn fallback (tests only).
```

- [ ] **Step 2: rewrite `skills/mneme/references/workflow-query.md`**

```markdown
---
type: Reference
title: mneme query workflow (host-agent)
description: Detailed checklist for the query scenario in SKILL.md.
---
# query workflow (host-agent)

The query scenario in SKILL.md is naive RAG: embed → KNN → top-k → read → synthesize with citations.

1. **Embed** the question (fastembed, default `intfloat/multilingual-e5-small` 384-dim).
2. **KNN** via sqlite-vec `indexlib.search(conn, query, k=10, embed_fn=...)`.
3. **Read** each top chunk's full concept page.
4. **Synthesize** an answer with **inline citations** as bundle-relative links: `[/concepts/foo.md]([/concepts/foo.md)`.
5. **Honest gaps**: if the wiki lacks coverage, say so and recommend `ingest`.
6. **Backfill offer**: if your synthesized answer is broadly useful and no page covers it, OFFER to write it as a new `Summary` page (ask first; do not auto-write).
```

- [ ] **Step 3: rewrite `skills/mneme/references/workflow-lint.md`**

```markdown
---
type: Reference
title: mneme lint workflow (host-agent)
description: Detailed checklist for the lint scenario in SKILL.md.
---
# lint workflow (host-agent)

The lint scenario in SKILL.md curates without auto-modifying. This doc is the detailed checklist.

1. **Validate**: `Bash: python3 skills/mneme/scripts/validate_okf.py <bundle>` — must be 0 ERROR.
2. **Find orphans**: `Bash: python3 -c "import sys; sys.path.insert(0,'skills/mneme/scripts'); import okflib; print(okflib.find_orphans('<bundle>'))"`.
3. **Sample review**: read a handful of pages; look for:
   - Stale `timestamp` with no log reference
   - Contradictions between related pages
   - Missing cross-links between topics that share concepts
   - Pages that drifted into `archive/` candidates
4. **Write** the curated report to `<bundle>/lint-report-<date>.md` — **do not** modify the wiki files.

If the user approves follow-up changes, run them as `ingest` (for additions) or via explicit `Write`/`Edit` (for curations), not via lint.
```

- [ ] **Step 4: commit**

```bash
git add skills/mneme/references/workflow-ingest.md skills/mneme/references/workflow-query.md skills/mneme/references/workflow-lint.md
git commit -m "docs: rewrite workflow-ingest/query/lint.md for host-agent (v2.1)

Drops references to 'mneme ingest' / 'mneme query' / 'mneme lint' CLI
subcommands (those subcommands no longer exist; host agent drives
these workflows via SKILL.md scenarios). Describes the host-agent
checklist (Read/Write/Edit/Bash + okflib/indexlib Python modules).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

## Phase F — final verify, review, merge

### Task F1: full-suite sanity + final inventory

- [ ] **Step 1: run full test suite + capture count**

```bash
cd /Users/scott1743/opc/mneme
.venv/bin/pytest -q 2>&1 | tail -3
```

Expected: 32 passed, 3 skipped (the 3 skipped are smoke tests no longer applicable since the Strands `@tool` wrappers are gone — but the test file was deleted, so actually all tests pass: `32 passed`).

- [ ] **Step 2: inventory deliverables**

```bash
cd /Users/scott1743/opc/mneme
ls skills/mneme/scripts/
ls skills/mneme/references/
ls skills/mneme/
ls tests/
```

Expected:
- `scripts/`: `okflib.py`, `indexlib.py`, `validate_okf.py`, `mneme.py`, `tools_helpers.py` (5 files).
- `references/`: `workflow-ingest.md`, `workflow-query.md`, `workflow-lint.md`, `type-vocab.md`, `wiki-structure.md`, `index-design.md` (6 files).
- `skills/mneme/`: `SKILL.md` + `scripts/` + `references/`.
- `tests/`: `conftest.py`, `test_okflib.py`, `test_indexlib.py`, `test_integration.py`, `test_cli.py`, `test_tools_helpers.py` (6 files; pycaches ignored).

- [ ] **Step 3: validate the sample bundle (regression)**

```bash
cd /Users/scott1743/opc/mneme
.venv/bin/python skills/mneme/scripts/validate_okf.py sample-bundle
```

Expected: `0 error(s)`.

### Task F2: dispatch a fresh code-reviewer subagent for whole-branch review

- [ ] **Step 1: capture the review package**

```bash
cd /Users/scott1743/opc/mneme
MERGE_BASE=$(git merge-base main HEAD)
git diff --stat $MERGE_BASE..HEAD
git diff $MERGE_BASE..HEAD -- 'skills/mneme/*' 'tests/*' 'pyproject.toml' > /tmp/v2_1_review.diff
wc -l /tmp/v2_1_review.diff
```

- [ ] **Step 2: dispatch the review subagent (sonnet; reviewer is its own context)**

Dispatch with:

> Review the v2.1 diff at `/tmp/v2_1_review.diff` (full diff with context). The branch is `feat/skill-v2_1` (merge-base is `main`). Goal: verify the spec at `docs/superpowers/specs/2026-07-06-mneme-skill-design-v2_1.md` is honored. Specifically check: (1) **no Strands `@tool` decorators or `Agent(...)` constructors** anywhere in `skills/mneme/scripts/` (except possibly leftover imports — the `@tool` decorator on functions was the v2 marker; both the `tools` module and the Strands-agent pattern must be gone); (2) `mneme.py` exposes only `init` and `reindex` subcommands (no `cmd_ingest/query/lint`); (3) `SKILL.md` describes exactly 6 scenarios (`init`/`reindex`/`ingest`/`query`/`lint`/`dream`); (4) `pyproject.toml` has no `[agents]` extra; (5) the `dream` scenario in SKILL.md documents `git` pre-snapshot + post-guard validate + `dream-report-<date>.md` + soft cap. Report any spec deviation or quality issue (YAGNI / dead code / unused imports / fragile assumptions). Return `SPEC_OK` + quality verdict + any findings.

- [ ] **Step 3: handle review findings**

If the reviewer returns findings:
- Critical/Important → dispatch a fix subagent with the complete findings list + diff path. After fix, re-run the full test suite + re-validate the sample bundle. Don't re-review in a loop unless the fix changes the spec surface.
- Minor → record in `.superpowers/sdd/progress.md` and proceed.

### Task F3: merge to main

- [ ] **Step 1: merge**

```bash
cd /Users/scott1743/opc/mneme
git checkout main
git merge --no-ff feat/skill-v2_1 -m "Merge feat/skill-v2_1: drop independent agents; host-agent driven + git-guarded dream

Removes the v2 Strands agent layer (tools.py / ingest.py / query.py /
lint.py + their tests + pyproject [agents] extra). All write paths now
flow through SKILL.md scenarios driven by the host agent using native
tools (Read/Write/Edit/Bash/Glob/Grep) + okflib/indexlib Python modules.

SKILL.md rewritten with 6 scenarios: init / reindex / ingest / query /
lint / dream. mneme.py thinned to init + reindex only.

Dream = scheduled host-agent session with git pre-snapshot, post-dream
validate, dream-report-<date>.md, and soft cap max_dream_changes_per_run=20.
Graces when the bundle isn't a git repo (warns, continues without
git ops).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git log --oneline | head -5
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Plan task |
|---|---|
| §1 identity, lightweight philosophy | covered throughout (Task A1/A2; SKILL.md preamble) |
| §2 D1–D9 | D1–D9 each map to a task (D1→A1, D3→A1+A2+D1, D7→D1, D8→A2+D1, D9→D1) |
| §3 architecture | Task A2 (mneme.py simplified), Task D1 (SKILL.md) |
| §4 SKILL.md 6 scenarios | Task D1 |
| §5 mneme.py CLI (init+reindex) | Task A2 |
| §6 dream (trigger + git guard + soft cap + report) | Task D1 (dream scenario) |
| §7 layout (delete tools/ingest/query/lint; keep okflib/indexlib/validate_okf/mneme) | Task A1 |
| §8 test plan (delete test_tools/agents_smoke; rewrite test_cli; keep others) | Task A1 (deletes), A2 (rewrite) |
| §9 non-goals | enforced by deletes (A1) and SKILL.md wording (D1) |
| §10 v2 → v2.1 migration | Tasks A1+A2+D1+E1 (delete + thin CLI + SKILL.md + workflow docs) |
| §11 future | n/a (out of scope; recorded in spec) |

**2. Placeholder scan:** no TBD/TODO/vague. The dream soft cap (`max_dream_changes_per_run=20`) is explicit. The dream atomic-write protocol is concrete (write to `.mneme/dream-pending/`, then `cp`/`git mv`). All SKILL.md scenarios have concrete Bash/Python snippets.

**3. Type consistency:**
- `mneme.main([...]) -> int` (returns 0/1/2) consistent across `init`/`reindex`/`unknown`/`no-args`.
- `resolve_bundle(config_path=None) -> Path | None` used consistently in `mneme.py` (cmd_reindex) and `tools_helpers.py`.
- `indexlib.open_index / ensure_schema / chunk_markdown / upsert_concept / remove_concept / search / reindex_bundle / default_embed_fn` signatures unchanged from v2.
- `okflib.find_orphans / list_concepts / read_concept / parse_frontmatter / validate_bundle` signatures unchanged.

**4. Ambiguity check:**
- Dream atomic-write: `.mneme/dream-pending/` is explicit; copy/move step is explicit.
- `tools_helpers.py` extraction: introduced in Task A2 because `tools.py` (which previously hosted `resolve_bundle`) was deleted in Task A1 — the new module name avoids the old `@tool`-bound `tools.py` collision.
- Git degradation: when the bundle isn't a git repo, dream logs a warning and continues without git ops (per spec §6.2); the report still gets written.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-06-mneme-skill-v2_1.md`. Two execution options:

1. **Subagent-driven (recommended for v2.1)** — fresh subagent per phase (A1, A2, D1, E1, F1, F2, F3).
2. **Inline** — execute in this session with checkpoints.

v2.1 is mostly deletions + a SKILL.md rewrite (no novel algorithms, low implementation risk) — **inline may actually be faster** than subagent-driven for this one. Your call.