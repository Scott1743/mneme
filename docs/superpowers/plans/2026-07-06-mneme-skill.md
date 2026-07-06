# Mneme Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a portable Claude Code agent skill (`mneme`) that maintains an external, OKF v0.1-conformant LLM wiki of research/learning notes via ingest/query/lint workflows, backed by a zero-dependency conformance library.

**Architecture:** Single `SKILL.md` (three prose workflows) + `scripts/okflib.py` (stdlib-only importable library: frontmatter parsing, concept listing, bundle validation) + `scripts/validate_okf.py` (CLI frontend). The wiki bundle lives external to this repo; location resolved from `~/.config/mneme/config.toml` first. `okflib` is the reserved interface a future MCP server would import.

**Tech Stack:** Python 3.10+ (stdlib only at runtime; `pytest` dev-only), Markdown + YAML frontmatter, Claude Code skill format.

## Global Constraints

- **OKF v0.1 §9 conformance** (hard contract): (1) every non-reserved `.md` has parseable YAML frontmatter; (2) every frontmatter has a non-empty `type`; (3) reserved `index.md`/`log.md` follow §6/§7 when present.
- **Tolerance contract (§9):** validators MUST NOT error on missing optional fields, unknown `type` values, unknown extra frontmatter keys, broken cross-links, or missing `index.md` — these are warnings only.
- **Zero runtime dependencies:** `okflib.py` and `validate_okf.py` use Python standard library only. `pytest` is dev-only (test-time).
- **Reserved filenames** `index.md`, `log.md` are not concept docs. Concept ID = file path with `.md` stripped.
- **`upstream/` is read-only:** never add frontmatter to or edit `.research/upstream/*.md`.
- **Bundle location resolution order** (spec §5): `~/.config/mneme/config.toml` `bundle_path` → `MNEME_BUNDLE` env → explicit arg → auto-discover (root `index.md` with `okf_version`) → `./wiki` → prompt/init.
- **Type vocab** (recommended, non-registered): `Concept`, `Reference`, `Summary`, `Source`.
- **Branch:** execute on `feat/skill-v1` (branch from `main` before Task 1).

## File Structure

```
mneme/
├── CLAUDE.md                          # MODIFY (Task 8): external-bundle model, new layout
├── SKILL.md                           # CREATE (Task 6): carrier
├── scripts/
│   ├── okflib.py                      # CREATE (Tasks 1-4): stdlib library
│   └── validate_okf.py                # CREATE (Task 5): CLI frontend
├── references/
│   ├── workflow-ingest.md             # CREATE (Task 7)
│   ├── workflow-query.md              # CREATE (Task 7)
│   ├── workflow-lint.md               # CREATE (Task 7)
│   └── type-vocab.md                  # CREATE (Task 7)
├── sample-bundle/                     # CREATE (Task 2): valid fixture + format demo
│   ├── index.md
│   ├── log.md
│   ├── sources/
│   └── concepts/
│       ├── llm-wiki.md
│       └── okf.md
├── tests/
│   ├── test_okflib.py                 # CREATE (Tasks 1-4)
│   ├── conftest.py                    # CREATE (Task 1): sys.path bootstrap
│   └── fixtures/
│       ├── missing_frontmatter/       # Task 3
│       ├── empty_type/                # Task 3
│       ├── unknown_type/              # Task 3
│       ├── extra_keys/                # Task 3
│       └── broken_link/               # Task 4
└── pyproject.toml                     # CREATE (Task 1): pytest dev dep
```

**Responsibilities:** `okflib.py` = single source of truth for OKF parsing/validation (importable, MCP-reservable). `validate_okf.py` = thin CLI, no logic of its own. `SKILL.md` = prose workflows + rules, no code. `references/` = workflow detail the agent loads on demand (keeps `SKILL.md` short).

---
## Task 1: parse_frontmatter + project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `scripts/okflib.py`
- Create: `tests/test_okflib.py`

**Interfaces:**
- Produces: `okflib.parse_frontmatter(text: str) -> Optional[Tuple[Dict, str]]`, `okflib.Violation`, `okflib.Report` (with `.errors`, `.warnings`, `.ok`).

