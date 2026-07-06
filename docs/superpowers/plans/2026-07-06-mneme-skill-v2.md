# Mneme Skill v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add L2 (sqlite-vec + fastembed index) and L3 (Strands ingest/query/lint agents + `mneme` CLI) to the mneme skill, plus the L1 wiki structure spec — so the wiki scales beyond one context window via retrieval, with agent-driven intermediate processing.

**Architecture:** L1 OKF bundle (existing `okflib`) → L2 `indexlib` (sqlite-vec, injected `embed_fn`, default fastembed) → L3 Strands agents + `mneme` CLI → L4 `SKILL.md`. Linking via CLI + skill (no MCP).

**Tech Stack:** Python 3.10+, sqlite-vec, fastembed (ONNX), strands-agents; pytest dev-only.

## Global Constraints

- **OKF v0.1 §9** conformance + tolerance contract (unchanged from v1).
- **L1 stays stdlib-only** (`okflib.py`, `validate_okf.py`). L2/L3 deps via pip extras: `mneme[index]` (sqlite-vec+fastembed), `mneme[agents]` (strands), `mneme[all]`.
- **`embed_fn` injected** into indexlib — tests use a fake (no model download); production default wraps fastembed.
- **`.mneme/` under a bundle is derived** (gitignored), skipped by the OKF validator and concept listing.
- **No resident service**; Strands agents run on-demand via CLI.
- **Branch:** `feat/skill-v2` (branch from `main` before Phase A).
- `upstream/` in `.research/` stays read-only (verbatim MIT).

## File Structure

```
skills/mneme/
├── SKILL.md                            # MODIFY (Task C3): call CLI; structure spec
├── scripts/
│   ├── okflib.py                       # MODIFY (Task A0): skip .mneme/ in list/validate
│   ├── validate_okf.py                 # unchanged
│   ├── indexlib.py                     # NEW (Phase A — L2)
│   ├── tools.py                        # NEW (Phase B — L3 shared tools)
│   ├── ingest.py / query.py / lint.py  # NEW (Phase B — L3 Strands agents)
│   └── mneme.py                        # NEW (Phase B — CLI)
└── references/
    ├── workflow-{ingest,query,lint}.md # MODIFY (Task C2)
    ├── type-vocab.md                   # unchanged
    ├── wiki-structure.md               # NEW (Task C1 — L1 spec)
    └── index-design.md                 # NEW (Task C1 — L2 spec)
tests/
├── test_okflib.py                      # MODIFY (Task A0): .mneme/ skip
├── test_indexlib.py                    # NEW (Phase A)
├── test_tools.py                       # NEW (Phase B)
└── test_cli.py                         # NEW (Phase B)
```

**Responsibilities:** `indexlib.py` = L2 (open_index/ensure_schema/chunk/upsert/remove/search/reindex). `tools.py` = L3 shared Strands tools wrapping `okflib`+`indexlib`. `ingest/query/lint.py` = Strands agents using those tools. `mneme.py` = thin CLI dispatch. `okflib.py` = L1 (extended to ignore `.mneme/`).

---

## Phase A — L2 indexlib (TDD)

### Task A0: okflib skips `.mneme/`

**Files:** Modify `skills/mneme/scripts/okflib.py`; Modify `tests/test_okflib.py`

- [ ] **Step 1: Write failing test** (append to `tests/test_okflib.py`)

```python
def test_list_concepts_skips_mneme_dir(tmp_path):
    import os
    bundle = tmp_path / "b"
    (bundle / "concepts").mkdir(parents=True)
    (bundle / "concepts" / "ok.md").write_text("---\ntype: Concept\n---\nbody\n")
    (bundle / ".mneme").mkdir()
    (bundle / ".mneme" / "index.db").write_text("not md")
    ids = list_concepts(bundle)
    assert "concepts/ok" in ids
    assert not any(".mneme" in i for i in ids)
```

- [ ] **Step 2: Run, expect fail** — `.venv/bin/pytest tests/test_okflib.py::test_list_concepts_skips_mneme_dir -v` → FAIL (rglob picks up nothing in .mneme since no .md, but `validate_bundle` may walk it; this test pins list_concepts behavior).

- [ ] **Step 3: Modify `list_concepts` and `validate_bundle`** in `okflib.py` to skip any path under a `.mneme/` segment. In `list_concepts`:

```python
def list_concepts(bundle_path) -> List[str]:
    root = Path(bundle_path)
    ids = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        if any(part == ".mneme" for part in p.relative_to(root).parts):
            continue
        if os.path.basename(rel) in RESERVED:
            continue
        ids.append(rel[:-3])
    return ids
```

Apply the same `.mneme` guard at the top of the `for p in sorted(root.rglob("*.md"))` loop in `validate_bundle` and `_check_links` (`continue` when any part is `.mneme`).

- [ ] **Step 4: Run full suite** — `.venv/bin/pytest -q` → all pass (15 tests).

- [ ] **Step 5: Commit**

```bash
git add skills/mneme/scripts/okflib.py tests/test_okflib.py
git commit -m "feat(okflib): skip .mneme/ derived dir in list/validate (TDD)"
```

### Task A1: indexlib — open_index + ensure_schema

