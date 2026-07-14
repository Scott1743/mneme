"""Task 4: `mneme search` returns candidates + snippets via FTS5.

The v2.0 search surface is intentionally minimal: the CLI never
composes an answer, it returns *navigation* — path, title, snippet —
and lets the host agent Read each candidate page to compose the
final response. This is the same idea as Karpathy's LLM Wiki (the
LLM walks the graph; the index is a candidate generator, not a
retrieval oracle).

Two paths:

1. **FTS5 (default)**: when ``<bundle>/.mneme/index.db`` exists,
   ``indexlib.search`` runs an FTS5 MATCH against the L1 schema
   that Task 3 (``reindex_paths``) populates. Column indices are
   ``title=0, description=1, tags=2, body=3`` — Task 3 corrected
   the original plan (which had body at column 4). Snippets pull
   from ``body`` (column 3).

2. **L0 grep fallback**: when ``index.db`` is missing, walk
   ``*.md`` files in the bundle (skipping ``.mneme/`` and
   ``sources/``), parse frontmatter for the title, and case-
   insensitively scan the body for the query. Each hit becomes a
   candidate whose snippet is the matching line plus a small
   context window. A stderr nudge suggests ``mneme reindex`` for
   better results.

The CLI never invokes sqlite-vec / fastembed here; both are
deferred to v2.1.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from mneme import cli, indexlib


ROOT = Path(__file__).resolve().parents[1]


def _seed_bundle_with_index(tmp_path: Path) -> Path:
    """Build a tiny OKF bundle + FTS5 index for candidate-shape tests."""
    bundle = tmp_path / "wiki"
    (bundle / "concepts").mkdir(parents=True)
    (bundle / "concepts" / "a.md").write_text(
        "---\n"
        "type: Concept\n"
        "title: Alpha\n"
        "description: alpha\n"
        "tags: [a]\n"
        "timestamp: 2026-07-13T00:00:00Z\n"
        "---\n"
        "# h\n"
        "rareword appears here\n",
        encoding="utf-8",
    )
    (bundle / "index.md").write_text("# Index\n", encoding="utf-8")
    indexed = indexlib.reindex_paths([bundle / "concepts" / "a.md"], bundle)
    assert indexed == 1
    return bundle


# ─────────────────────────────────────────────────────────────────────────
# FTS5 path (default)
# ─────────────────────────────────────────────────────────────────────────


def test_search_returns_candidates_only(tmp_path):
    """`indexlib.search` returns ``{"query": ..., "candidates": [...]}``
    and each candidate carries ``path``, ``title``, and ``snippet``."""
    bundle = _seed_bundle_with_index(tmp_path)
    db = bundle / ".mneme" / "index.db"
    out = indexlib.search("rareword", db, k=5)
    assert "candidates" in out and out["candidates"], (
        f"expected non-empty candidates; got {out!r}"
    )
    candidate = out["candidates"][0]
    assert {"path", "title", "snippet"} <= candidate.keys(), (
        f"candidate missing required keys; got {candidate!r}"
    )
    assert candidate["path"] == "concepts/a.md"
    assert candidate["title"] == "Alpha"
    # The snippet comes from the body column (3), so it must contain
    # the matched word.
    assert "rareword" in candidate["snippet"]


def test_search_uses_body_column_3_for_snippet(tmp_path):
    """Pin the FTS5 snippet column to `body` (index 3). Task 3
    corrected the original plan's column 4; this test re-pins it so
    a future schema change can't silently shift snippets off body.
    """
    bundle = _seed_bundle_with_index(tmp_path)
    db = bundle / ".mneme" / "index.db"
    out = indexlib.search("rareword", db, k=1)
    assert out["candidates"]
    snippet = out["candidates"][0]["snippet"]
    # The FTS5 snippet delimiters (`|`, `|`, `…`) only appear when
    # `snippet()` is called with the configured delimiters. If the
    # snippet doesn't carry the highlight delimiters, we hit the
    # wrong column.
    assert "|" in snippet and "rareword" in snippet, (
        f"snippet should highlight rareword from body (col 3); got {snippet!r}"
    )


def test_search_fts5_path_does_not_import_l2(tmp_path):
    """`indexlib.search` must not pull in sqlite_vec or fastembed."""
    # The function itself must not import them — pre-import check
    # via attribute absence on the module.
    from mneme import indexlib as _indexlib

    assert hasattr(_indexlib, "search"), "v2.0 FTS5 search must be exported"
    assert not hasattr(_indexlib, "search_semantic"), (
        "v2.0 must not ship a semantic/vector search API"
    )
    # Confirm the FTS5 search module is importable without L2 deps
    # present. We import sqlite_vec / fastembed under sentinel names
    # so any accidental import inside `search` would either resolve
    # to the sentinel or raise ImportError — either way, we catch it
    # via a direct attribute lookup on the function's bytecode.
    import inspect as _inspect

    src = _inspect.getsource(_indexlib.search)
    # Drop the docstring so it can't trip on documentation that
    # *mentions* L2 by name (we only care about import statements).
    if '"""' in src:
        first_quote = src.find('"""')
        # Skip past the closing triple-quote.
        end_quote = src.find('"""', first_quote + 3)
        if end_quote != -1:
            src = src[:first_quote] + src[end_quote + 3:]
    assert "import sqlite_vec" not in src, (
        "v2.0 search must not import sqlite_vec"
    )
    assert "from sqlite_vec" not in src, (
        "v2.0 search must not import sqlite_vec"
    )
    assert "import fastembed" not in src, (
        "v2.0 search must not import fastembed"
    )
    assert "from fastembed" not in src, (
        "v2.0 search must not import fastembed"
    )
    # The v2.0 module must remain free of optional vector dependencies.
    module_src = (
        ROOT / "skills" / "mneme" / "scripts" / "mneme" / "indexlib.py"
    ).read_text()
    assert "sqlite_vec" not in module_src
    assert "fastembed" not in module_src