- [ ] **Step 1: Create venv + install pytest**

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "mneme"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = ["pytest"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Write `tests/conftest.py`** (puts `scripts/` on sys.path so `import okflib` works)

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
```

- [ ] **Step 4: Write failing tests** (`tests/test_okflib.py`)

```python
from okflib import parse_frontmatter


def test_parse_frontmatter_basic():
    text = "---\ntype: Concept\ntitle: Foo\ntags: [a, b]\n---\n# Body\n"
    meta, body = parse_frontmatter(text)
    assert meta["type"] == "Concept"
    assert meta["title"] == "Foo"
    assert meta["tags"] == ["a", "b"]
    assert body.startswith("# Body")


def test_parse_frontmatter_quoted():
    text = "---\ntype: \"Reference\"\ntitle: 'Has, comma'\n---\nbody\n"
    meta, _ = parse_frontmatter(text)
    assert meta["type"] == "Reference"
    assert meta["title"] == "Has, comma"


def test_parse_frontmatter_none_when_absent():
    assert parse_frontmatter("# just a body\nno frontmatter\n") is None
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_okflib.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'okflib'`

- [ ] **Step 6: Write `scripts/okflib.py`**

```python
"""Zero-dependency (Python stdlib only) OKF v0.1 library.

Minimal YAML-subset frontmatter parser: sufficient for OKF's required
fields (type) and common metadata (key: value, key: [a, b], quoted
strings, # comments). NOT a full YAML parser — OKF conformance only
requires `type`; consumers needing full YAML may use PyYAML separately.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

RESERVED = ("index.md", "log.md")
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?(.*)\Z", re.S)


@dataclass
class Violation:
    path: str
    rule: str
    severity: str  # "error" | "warning"
    detail: str


@dataclass
class Report:
    errors: List[Violation] = field(default_factory=list)
    warnings: List[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_frontmatter(text: str) -> Optional[Tuple[Dict, str]]:
    """Return (metadata_dict, body) or None if no frontmatter block."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    raw, body = m.group(1), m.group(2)
    meta: Dict = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            meta[key] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
        elif len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
            meta[key] = val[1:-1]
        else:
            meta[key] = val
    return meta, body
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_okflib.py -v`
Expected: PASS (3 tests)

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml tests/conftest.py tests/test_okflib.py scripts/okflib.py .gitignore
git commit -m "feat(okflib): add parse_frontmatter + project scaffold (TDD)"
```

## Task 2: sample-bundle fixture + list_concepts + read_concept

**Files:**
- Create: `sample-bundle/index.md`, `sample-bundle/log.md`, `sample-bundle/concepts/llm-wiki.md`, `sample-bundle/concepts/okf.md`, `sample-bundle/sources/.gitkeep`
- Modify: `scripts/okflib.py` (add `list_concepts`, `read_concept`)
- Modify: `tests/test_okflib.py` (add tests)

**Interfaces:**
- Produces: `okflib.list_concepts(bundle_path) -> List[str]`, `okflib.read_concept(bundle_path, concept_id) -> Optional[Tuple[Dict, str]]`.

- [ ] **Step 1: Write failing tests** (append to `tests/test_okflib.py`; add `from pathlib import Path` and module constants near top)

```python
from pathlib import Path
from okflib import list_concepts, read_concept

SAMPLE = Path(__file__).parent.parent / "sample-bundle"


def test_list_concepts_excludes_reserved():
    ids = list_concepts(SAMPLE)
    assert "concepts/llm-wiki" in ids
    assert "concepts/okf" in ids
    assert "index" not in ids
    assert "log" not in ids


def test_read_concept_returns_metadata_and_body():
    meta, body = read_concept(SAMPLE, "concepts/okf")
    assert meta["type"] == "Reference"
    assert "OKF" in body


def test_read_concept_missing_returns_none():
    assert read_concept(SAMPLE, "concepts/nope") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_okflib.py -v`
Expected: FAIL — `FileNotFoundError` (sample-bundle does not exist yet) / `ImportError` (functions missing)

- [ ] **Step 3: Create the sample bundle**

`sample-bundle/index.md`:
```markdown
---
okf_version: "0.1"
---

# Concepts

* [LLM Wiki](concepts/llm-wiki.md) - Karpathy's idea of a persistent, agent-maintained knowledge wiki.
* [OKF](concepts/okf.md) - Open Knowledge Format v0.1: markdown + YAML frontmatter, 3 rules.
```

`sample-bundle/log.md`:
```markdown
# Directory Update Log

## 2026-07-06
* **Creation**: Seeded sample bundle with llm-wiki and okf concepts.
```

`sample-bundle/concepts/llm-wiki.md`:
```markdown
---
type: Concept
title: LLM Wiki
description: Karpathy's idea of a persistent, agent-maintained knowledge wiki.
tags: [karpathy, wiki]
timestamp: 2026-07-06T00:00:00Z
---
# LLM Wiki
Compile knowledge once into a persistent wiki instead of RAG-ing from scratch each query. See also [OKF](/concepts/okf.md).
```

`sample-bundle/concepts/okf.md`:
```markdown
---
type: Reference
title: OKF
description: Open Knowledge Format v0.1.
tags: [okf, spec]
timestamp: 2026-07-06T00:00:00Z
---
# OKF
A directory of markdown + YAML frontmatter with 3 conformance rules. See [LLM Wiki](/concepts/llm-wiki.md) for the intellectual origin.
```

`sample-bundle/sources/.gitkeep`: (empty file)

- [ ] **Step 4: Add `list_concepts` + `read_concept` to `scripts/okflib.py`** (append after `parse_frontmatter`)

```python
def list_concepts(bundle_path) -> List[str]:
    """Concept IDs (file path without .md) for all non-reserved .md files."""
    root = Path(bundle_path)
    ids = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        if os.path.basename(rel) in RESERVED:
            continue
        ids.append(rel[:-3])
    return ids


def read_concept(bundle_path, concept_id: str) -> Optional[Tuple[Dict, str]]:
    """Return (metadata, body) for a concept ID, or None if missing."""
    p = Path(bundle_path) / (concept_id + ".md")
    if not p.exists():
        return None
    return parse_frontmatter(p.read_text(encoding="utf-8"))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_okflib.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add sample-bundle/ scripts/okflib.py tests/test_okflib.py
git commit -m "feat(okflib): add sample-bundle fixture + list_concepts/read_concept (TDD)"
```

## Task 3: validate_bundle — hard rules (§9 rules 1 & 2)

**Files:**
- Modify: `scripts/okflib.py` (add `validate_bundle`, `_validate_reserved`)
- Create: `tests/fixtures/missing_frontmatter/a.md`, `tests/fixtures/empty_type/a.md`, `tests/fixtures/unknown_type/a.md`, `tests/fixtures/extra_keys/a.md`
- Modify: `tests/test_okflib.py` (add tests)

**Interfaces:**
- Produces: `okflib.validate_bundle(bundle_path) -> Report`.

- [ ] **Step 1: Write failing tests** (append to `tests/test_okflib.py`; add `from okflib import validate_bundle`)

```python
from okflib import validate_bundle

FIX = Path(__file__).parent / "fixtures"


def test_valid_bundle_passes():
    report = validate_bundle(SAMPLE)
    assert report.ok, [(v.path, v.rule, v.detail) for v in report.errors]


def test_missing_frontmatter_fails():
    report = validate_bundle(FIX / "missing_frontmatter")
    assert not report.ok
    assert any(v.rule == "no-frontmatter" for v in report.errors)


def test_empty_type_fails():
    report = validate_bundle(FIX / "empty_type")
    assert not report.ok
    assert any(v.rule == "empty-type" for v in report.errors)


def test_unknown_type_passes():
    report = validate_bundle(FIX / "unknown_type")
    assert report.ok


def test_extra_keys_pass():
    report = validate_bundle(FIX / "extra_keys")
    assert report.ok
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_okflib.py -v`
Expected: FAIL — `ImportError` (validate_bundle missing)

- [ ] **Step 3: Create the fixtures**

`tests/fixtures/missing_frontmatter/a.md`:
```markdown
# No frontmatter here
Just a body.
```

`tests/fixtures/empty_type/a.md`:
```markdown
---
type:
title: A
---
body
```

`tests/fixtures/unknown_type/a.md`:
```markdown
---
type: WhateverThing
title: A
---
body
```

`tests/fixtures/extra_keys/a.md`:
```markdown
---
type: Concept
custom_field: x
author: me
---
body
```

- [ ] **Step 4: Add `validate_bundle` + `_validate_reserved` to `scripts/okflib.py`** (append after `read_concept`)

```python
def validate_bundle(bundle_path) -> Report:
    """Check OKF v0.1 §9 hard rules + soft warnings (links/index added in Task 4)."""
    root = Path(bundle_path)
    report = Report()
    if not root.is_dir():
        report.errors.append(Violation(str(root), "no-bundle", "error", "bundle path is not a directory"))
        return report
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        name = os.path.basename(rel)
        text = p.read_text(encoding="utf-8")
        if name in RESERVED:
            _validate_reserved(rel, name, text, report)
            continue
        parsed = parse_frontmatter(text)
        if parsed is None:
            report.errors.append(Violation(rel, "no-frontmatter", "error", "missing YAML frontmatter block"))
            continue
        meta, _ = parsed
        t = meta.get("type")
        if not t or not str(t).strip():
            report.errors.append(Violation(rel, "empty-type", "error", "frontmatter has no non-empty 'type'"))
    return report


def _validate_reserved(rel, name, text, report):
    m = _FRONTMATTER_RE.match(text)
    body = m.group(2) if m else text
    if name == "index.md" and not body.strip():
        report.warnings.append(Violation(rel, "bad-reserved", "warning", "index.md has empty body"))
    if name == "log.md" and not text.strip():
        report.warnings.append(Violation(rel, "bad-reserved", "warning", "log.md is empty"))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_okflib.py -v`
Expected: PASS (11 tests)

- [ ] **Step 6: Commit**

```bash
git add scripts/okflib.py tests/fixtures/missing_frontmatter tests/fixtures/empty_type tests/fixtures/unknown_type tests/fixtures/extra_keys tests/test_okflib.py
git commit -m "feat(okflib): validate_bundle hard rules (frontmatter + type) (TDD)"
```

## Task 4: validate_bundle — soft warnings (broken links, missing index)

**Files:**
- Modify: `scripts/okflib.py` (add `_check_links`, call it + missing-index check in `validate_bundle`)
- Create: `tests/fixtures/broken_link/a.md`
- Modify: `tests/test_okflib.py` (add test)

**Interfaces:**
- Modifies: `validate_bundle` now also populates `report.warnings` with `broken-link` and `missing-index`.

- [ ] **Step 1: Write failing test** (append to `tests/test_okflib.py`)

```python
def test_broken_link_is_warning_not_error():
    report = validate_bundle(FIX / "broken_link")
    assert report.ok  # broken link is a warning, not an error (OKF §9 tolerance)
    assert any(v.rule == "broken-link" for v in report.warnings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_okflib.py::test_broken_link_is_warning_not_error -v`
Expected: FAIL — fixture missing / no broken-link warning produced

- [ ] **Step 3: Create the fixture**

`tests/fixtures/broken_link/a.md`:
```markdown
---
type: Concept
---
See [missing](/nope.md).
```

- [ ] **Step 4: Add `_check_links` + wire into `validate_bundle`**

Add the module-level constant near the other regex:
```python
_LINK_RE = re.compile(r"\]\((/[^\)]+\.md)\)")
```

Add the helper (after `_validate_reserved`):
```python
def _check_links(root, report):
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        if os.path.basename(rel) in RESERVED:
            continue
        text = p.read_text(encoding="utf-8")
        for m in _LINK_RE.finditer(text):
            target = m.group(1).lstrip("/")
            if not (root / target).exists():
                report.warnings.append(
                    Violation(rel, "broken-link", "warning", f"link target not found: {m.group(1)}")
                )
```

In `validate_bundle`, insert immediately before the final `return report`:
```python
    _check_links(root, report)
    if not (root / "index.md").exists():
        report.warnings.append(Violation("index.md", "missing-index", "warning", "no root index.md"))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_okflib.py -v`
Expected: PASS (12 tests). Note: `broken_link` fixture has no `index.md`, so it also emits `missing-index` (a warning) — `report.ok` stays True.

- [ ] **Step 6: Commit**

```bash
git add scripts/okflib.py tests/fixtures/broken_link tests/test_okflib.py
git commit -m "feat(okflib): soft warnings for broken links + missing index (TDD)"
```

## Task 5: validate_okf.py CLI frontend

**Files:**
- Create: `scripts/validate_okf.py`
- Modify: `tests/test_okflib.py` (add CLI tests)

**Interfaces:**
- Produces: `scripts/validate_okf.py` — exit 0 if no errors, 1 if errors, 2 on usage error.

- [ ] **Step 1: Write failing tests** (append to `tests/test_okflib.py`; add `import subprocess, sys`)

```python
import subprocess
import sys

VALIDATOR = Path(__file__).parent.parent / "scripts" / "validate_okf.py"


def _run(bundle):
    return subprocess.run([sys.executable, str(VALIDATOR), str(bundle)], capture_output=True, text=True)


def test_cli_valid_bundle_exit_zero():
    r = _run(SAMPLE)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 error(s)" in r.stdout


def test_cli_invalid_bundle_exit_one():
    r = _run(FIX / "missing_frontmatter")
    assert r.returncode == 1
    assert "no-frontmatter" in r.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_okflib.py -v`
Expected: FAIL — `validate_okf.py` does not exist

- [ ] **Step 3: Write `scripts/validate_okf.py`**

```python
#!/usr/bin/env python3
"""OKF v0.1 conformance validator CLI. Zero-dependency (stdlib)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from okflib import validate_bundle


def main(argv):
    if len(argv) != 2:
        print("usage: validate_okf.py <bundle_path>", file=sys.stderr)
        return 2
    report = validate_bundle(argv[1])
    for v in report.errors:
        print(f"ERROR  {v.path}: [{v.rule}] {v.detail}")
    for v in report.warnings:
        print(f"WARN   {v.path}: [{v.rule}] {v.detail}")
    print(f"\n{len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_okflib.py -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Smoke-test the CLI manually**

Run: `.venv/bin/python scripts/validate_okf.py sample-bundle`
Expected: `0 error(s)` and exit 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/validate_okf.py tests/test_okflib.py
git commit -m "feat(cli): add validate_okf.py frontend on okflib (TDD)"
```

## Task 6: SKILL.md (the carrier)

**Files:**
- Create: `SKILL.md`

**Interfaces:**
- Produces: the agent skill itself. References `scripts/validate_okf.py` and `references/*.md`.

- [ ] **Step 1: Write `SKILL.md`**

```markdown
---
name: mneme
description: "Maintain a local, OKF-conformant LLM knowledge wiki of research/learning notes. Use when the user wants to ingest a source (paper/article/note) into their wiki, query the wiki, lint/check OKF conformance, or initialize a new wiki. Triggers: 'mneme', 'my wiki', 'ingest this', 'query my notes', 'lint the wiki', 'knowledge base', '查 wiki', '摄入笔记', '知识库'."
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

mneme maintains an external OKF v0.1 wiki of research/learning notes. You are its disciplined maintainer (the schema layer). Three workflows: **ingest**, **query**, **lint** (+ **init**).

## Step 0: resolve the bundle (EVERY operation)

Find the wiki bundle in this order; use the first hit:
1. `~/.config/mneme/config.toml` key `bundle_path`.
2. `MNEME_BUNDLE` env var.
3. An explicit path the user gave in this request.
4. Auto-discover: walk up from cwd for a root `index.md` whose frontmatter contains `okf_version`.
5. `./wiki` if it exists.
6. None found → ask the user for the path, or offer `init`.

`config.toml` is simple `key = "value"` lines; parse with stdlib (no PyYAML needed).

## OKF v0.1 conformance (hard rules — never violate on write)

1. Every non-reserved `.md` MUST have a `---`-delimited YAML frontmatter block.
2. Every frontmatter MUST have a non-empty `type`.
3. Reserved `index.md` (directory listing; no frontmatter except root `okf_version`) and `log.md` (date-prefixed timeline) follow their structure.

Do NOT reject unknown `type` values, extra frontmatter keys, or broken links — warnings only.

## type vocab (recommended, non-registered)

`Concept` (idea/topic) · `Reference` (distilled external source) · `Summary` (synthesis) · `Source` (raw doc in sources/).

## ingest <source path>

1. Resolve bundle (Step 0). If absent and user wants, run `init`.
2. Read the source (.md/.txt only in v1). Copy to `sources/<slug>.md` (immutable raw layer).
3. Read the source; optionally discuss key points with the user.
4. Write concept page(s) under an appropriate subdir, each with frontmatter: `type`, `title`, `description`, `tags`, `timestamp` (ISO 8601), `resource` (source path).
5. Update related existing pages with cross-links (absolute bundle-relative: `/dir/concept.md`).
6. Update `index.md`: add `* [Title](path) - description` under the right section.
7. Append to `log.md`: `## YYYY-MM-DD ingest | <title>` + one-line note.
8. Run `python3 scripts/validate_okf.py <bundle>`. Fix any ERROR before ingest is done.

## query <question>

1. Resolve bundle.
2. Read `index.md` first (progressive disclosure) to locate relevant pages.
3. Read those pages.
4. Synthesize an answer WITH citations (bundle-relative links + external citations present).
5. If the answer is broadly useful and no page covers it, OFFER to backfill as a new concept page (do not auto-write in v1).

## lint

1. Resolve bundle.
2. Run `python3 scripts/validate_okf.py <bundle>`. Report ERRORs (must fix) and WARNings.
3. Curate warnings: contradictions, stale claims, orphan pages, missing cross-links, important concepts with no page. Propose fixes; apply only with user approval.

## init <path>

Scaffold a new empty bundle and record it:
- `<path>/index.md` with `okf_version: "0.1"` frontmatter + empty `# Concepts` body.
- `<path>/log.md` with `# Directory Update Log` header.
- `<path>/sources/.gitkeep`.
- Write `bundle_path = "<path>"` to `~/.config/mneme/config.toml` (create `~/.config/mneme/` if needed).

## references (load on demand)

`references/workflow-ingest.md` · `references/workflow-query.md` · `references/workflow-lint.md` · `references/type-vocab.md`. Validator: `scripts/validate_okf.py`. OKF spec: `.research/upstream/OKF-SPEC.md`.
```

- [ ] **Step 2: Verify structure**

Run: `grep -E '^(name: mneme|## ingest|## query|## lint|## init|## Step 0)' SKILL.md`
Expected: 6 matches (the required sections exist).

- [ ] **Step 3: Commit**

```bash
git add SKILL.md
git commit -m "feat(skill): add SKILL.md carrier (ingest/query/lint/init workflows)"
```

## Task 7: references/ docs

**Files:**
- Create: `references/workflow-ingest.md`, `references/workflow-query.md`, `references/workflow-lint.md`, `references/type-vocab.md`

- [ ] **Step 1: Write `references/workflow-ingest.md`**

```markdown
---
type: Reference
title: mneme ingest workflow
description: Detailed rules for ingesting a source into the wiki.
---
# ingest workflow

- **Slug**: derive from source filename, lowercase, spaces→hyphens. `My Note.md` → `sources/my-note.md`.
- **Placement**: concept pages go under a topical subdir (e.g. `concepts/`, or a domain dir). Mirror the source's theme; create a dir if none fits.
- **Type choice**: `Reference` for a distilled external source; `Concept` for an idea you extract; `Summary` when you synthesize across multiple sources; `Source` is the raw copy in `sources/`.
- **One source → multiple pages**: a rich source may yield 5–15 pages (one per distinct concept). Always link them to each other and to existing pages.
- **Cross-links**: absolute bundle-relative form (`/concepts/okf.md`) — stable when files move within their subdir.
- **index.md**: add one entry per new page, description copied from the page's frontmatter `description`.
- **log.md**: `## YYYY-MM-DD ingest | <source title>` then bullet lines of what was created/updated.
- **Validate last**: `python3 scripts/validate_okf.py <bundle>` must report 0 errors before you stop.
```

- [ ] **Step 2: Write `references/workflow-query.md`**

```markdown
---
type: Reference
title: mneme query workflow
description: How to answer questions from the wiki with citations.
---
# query workflow

- **Progressive disclosure**: always read `index.md` first; do not load the whole bundle. Drill only into pages the index suggests are relevant.
- **Cite**: every non-trivial claim links the concept page it came from (`/concepts/<id>.md`). If the page has a `# Citations` section, surface those external links too.
- **Honesty about gaps**: if the wiki lacks coverage, say so — do not fabricate. Suggest an ingest.
- **Backfill**: if your synthesized answer is broadly useful and no page covers it, OFFER to create a `Summary` or `Concept` page capturing it (ask first; v1 does not auto-write).
```

- [ ] **Step 3: Write `references/workflow-lint.md`**

```markdown
---
type: Reference
title: mneme lint workflow
description: Curate the wiki for conformance and quality.
---
# lint workflow

- **Hard errors** (from validator, must fix): `no-frontmatter`, `empty-type`, `no-bundle`.
- **Warnings** (curate, ask before fixing): `broken-link` (target missing — create the page or fix the path), `missing-index` (no root `index.md` — generate one), `bad-reserved` (empty `index.md`/`log.md`).
- **Curation heuristics** (agent judgment, propose only): contradictions between pages, stale `timestamp` with no log entry, orphan pages (nothing links to them — link them or merge), important concepts with no page, missing cross-links between related pages.
- **Apply fixes only with user approval**; re-run the validator after.
```

- [ ] **Step 4: Write `references/type-vocab.md`**

```markdown
---
type: Reference
title: mneme type vocabulary
description: Recommended OKF type values for research/learning notes.
---
# type vocabulary

Recommended (non-registered — OKF tolerates any `type`):

- `Concept` — an idea or topic page. Most common.
- `Reference` — a distilled external source (paper, article, doc).
- `Summary` — a synthesis across multiple concepts/sources.
- `Source` — the raw source document copy in `sources/` (immutable).

Add new types freely; consumers treat unknown types as generic concepts. Keep `type` values short and self-explanatory.
```

- [ ] **Step 5: Verify all four exist**

Run: `ls references/workflow-ingest.md references/workflow-query.md references/workflow-lint.md references/type-vocab.md`
Expected: no error (all four files listed).

- [ ] **Step 6: Commit**

```bash
git add references/
git commit -m "docs: add references/ workflow + type-vocab docs"
```

## Task 8: Update CLAUDE.md (external-bundle model + new layout)

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Replace the `## 目录结构` code block** in `CLAUDE.md` with the updated layout (external bundle; no in-repo `wiki/`):

````
## 目录结构

```
mneme/
├── CLAUDE.md              # 本文件 = schema 层（项目宪法 + agent 维护规约）
├── SKILL.md               # agent skill 载体：ingest / query / lint / init
├── scripts/
│   ├── okflib.py          # 零依赖 OKF 库（parse/list/validate；MCP 预留接口）
│   └── validate_okf.py    # okflib 的 CLI 前端
├── references/            # skill 支撑文档（工作流详述、type 词表）
├── sample-bundle/         # 合规示范/测试夹具（非真 wiki）
├── tests/                 # okflib TDD 测试 + fixtures/
├── .research/             # 立项研究档案（upstream/ 为 verbatim MIT 副本，勿改）
└── .gitignore
```

**真 wiki bundle 在仓库外**，路径由 `~/.config/mneme/config.toml` 的 `bundle_path` 指定（见 spec §5）。`sample-bundle/` 仅作测试夹具与格式演示。
````

- [ ] **Step 2: Verify the edit**

Run: `grep -E 'sample-bundle/|okflib.py|config.toml 的 bundle_path' CLAUDE.md`
Expected: matches for all three (new layout landed).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md to external-bundle model + new layout"
```

## Task 9: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/pytest -v`
Expected: all tests PASS (14 tests, 0 failures).

- [ ] **Step 2: Validate the sample bundle**

Run: `.venv/bin/python scripts/validate_okf.py sample-bundle`
Expected: `0 error(s)`, exit 0.

- [ ] **Step 3: Confirm all deliverables exist**

Run: `ls SKILL.md scripts/okflib.py scripts/validate_okf.py references/workflow-ingest.md references/workflow-query.md references/workflow-lint.md references/type-vocab.md sample-bundle/index.md`
Expected: no error (all files present).

- [ ] **Step 4: Commit any remaining changes** (e.g. `.venv` is gitignored; nothing expected)

```bash
git status --short
# if anything untracked that should be tracked:
git add -A && git commit -m "chore: finalize mneme skill v1"
```

- [ ] **Step 5: Merge `feat/skill-v1` into `main`** (after Task 9 verified)

```bash
git checkout main
git merge --no-ff feat/skill-v1
```

---

## Phase 2 (v2 — DEFERRED, not for execution now)

Per user request, captured in the plan but **not implemented in v1**. When v2 starts, expand each outline into full TDD tasks per the Phase 1 format. Spec reference: §14.

- **P2.1 Converter registry + format detection.** `scripts/converters/__init__.py` with a `detect(path) -> format_key` and `convert(path) -> (md_or_csv_paths)` dispatcher. Lazy-import per-format modules. TDD: detect by extension; unknown → fallback to copy-as-md.
- **P2.2 Per-format converters** (thin wraps over existing libs):
  - `docx.py` → md (`mammoth`)
  - `pdf.py` → md (`pdfplumber`; scanned → OCR path)
  - `pptx.py` → md, one section per slide (`python-pptx`)
  - `xlsx.py` → csv per sheet + md summary (`openpyxl`)
  - `image.py` → md via OCR (`pytesseract`, system `tesseract`)
  - `html.py` → md (`trafilatura`)
  Each: TDD with a tiny fixture file, asserting expected md/csv output contains key tokens.
- **P2.3 Wire converters into ingest.** `SKILL.md` ingest Step 2 becomes: if source is not `.md`/`.txt`, run `convert` first, then proceed. Output md/csv lands in `sources/`.
- **P2.4 Packaging.** `pyproject.toml` `[project.optional-dependencies] converters = [...]`; lazy imports so base install stays zero-dep. Document `tesseract` system prerequisite for OCR.
- **P2.5 Network note.** HTML ingest supports local `.html` (reliable) and URLs (China network — proxy or `! cmd` fetch). `trafilatura` handles both.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Covered by |
|---|---|
| §1 identity / 3-layer | Task 6 (SKILL.md), Task 8 (CLAUDE.md) |
| §2 D1 external bundle | Task 6 Step 0, Task 8 |
| §2 D2 research notes + type vocab | Task 6, Task 7 (type-vocab.md) |
| §2 D3 single skill + validator | Tasks 1–6 |
| §2 D4 config persistence + MCP reserve | Task 6 Step 0 (config), Tasks 1–4 (`okflib` = importable interface) |
| §3 storage access layer / okflib | Tasks 1–4 |
| §5 bundle resolution | Task 6 Step 0 |
| §6 ingest/query/lint data flow | Task 6 + Task 7 references |
| §7 error handling | Task 6 (lint), Task 4 (warnings) |
| §8 testing (TDD) | Tasks 1–5 (TDD throughout) |
| §9 type vocab | Task 7 type-vocab.md |
| §10 repo layout | Task 8 |
| §11 install/activation | Task 6 (init), Task 8 (config note) — symlink step noted in spec, not a code task |
| §12 v1 non-goals | respected (no URL/PDF/Office in v1) |
| §14 v2 conversion | Phase 2 (deferred outline) |

Gap: the user-scope skill symlink (`~/.claude/skills/mneme -> repo`) from spec §11 is a one-time install action, not a code task — left as a documented post-install step (mention in CLAUDE.md or a future INSTALL note). Acceptable.

**2. Placeholder scan:** No TBD/TODO/"add error handling"/"similar to Task N". All code steps show complete code. Phase 2 is explicitly deferred outline, not executable steps.

**3. Type consistency:** `parse_frontmatter`, `list_concepts`, `read_concept`, `validate_bundle`, `Violation(path, rule, severity, detail)`, `Report(errors, warnings, ok)` — names match across Tasks 1–5 and the SKILL.md/CLI references. `validate_okf.py main(argv)` returns 0/1/2 consistently with Task 5 tests.