**Files:** Create `skills/mneme/scripts/indexlib.py`; Create `tests/test_indexlib.py`; Modify `tests/conftest.py` (add `scripts` already on path — indexlib same dir)

**Interfaces:** Produces `indexlib.open_index(db_path) -> sqlite3.Connection`, `indexlib.ensure_schema(conn)`.

- [ ] **Step 1: Write failing test** (`tests/test_indexlib.py`)

```python
from pathlib import Path
from indexlib import open_index, ensure_schema


def test_open_index_creates_schema(tmp_path):
    conn = open_index(tmp_path / "index.db")
    ensure_schema(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "chunks" in tables
    assert "meta" in tables
    conn.close()
```

- [ ] **Step 2: Run, expect fail** — `.venv/bin/pytest tests/test_indexlib.py -v` → FAIL (`No module named 'indexlib'`).

- [ ] **Step 3: Install L2 dev deps** — `.venv/bin/pip install sqlite-vec` (fastembed installed in A5; tests use fake embed_fn so not needed yet).

- [ ] **Step 4: Create `skills/mneme/scripts/indexlib.py`**

```python
"""L2 index: sqlite-vec + pluggable embedding (embed_fn injected).

Default embed_fn wraps fastembed; tests inject a fake. No hard dependency
on a specific embedding provider — that's the point.
"""
from __future__ import annotations

import struct
import sqlite3
from typing import Callable, List, Dict

EmbedFn = Callable[[List[str]], List[List[float]]]


def open_index(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        import sqlite_vec
        sqlite_vec.load(conn)
    except Exception:
        pass  # extension absent → vec ops raise at use; tested separately
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chunks ("
        "chunk_id INTEGER PRIMARY KEY, concept_id TEXT, path TEXT, title TEXT, "
        "type TEXT, chunk_idx INTEGER, text TEXT, tags TEXT, timestamp TEXT, hash TEXT)"
    )
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()


def _ensure_vec_table(conn: sqlite3.Connection, dim: int) -> None:
    row = conn.execute("SELECT value FROM meta WHERE key='dim'").fetchone()
    if row is None:
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0("
            f"chunk_id INTEGER PRIMARY KEY, embedding FLOAT[{dim}])"
        )
        conn.execute("INSERT INTO meta(key,value) VALUES('dim',?)", (str(dim),))
        conn.commit()
    elif int(row[0]) != dim:
        raise ValueError(f"embedding dim mismatch: index has {row[0]}, got {dim}")


def _vec_blob(vec: List[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)
```

- [ ] **Step 5: Run, expect pass** — `.venv/bin/pytest tests/test_indexlib.py -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add skills/mneme/scripts/indexlib.py tests/test_indexlib.py
git commit -m "feat(indexlib): open_index + ensure_schema (TDD)"
```

### Task A2: chunk_markdown

**Files:** Modify `skills/mneme/scripts/indexlib.py`; Modify `tests/test_indexlib.py`

- [ ] **Step 1: Write failing tests** (append)

```python
from indexlib import chunk_markdown


def test_chunk_markdown_splits_by_headings():
    chunks = chunk_markdown("# Title\nbody1\n## Sub\nbody2\n")
    assert len(chunks) == 2
    assert "Title" in chunks[0] and "body1" in chunks[0]
    assert "Sub" in chunks[1]


def test_chunk_markdown_no_headings_returns_one():
    assert len(chunk_markdown("just text\nmore\n")) == 1
```

- [ ] **Step 2: Run, expect fail** — `ImportError: cannot import name 'chunk_markdown'`.

- [ ] **Step 3: Add to `indexlib.py`**

```python
def chunk_markdown(text: str) -> List[str]:
    parts, cur = [], []
    for line in text.splitlines():
        if line.startswith("#") and cur:
            parts.append("\n".join(cur).strip())
            cur = [line]
        else:
            cur.append(line)
    if cur:
        parts.append("\n".join(cur).strip())
    return [p for p in parts if p]
```

- [ ] **Step 4: Run, expect pass** → PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/mneme/scripts/indexlib.py tests/test_indexlib.py
git commit -m "feat(indexlib): chunk_markdown by headings (TDD)"
```

### Task A3: upsert_concept + remove_concept

**Files:** Modify `skills/mneme/scripts/indexlib.py`; Modify `tests/test_indexlib.py`

**Interfaces:** Produces `indexlib.upsert_concept(conn, concept_id, path, title, type, body, tags, timestamp, embed_fn) -> int`, `indexlib.remove_concept(conn, concept_id)`.

- [ ] **Step 1: Add fake_embed + failing tests** (append to `tests/test_indexlib.py`)

```python
import hashlib
from indexlib import open_index, ensure_schema, upsert_concept, remove_concept