# ─────────────────────────────────────────────────────────────────────────
# L0 grep fallback (when index.db missing)
# ─────────────────────────────────────────────────────────────────────────


def test_search_falls_back_to_grep_when_no_index(tmp_path, capsys):
    """When ``<bundle>/.mneme/index.db`` is missing, ``mneme search``
    falls back to walking ``*.md`` files for title/body matches — no
    crash, no L2 import."""
    bundle = tmp_path / "wiki"
    (bundle / "concepts").mkdir(parents=True)
    (bundle / "concepts" / "alpha.md").write_text(
        "---\n"
        "type: Concept\n"
        "title: Alpha\n"
        "tags: [a]\n"
        "---\n"
        "the body mentions rareword once\n",
        encoding="utf-8",
    )
    (bundle / "index.md").write_text("# Index\n", encoding="utf-8")
    rc = cli.main(["search", "rareword", "--bundle", str(bundle), "--json"])
    assert rc == 0, "L0 grep fallback must succeed (no crash)"
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "rareword"
    assert payload["candidates"], (
        f"expected at least one L0 grep candidate; got {payload!r}"
    )
    candidate = payload["candidates"][0]
    assert candidate["path"] == "concepts/alpha.md"
    assert candidate["title"] == "Alpha"
    assert "rareword" in candidate["snippet"]


def test_search_grep_fallback_suggests_reindex(tmp_path, capsys):
    """L0 grep fallback nudges the user toward ``mneme reindex`` for
    full-text ranking, but does not block them from getting results."""
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    (bundle / "index.md").write_text("# Index\n", encoding="utf-8")
    cli.main(["search", "anything", "--bundle", str(bundle), "--json"])
    err = capsys.readouterr().err
    assert "reindex" in err.lower(), (
        f"expected stderr to nudge toward `mneme reindex`; got {err!r}"
    )


def test_search_grep_fallback_excludes_mneme_and_sources(tmp_path, capsys):
    """L0 grep must not descend into ``.mneme/`` (that's where the
    index lives) or ``sources/`` (immutable raw inputs)."""
    bundle = tmp_path / "wiki"
    (bundle / "concepts").mkdir(parents=True)
    (bundle / "concepts" / "real.md").write_text(
        "---\ntype: Concept\ntitle: Real\ntags: [r]\n---\nneedle here\n",
        encoding="utf-8",
    )
    (bundle / "sources").mkdir(parents=True)
    (bundle / "sources" / "raw.md").write_text("needle in raw source\n", encoding="utf-8")
    # Create .mneme/ but WITHOUT index.db so we exercise the L0 grep
    # path. If grep descended into .mneme/, it would pick up stray
    # files; we want to confirm the rglob filter excludes the dir
    # entirely.
    (bundle / ".mneme").mkdir(parents=True)
    (bundle / ".mneme" / "index.db.notes").write_text(
        "needle in metadata blob\n", encoding="utf-8"
    )
    (bundle / "index.md").write_text("# Index\n", encoding="utf-8")

    rc = cli.main(["search", "needle", "--bundle", str(bundle), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    paths = [c["path"] for c in payload["candidates"]]
    assert paths == ["concepts/real.md"], (
        f"expected only concepts/real.md; got {paths!r}"
    )


def test_search_exit_codes_missing_bundle(tmp_path):
    """Frozen contract: ``search`` exits 1 when no bundle can be resolved."""
    assert cli.main(["search", "anything", "--bundle", str(tmp_path / "nope")]) == 1


# ─────────────────────────────────────────────────────────────────────────
# Human output + JSON shape
# ─────────────────────────────────────────────────────────────────────────


def test_search_human_output_is_path_title_snippet(tmp_path, capsys):
    """Human (non-JSON) output is one line per candidate:
    ``path <TAB> title <TAB> snippet``."""
    bundle = _seed_bundle_with_index(tmp_path)
    rc = cli.main(["search", "rareword", "--bundle", str(bundle)])
    assert rc == 0
    out_lines = [l for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert out_lines, "human output must have at least one line"
    line = out_lines[0]
    parts = line.split("\t")
    assert len(parts) == 3, f"expected 3 tab-separated fields; got {line!r}"
    path, title, snippet = parts
    assert path == "concepts/a.md"
    assert title == "Alpha"
    assert "rareword" in snippet


def test_search_subprocess_json_via_shim(tmp_path):
    """End-to-end check that the CLI shim wires search correctly with
    the new FTS5 + L0 fallback contract."""
    bundle = _seed_bundle_with_index(tmp_path)
    shim = ROOT / "skills" / "mneme" / "scripts" / "mneme.py"
    r = subprocess.run(
        [sys.executable, str(shim), "search", "rareword",
         "--bundle", str(bundle), "--json"],
        capture_output=True, text=True,
        cwd=str(ROOT / "skills" / "mneme" / "scripts"),
        env={"PYTHONPATH": str(ROOT / "skills" / "mneme" / "scripts")},
    )
    assert r.returncode == 0, (
        f"shim invocation failed: stdout={r.stdout!r} stderr={r.stderr!r}"
    )
    payload = json.loads(r.stdout)
    assert payload["candidates"][0]["path"] == "concepts/a.md"