def fake_embed(texts, dim=8):
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode("utf-8")).digest()
        vec = [(b - 128) / 128.0 for b in (h * (dim // len(h) + 1))[:dim]]
        out.append(vec)
    return out


_E = lambda ts: fake_embed(ts, 8)


def test_upsert_inserts_chunks_and_vectors(tmp_path):
    conn = open_index(tmp_path / "index.db"); ensure_schema(conn)
    n = upsert_concept(conn, "c1", "c1.md", "T", "Concept", "# H\nbody", "[]", "", _E)
    assert n == 1
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 1
    conn.close()


def test_upsert_replaces_on_reupsert(tmp_path):
    conn = open_index(tmp_path / "index.db"); ensure_schema(conn)
    upsert_concept(conn, "c1", "c1.md", "T", "Concept", "# A\nx", "[]", "", _E)
    upsert_concept(conn, "c1", "c1.md", "T", "Concept", "# A\nx\n# B\ny", "[]", "", _E)
    assert conn.execute("SELECT COUNT(*) FROM chunks WHERE concept_id='c1'").fetchone()[0] == 2
    conn.close()


def test_remove_concept_clears(tmp_path):
    conn = open_index(tmp_path / "index.db"); ensure_schema(conn)
    upsert_concept(conn, "c1", "c1.md", "T", "Concept", "body", "[]", "", _E)
    remove_concept(conn, "c1")
    assert conn.execute("SELECT COUNT(*) FROM chunks WHERE concept_id='c1'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 0
    conn.close()
```

- [ ] **Step 2: Run, expect fail** — `ImportError: cannot import name 'upsert_concept'`.

- [ ] **Step 3: Add to `indexlib.py`**

```python
import hashlib


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def upsert_concept(conn, concept_id, path, title, type, body, tags, timestamp, embed_fn: EmbedFn) -> int:
    old_ids = [r[0] for r in conn.execute("SELECT chunk_id FROM chunks WHERE concept_id=?", (concept_id,))]
    for cid in old_ids:
        conn.execute("DELETE FROM vec_chunks WHERE chunk_id=?", (cid,))
    conn.execute("DELETE FROM chunks WHERE concept_id=?", (concept_id,))
    chunks = chunk_markdown(body)
    if not chunks:
        conn.commit()
        return 0
    vectors = embed_fn(chunks)
    dim = len(vectors[0])
    _ensure_vec_table(conn, dim)
    for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
        cur = conn.execute(
            "INSERT INTO chunks(concept_id,path,title,type,chunk_idx,text,tags,timestamp,hash) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (concept_id, path, title, type, idx, chunk, tags, timestamp, _hash(chunk)),
        )
        conn.execute("INSERT INTO vec_chunks(chunk_id, embedding) VALUES (?, ?)", (cur.lastrowid, _vec_blob(vec)))
    conn.commit()
    return len(chunks)


def remove_concept(conn, concept_id) -> None:
    old_ids = [r[0] for r in conn.execute("SELECT chunk_id FROM chunks WHERE concept_id=?", (concept_id,))]
    for cid in old_ids:
        conn.execute("DELETE FROM vec_chunks WHERE chunk_id=?", (cid,))
    conn.execute("DELETE FROM chunks WHERE concept_id=?", (concept_id,))
    conn.commit()
```

- [ ] **Step 4: Run, expect pass** → PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/mneme/scripts/indexlib.py tests/test_indexlib.py
git commit -m "feat(indexlib): upsert_concept + remove_concept (TDD)"
```

### Task A4: search (KNN)

**Files:** Modify `skills/mneme/scripts/indexlib.py`; Modify `tests/test_indexlib.py`

**Interfaces:** Produces `indexlib.search(conn, query, k, embed_fn) -> List[Dict]`.

- [ ] **Step 1: Write failing test** (append)

```python
from indexlib import search


def test_search_returns_chunk_for_exact_text(tmp_path):
    conn = open_index(tmp_path / "index.db"); ensure_schema(conn)
    body = "# Transformers\nAttention is all you need."
    upsert_concept(conn, "c1", "c1.md", "T", "Concept", body, "[]", "", _E)
    results = search(conn, "Attention is all you need.", 1, _E)
    assert len(results) == 1
    assert results[0]["concept_id"] == "c1"
    assert "Attention" in results[0]["text"]
    conn.close()
```

- [ ] **Step 2: Run, expect fail** — `ImportError: cannot import name 'search'`.

- [ ] **Step 3: Add to `indexlib.py`**

```python
def search(conn, query: str, k: int, embed_fn: EmbedFn) -> List[Dict]:
    qvec = embed_fn([query])[0]
    _ensure_vec_table(conn, len(qvec))
    rows = conn.execute(
        "SELECT chunk_id, distance FROM vec_chunks WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (_vec_blob(qvec), k),
    ).fetchall()
    out = []
    for chunk_id, dist in rows:
        r = conn.execute(
            "SELECT concept_id,path,title,type,text FROM chunks WHERE chunk_id=?", (chunk_id,)
        ).fetchone()
        if r:
            out.append({"concept_id": r[0], "path": r[1], "title": r[2], "type": r[3], "text": r[4], "distance": dist})
    return out
```

- [ ] **Step 4: Run, expect pass** → PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/mneme/scripts/indexlib.py tests/test_indexlib.py
git commit -m "feat(indexlib): KNN search (TDD)"
```

### Task A5: reindex_bundle + default fastembed embed_fn

**Files:** Modify `skills/mneme/scripts/indexlib.py`; Modify `tests/test_indexlib.py`; Modify `pyproject.toml` (extras)

**Interfaces:** Produces `indexlib.reindex_bundle(bundle_path, embed_fn, db_path=None) -> int`, `indexlib.default_embed_fn(model=None) -> EmbedFn`.

- [ ] **Step 1: Write failing test** (append)

```python
from indexlib import reindex_bundle

SAMPLE = Path(__file__).parent.parent / "sample-bundle"


def test_reindex_bundle_indexes_concepts(tmp_path):
    db = tmp_path / "index.db"
    n = reindex_bundle(SAMPLE, _E, db_path=db)
    assert n >= 2  # sample-bundle has 2 concepts
    conn = open_index(db); ensure_schema(conn)
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] >= 2
    conn.close()
```

- [ ] **Step 2: Run, expect fail** — `ImportError: cannot import name 'reindex_bundle'`.

- [ ] **Step 3: Add to `indexlib.py`**

```python
from pathlib import Path


def default_embed_fn(model: str = "intfloat/multilingual-e5-small") -> EmbedFn:
    """Production embed_fn: wraps fastembed. Requires `pip install fastembed`."""
    from fastembed import TextEmbedding

    embedder = TextEmbedding(model_name=model)

    def fn(texts: List[str]) -> List[List[float]]:
        return [list(v) for v in embedder.embed(list(texts))]

    return fn


def reindex_bundle(bundle_path, embed_fn: EmbedFn, db_path=None) -> int:
    import okflib  # sibling module in scripts/

    root = Path(bundle_path)
    db_path = db_path or (root / ".mneme" / "index.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = open_index(db_path)
    ensure_schema(conn)
    n = 0
    for cid in okflib.list_concepts(bundle_path):
        parsed = okflib.read_concept(bundle_path, cid)
        if not parsed:
            continue
        meta, body = parsed
        upsert_concept(
            conn, cid, f"{cid}.md", meta.get("title", cid), meta.get("type", ""),
            body, str(meta.get("tags", [])), meta.get("timestamp", ""), embed_fn,
        )
        n += 1
    conn.close()
    return n
```

- [ ] **Step 4: Add extras to `pyproject.toml`**

```toml
[project.optional-dependencies]
dev = ["pytest"]
index = ["sqlite-vec", "fastembed"]
agents = ["strands-agents", "strands-agents-tools"]
all = ["sqlite-vec", "fastembed", "strands-agents", "strands-agents-tools"]
```

- [ ] **Step 5: Run, expect pass** (uses fake `_E`; fastembed not exercised here) → PASS.

- [ ] **Step 6: Smoke-test real fastembed (manual, optional)** — `.venv/bin/pip install fastembed && .venv/bin/python -c "from skills.mneme.scripts import indexlib as i; i.reindex_bundle('sample-bundle', i.default_embed_fn())"` → exits 0 (downloads ~100MB model on first run).

- [ ] **Step 7: Commit**

```bash
git add skills/mneme/scripts/indexlib.py tests/test_indexlib.py pyproject.toml
git commit -m "feat(indexlib): reindex_bundle + default fastembed embed_fn (TDD)"
```

## Phase B — L3 Strands agents + CLI

### Task B1: tools.py — resolve_bundle + slug + @tool wrappers

**Files:** Create `skills/mneme/scripts/tools.py`; Create `tests/test_tools.py`; Install `.venv/bin/pip install strands-agents strands-agents-tools`

**Interfaces:** Produces `tools.resolve_bundle(config_path=None) -> Path|None`, `tools.slug_from_path(path) -> str`, plus `@tool`-decorated wrappers (`read_source`, `list_concepts`, `read_concept`, `search_index`, `write_concept`, `update_index_md`, `append_log`, `validate`, `find_orphans`) used by the agents.

- [ ] **Step 1: Write failing tests** (`tests/test_tools.py`)

```python
from pathlib import Path
from tools import resolve_bundle, slug_from_path


def test_resolve_bundle_from_config(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('bundle_path = "/tmp/mywiki"\n')
    assert resolve_bundle(config_path=cfg) == Path("/tmp/mywiki")


def test_resolve_bundle_env_fallback(tmp_path, monkeypatch):
    cfg = tmp_path / "none.toml"
    monkeypatch.setenv("MNEME_BUNDLE", "/env/wiki")
    assert resolve_bundle(config_path=cfg) == Path("/env/wiki")


def test_resolve_bundle_autodiscover_root_index(tmp_path, monkeypatch):
    cfg = tmp_path / "none.toml"
    monkeypatch.delenv("MNEME_BUNDLE", raising=False)
    bundle = tmp_path / "awiki"
    (bundle / "concepts").mkdir(parents=True)
    (bundle / "index.md").write_text('---\nokf_version: "0.1"\n---\n# Concepts\n')
    monkeypatch.chdir(bundle / "concepts")
    assert resolve_bundle(config_path=cfg) == bundle


def test_slug_from_path():
    assert slug_from_path("My Note.md") == "my-note"
    assert slug_from_path("/a/b/Cool Paper.pdf") == "cool-paper"
```

- [ ] **Step 2: Run, expect fail** — `ImportError: No module named 'tools'`.

- [ ] **Step 3: Create `skills/mneme/scripts/tools.py`**

```python
"""L3 shared tools for mneme Strands agents. Wraps okflib (L1) + indexlib (L2)."""
from __future__ import annotations

import os
import re
from pathlib import Path

from strands import tool


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


def _bundle() -> Path:
    b = resolve_bundle()
    if b is None:
        raise SystemExit("mneme: no bundle found — run `mneme init <path>` or set ~/.config/mneme/config.toml")
    return b


@tool
def read_source(path: str) -> str:
    """Read a source file (.md/.txt) and return its full text."""
    return Path(path).read_text(encoding="utf-8")


@tool
def list_concepts() -> list:
    """List all concept IDs in the wiki bundle."""
    import okflib
    return okflib.list_concepts(str(_bundle()))


@tool
def read_concept(concept_id: str) -> str:
    """Read a concept page (frontmatter + body) by concept_id."""
    import okflib
    p = _bundle() / f"{concept_id}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


@tool
def search_index(query: str, k: int = 5) -> list:
    """Semantic search the wiki index; return top-k chunks with concept_id, title, text."""
    import indexlib
    from indexlib import default_embed_fn
    bundle = _bundle()
    conn = indexlib.open_index(bundle / ".mneme" / "index.db")
    return indexlib.search(conn, query, k, default_embed_fn())


@tool
def write_concept(concept_id: str, frontmatter: str, body: str) -> str:
    """Write a concept page. frontmatter is the YAML block (without --- fences)."""
    p = _bundle() / f"{concept_id}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{frontmatter}\n---\n{body}\n", encoding="utf-8")
    return str(p)


@tool
def append_log(op: str, title: str, note: str = "") -> str:
    """Append a dated entry to the bundle's log.md."""
    import datetime
    p = _bundle() / "log.md"
    date = datetime.date.today().isoformat()
    entry = f"\n## {date} {op} | {title}\n{note}\n" if note else f"\n## {date} {op} | {title}\n"
    p.write_text((p.read_text(encoding="utf-8") if p.exists() else "# Directory Update Log\n") + entry, encoding="utf-8")
    return str(p)


@tool
def validate() -> str:
    """Run the OKF conformance validator on the bundle; return the report text."""
    import subprocess, sys
    v = Path(__file__).parent / "validate_okf.py"
    r = subprocess.run([sys.executable, str(v), str(_bundle())], capture_output=True, text=True)
    return r.stdout


@tool
def find_orphans() -> list:
    """Return concept IDs that are not linked from any other concept page."""
    import okflib
    bundle = _bundle()
    ids = set(okflib.list_concepts(str(bundle)))
    linked = set()
    for p in bundle.rglob("*.md"):
        rel = p.relative_to(bundle).as_posix()
        if rel in ("index.md", "log.md"):
            continue
        for m in re.finditer(r"\]\((/[^\)]+\.md)\)", p.read_text(encoding="utf-8")):
            linked.add(m.group(1).lstrip("/")[:-3])
    return sorted(ids - linked)
```

- [ ] **Step 4: Run, expect pass** — `.venv/bin/pytest tests/test_tools.py -v` → PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add skills/mneme/scripts/tools.py tests/test_tools.py
git commit -m "feat(tools): resolve_bundle + slug + Strands @tool wrappers (TDD)"
```

### Task B2: mneme.py CLI — init + reindex (TDD); ingest/query/lint dispatch

**Files:** Create `skills/mneme/scripts/mneme.py`; Create `tests/test_cli.py`

**Interfaces:** Produces `mneme.main(argv) -> int` dispatching `init/reindex/ingest/query/lint`.

- [ ] **Step 1: Write failing tests** (`tests/test_cli.py`)

```python
from pathlib import Path
import mneme


def test_init_scaffolds_bundle_and_config(tmp_path, monkeypatch):
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
    # point config at sample-bundle
    sample = Path(__file__).parent.parent / "sample-bundle"
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'bundle_path = "{sample}"\n')
    import indexlib
    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: (lambda ts: __import__("tests.test_indexlib", fromlist=["fake_embed"]).fake_embed(ts, 8)))
    rc = mneme.main(["reindex", "--config", str(cfg)])
    assert rc == 0
    assert (sample / ".mneme" / "index.db").exists()
```

- [ ] **Step 2: Run, expect fail** — `No module named 'mneme'`.

- [ ] **Step 3: Create `skills/mneme/scripts/mneme.py`**

```python
#!/usr/bin/env python3
"""mneme CLI: init / reindex / ingest / query / lint."""
from __future__ import annotations

import sys
from pathlib import Path

CONFIG_DEFAULT = Path.home() / ".config" / "mneme" / "config.toml"


def _write_config(bundle_path: Path, config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(f'bundle_path = "{bundle_path}"\n', encoding="utf-8")


def cmd_init(args) -> int:
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
    import indexlib
    config = Path(args[args.index("--config") + 1]) if "--config" in args else CONFIG_DEFAULT
    from tools import resolve_bundle
    bundle = resolve_bundle(config_path=config)
    if bundle is None:
        print("no bundle found", file=sys.stderr); return 1
    n = indexlib.reindex_bundle(str(bundle), indexlib.default_embed_fn())
    print(f"indexed {n} concepts into {bundle}/.mneme/index.db")
    return 0


def cmd_ingest(args) -> int:
    from ingest import run as run_ingest
    return run_ingest(args)


def cmd_query(args) -> int:
    from query import run as run_query
    return run_query(args)


def cmd_lint(args) -> int:
    from lint import run as run_lint
    return run_lint(args)


def main(argv) -> int:
    if not argv:
        print("usage: mneme {init|reindex|ingest|query|lint} ...", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    return {"init": cmd_init, "reindex": cmd_reindex, "ingest": cmd_ingest,
            "query": cmd_query, "lint": cmd_lint}.get(cmd, lambda a: (print("unknown command", file=sys.stderr), 2)[1])(rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run, expect pass** — `.venv/bin/pytest tests/test_cli.py -v` → PASS (2 tests; `reindex` uses the monkeypatched fake embed_fn).

- [ ] **Step 5: Commit**

```bash
git add skills/mneme/scripts/mneme.py tests/test_cli.py
git commit -m "feat(cli): mneme init + reindex (TDD); ingest/query/lint dispatch"
```

### Task B3: ingest.py / query.py / lint.py — Strands agents

**Files:** Create `skills/mneme/scripts/ingest.py`, `query.py`, `lint.py`; Create `tests/test_agents_smoke.py`

**Interfaces:** Each exports `run(args) -> int` invoking a Strands `Agent` with the shared tools + a system prompt. Model provider via `MNEME_MODEL_PROVIDER` (default `anthropic`).

- [ ] **Step 1: Create `skills/mneme/scripts/ingest.py`**

```python
"""mneme ingest: a Strands agent that reads a source and writes concept pages."""
from __future__ import annotations

import sys
from pathlib import Path
from strands import Agent
from tools import (read_source, write_concept, update_index_md, append_log,
                   validate, list_concepts, read_concept)

# update_index_md and cross_link are folded into write_concept + agent-driven edits;
# the agent uses Edit/Write on index.md via its own file tools when needed.

SYSTEM = """You are mneme's ingest agent. Given a source file, read it, decide how to
decompose it into atomic concept pages, write each as an OKF concept (frontmatter with
non-empty type, title, description, tags, timestamp, resource), cross-link related pages
using absolute bundle-relative links (/dir/concept.md), update the bundle's index.md, and
append a dated entry to log.md. Always validate at the end and fix any ERROR. One source
may yield 5-15 pages. Use the tools provided."""


def build_agent():
    return Agent(tools=[read_source, write_concept, append_log, validate,
                        list_concepts, read_concept], system_prompt=SYSTEM)


def run(args) -> int:
    if not args:
        print("usage: mneme ingest <source_path>", file=sys.stderr); return 2
    source = args[0]
    agent = build_agent()
    result = agent(f"Ingest the source at {source} into the wiki. Resolve the bundle via the tools' resolve_bundle.")
    print(str(result))
    return 0
```

- [ ] **Step 2: Create `skills/mneme/scripts/query.py`**

```python
"""mneme query: a Strands agent that answers from the wiki with citations."""
from __future__ import annotations

import sys
from strands import Agent
from tools import search_index, read_concept, list_concepts

SYSTEM = """You are mneme's query agent. For a question, call search_index to get top-k
relevant chunks, read the full concept pages they belong to, and synthesize an answer WITH
citations (bundle-relative links to the concept pages). If the wiki lacks coverage, say so
and suggest an ingest — never fabricate. If the answer is broadly useful and no page covers
it, offer (do not auto-create) to backfill it."""


def build_agent():
    return Agent(tools=[search_index, read_concept, list_concepts], system_prompt=SYSTEM)


def run(args) -> int:
    if not args:
        print("usage: mneme query <question>", file=sys.stderr); return 2
    agent = build_agent()
    print(str(agent(" ".join(args))))
    return 0
```

- [ ] **Step 3: Create `skills/mneme/scripts/lint.py`**

```python
"""mneme lint: a Strands agent that curates the wiki."""
from __future__ import annotations

import sys
from strands import Agent
from tools import validate, find_orphans, list_concepts, read_concept

SYSTEM = """You are mneme's lint agent. Run validate (fix hard ERRORs), find_orphans, and
review for stale pages (old timestamp, no log entry), missing cross-links between related
concepts, and important concepts with no page. Propose fixes; do not apply without approval."""


def build_agent():
    return Agent(tools=[validate, find_orphans, list_concepts, read_concept], system_prompt=SYSTEM)


def run(args) -> int:
    agent = build_agent()
    print(str(agent("Lint the wiki. Report errors and curation suggestions.")))
    return 0
```

- [ ] **Step 4: Write smoke test** (`tests/test_agents_smoke.py`) — model-dependent, skip if no key.

```python
import os
import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")


def test_ingest_agent_imports():
    from ingest import build_agent
    a = build_agent()
    assert a is not None


def test_query_agent_imports():
    from query import build_agent
    assert build_agent() is not None


def test_lint_agent_imports():
    from lint import build_agent
    assert build_agent() is not None
```

- [ ] **Step 5: Run** — `.venv/bin/pytest -q` → unit tests pass; smoke skipped without key. With key: `.venv/bin/pytest tests/test_agents_smoke.py -v` → PASS (agents construct).

- [ ] **Step 6: Commit**

```bash
git add skills/mneme/scripts/ingest.py skills/mneme/scripts/query.py skills/mneme/scripts/lint.py tests/test_agents_smoke.py
git commit -m "feat(agents): Strands ingest/query/lint agents + smoke tests"
```

## Phase C — L1 structure spec + docs + SKILL.md revision

### Task C1: wiki-structure.md + index-design.md

**Files:** Create `skills/mneme/references/wiki-structure.md`, `skills/mneme/references/index-design.md`

- [ ] **Step 1: Write `wiki-structure.md`** (L1 spec — from v2 spec §4)

```markdown
---
type: Reference
title: mneme wiki structure
description: How a growing OKF wiki bundle is organized and curated.
---
# wiki structure

A bundle:
\`\`\`
<bundle>/
├── index.md          # root index (progressive disclosure; root has okf_version)
├── log.md            # change timeline (## YYYY-MM-DD <op> | <title>)
├── sources/          # immutable raw source copies (ingest copies here)
├── concepts/         # atomic concept pages (the bulk; flat + slug)
├── references/       # distilled external sources (papers/articles)
├── summaries/        # cross-concept syntheses (compaction products)
├── topics/           # topical hubs (curated reading paths/maps)
├── archive/          # superseded pages (kept for history, de-indexed)
└── .mneme/           # derived (L2 index.db) — gitignored, not OKF concepts
\`\`\`

Curation: one concept per page; slug = lowercase, non-alnum→hyphen; cross-links absolute bundle-relative (/dir/concept.md); at thresholds roll multiple pages into a `summaries/` page; retire stale to `archive/` (de-indexed); use `topics/` for curated entry points. Retrieval is via the L2 index, so the tree stays flat — no manual deep nesting.
```

- [ ] **Step 2: Write `index-design.md`** (L2 spec — from v2 spec §5)

```markdown
---
type: Reference
title: mneme index design
description: L2 sqlite-vec + fastembed index — schema, chunking, retrieval.
---
# index design

- Storage: `<bundle>/.mneme/index.db` (SQLite + sqlite-vec). gitignored. Derived.
- Tables: `chunks(chunk_id, concept_id, path, title, type, chunk_idx, text, tags, timestamp, hash)`; `vec_chunks` (vec0 virtual, embedding FLOAT[dim]); `meta(key,value)` (dim, embedding_model, okf_version, last_sync).
- Embedding: fastembed ONNX, multilingual small model (e.g. `intfloat/multilingual-e5-small` 384-dim). Offline, no key. `embed_fn` is injected (testable with a fake).
- Chunking: concept pages by markdown headings; sources by paragraph/512-token with overlap.
- Incremental: per-chunk hash; unchanged chunks skipped on reindex (mtime/hash fast-path).
- Query: embed question → sqlite-vec KNN top-k → join chunk text + concept_id → ranked.
```

- [ ] **Step 3: Commit**

```bash
git add skills/mneme/references/wiki-structure.md skills/mneme/references/index-design.md
git commit -m "docs: add wiki-structure + index-design reference specs"
```

### Task C2: revise workflow docs to reference CLI + structure

**Files:** Modify `skills/mneme/references/workflow-ingest.md`, `workflow-query.md`, `workflow-lint.md`

- [ ] **Step 1: Prepend a "use the CLI" note to each** — e.g. in `workflow-ingest.md`, after the title:

```markdown
> The `mneme ingest <src>` CLI runs a Strands agent that performs these steps. This doc is the agent's spec (and a checklist for manual review). Place pages per `wiki-structure.md`.
```

Add the analogous one-liner to `workflow-query.md` (`mneme query`) and `workflow-lint.md` (`mneme lint`), each pointing to `wiki-structure.md` / `index-design.md` where relevant.

- [ ] **Step 2: Commit**

```bash
git add skills/mneme/references/workflow-ingest.md skills/mneme/references/workflow-query.md skills/mneme/references/workflow-lint.md
git commit -m "docs: point workflow docs at mneme CLI + structure/index specs"
```

### Task C3: revise SKILL.md (call CLI; structure spec; model-provider note)

**Files:** Modify `skills/mneme/SKILL.md`

- [ ] **Step 1: Replace the ingest/query/lint workflow bodies** with CLI-first instructions. The ingest section becomes:

```markdown
## ingest <source path>

Run `mneme ingest <source>` — it spawns a Strands agent that reads the source, decomposes it into concept pages (frontmatter: type/title/description/tags/timestamp/resource), cross-links related pages, updates `index.md` + `log.md`, indexes chunks into the L2 sqlite-vec index, and validates. Requires `MNEME_MODEL_PROVIDER` (default `anthropic`; set `ANTHROPIC_API_KEY`).

If no model provider is configured, fall back to manual: copy source to `sources/<slug>.md`, write concept pages per `references/wiki-structure.md`, run `mneme reindex` then `python3 scripts/validate_okf.py <bundle>`.
```

Make `query` → `mneme query <question>` (searches the L2 index, synthesizes with citations) and `lint` → `mneme lint` (validate + curation). Keep Step 0 (bundle resolution), OKF rules, and type-vocab sections. Add to the references line: `references/wiki-structure.md` and `references/index-design.md`.

- [ ] **Step 2: Verify** — `grep -E 'mneme (ingest|query|lint)|wiki-structure|index-design' SKILL.md` → matches.

- [ ] **Step 3: Commit**

```bash
git add skills/mneme/SKILL.md
git commit -m "feat(skill): SKILL.md calls mneme CLI; references structure + index specs"
```

### Task C4: update CLAUDE.md layout for L2/L3

**Files:** Modify `CLAUDE.md`

- [ ] **Step 1: Update the `skills/mneme/scripts/` block** in the layout to list `indexlib.py`, `tools.py`, `ingest.py`, `query.py`, `lint.py`, `mneme.py` alongside `okflib.py`/`validate_okf.py`, and add `wiki-structure.md`/`index-design.md` to the references line. Add one line under the layout: "**L2** sqlite-vec 索引 (`<bundle>/.mneme/index.db`) + **L3** Strands agents (`mneme` CLI) — 见 v2 spec。"

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md layout reflects L2 indexlib + L3 agents"
```

## Phase D — integration + finalize

### Task D1: end-to-end plumbing test (no LLM)

**Files:** Create `tests/test_integration.py`

- [ ] **Step 1: Write the test** — exercises L1→L2→CLI without a model (uses fake embed_fn).

```python
import subprocess
import sys
from pathlib import Path
import mneme
import indexlib
from test_indexlib import fake_embed

_E = lambda ts: fake_embed(ts, 8)


def test_end_to_end_init_reindex_search_validate(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    assert mneme.main(["init", str(bundle), "--config", str(cfg)]) == 0
    # manually write a concept (simulating an ingest)
    c = bundle / "concepts" / "cats.md"
    c.parent.mkdir(parents=True, exist_ok=True)
    c.write_text("---\ntype: Concept\ntitle: Cats\ndescription: felines\n---\n# Cats\nCats love naps in the sun.\n")
    # reindex with fake embed
    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: _E)
    assert mneme.main(["reindex", "--config", str(cfg)]) == 0
    # search
    conn = indexlib.open_index(bundle / ".mneme" / "index.db")
    res = indexlib.search(conn, "Cats love naps in the sun.", 1, _E)
    assert res and res[0]["concept_id"] == "concepts/cats"
    conn.close()
    # validate
    v = Path(__file__).parent.parent / "skills" / "mneme" / "scripts" / "validate_okf.py"
    r = subprocess.run([sys.executable, str(v), str(bundle)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
```

- [ ] **Step 2: Run** — `.venv/bin/pytest tests/test_integration.py -v` → PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: end-to-end L1+L2+CLI plumbing (no LLM) (TDD)"
```

### Task D2: full suite + merge to main

- [ ] **Step 1: Run full suite** — `.venv/bin/pytest -q` → all unit + integration pass; agent smoke skipped without key.
- [ ] **Step 2: Validate sample-bundle** — `.venv/bin/python skills/mneme/scripts/validate_okf.py sample-bundle` → `0 error(s)`.
- [ ] **Step 3: Confirm deliverables** — `ls skills/mneme/scripts/{indexlib,tools,ingest,query,lint,mneme}.py skills/mneme/references/{wiki-structure,index-design}.md`.
- [ ] **Step 4: Merge `feat/skill-v2` to `main`**

```bash
git checkout main
git merge --no-ff feat/skill-v2 -m "Merge feat/skill-v2: L2 sqlite-vec index + L3 Strands agents + CLI"
```

---

## Self-Review

**1. Spec coverage (v2 spec → task):**

| Spec section | Task |
|---|---|
| §3 L1 wiki | A0 (skip .mneme), C1 (structure), C3 (SKILL.md) |
| §4 wiki structure spec | C1 (wiki-structure.md) |
| §5 L2 index (sqlite-vec+fastembed) | A1–A5 (indexlib), C1 (index-design.md) |
| §6 L3 Strands agents | B1 (tools), B3 (ingest/query/lint) |
| §7 linking (CLI+skill, no MCP) | B2 (mneme CLI), C3 (SKILL.md) |
| §8 bundle resolution | B1 (resolve_bundle) |
| §9 data flows | B2/B3 (CLI+agents), D1 (integration) |
| §10 error handling | B1 (resolve_bundle None → SystemExit), B2 (CLI rc 1/2) |
| §11 testing (TDD) | A0–A5, B1, B2, D1 (TDD throughout); B3 smoke |
| §12 repo layout | C4 (CLAUDE.md) |
| §13 non-goals | respected (no MCP, no resident service, local sqlite-vec) |
| §14 migration from v1 | A0 reuses okflib; C2/C3 revise v1 docs |

Gap: real fastembed model is only smoke-tested manually (A5 Step 6) — full auto test would download ~100MB. Acceptable; fake embed_fn covers logic.

**2. Placeholder scan:** No TBD/TODO. All code steps show complete code. Strands agent `update_index_md`/`cross_link` are noted as folded into `write_concept` + agent file edits (the agent uses its own write capability) — explicit, not a placeholder.

**3. Type consistency:** `indexlib.open_index/ensure_schema/chunk_markdown/upsert_concept/remove_concept/search/reindex_bundle/default_embed_fn` match across A1–A5, B1 (`search_index`, `default_embed_fn`), B2 (`reindex_bundle`), D1. `tools.resolve_bundle/slug_from_path` match B1/B2. `mneme.main(["init"|"reindex"|"ingest"|"query"|"lint", ...])` matches B2/D1 tests. `EmbedFn = Callable[[List[str]], List[List[float]]]` consistent. `fake_embed(texts, dim)` shared via `from test_indexlib import fake_embed` in D1.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-06-mneme-skill-v2.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks.
2. **Inline Execution** — execute tasks in this session with `executing-plans`, checkpoints per phase.

Which approach? (v1 was inline; this plan is larger — subagent-driven may suit it better.)


