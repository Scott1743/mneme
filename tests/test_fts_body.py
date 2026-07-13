"""Task 3: FTS5 schema with `body`, populated by reindex.

The v2.0 L1 index is a zero-dep sqlite3 + FTS5 database. The `pages`
table carries the frontmatter-derived columns plus the full markdown
`body`; the `pages_fts` virtual table mirrors them so a MATCH query
can find words that only appear in the body (e.g. long paragraphs,
code blocks, embedded prose) and not in `title` / `description` /
`tags`.

`reindex_paths(paths, bundle)` is the atomic snapshot rebuild entry
point: it writes the new index into a temp database, fsyncs it, and
renames it into place so a crash mid-build never leaves the live
`bundle/.mneme/index.db` in a torn state.
"""
from __future__ import annotations

import sqlite3

import pytest
pytestmark = pytest.mark.unit

from mneme import indexlib


def test_ensure_schema_has_body_column_and_fts():
    conn = sqlite3.connect(":memory:")
    indexlib.ensure_schema(conn)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(pages)").fetchall()]
    assert "body" in cols, "pages.body column missing — FTS5 needs body to be searchable"
    assert conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE name='pages_fts'"
    ).fetchone()[0] == 1, "pages_fts virtual table missing"


def test_snippet_finds_body_only_word(tmp_path):
    bundle = tmp_path / "wiki"
    (bundle / "concepts").mkdir(parents=True)
    (bundle / "concepts" / "a.md").write_text(
        "---\n"
        "type: Concept\n"
        "title: A\n"
        "description: alpha\n"
        "tags: [x]\n"
        "timestamp: 2026-07-13T00:00:00Z\n"
        "---\n"
        "# body\n"
        "rareword appears here\n"
    )
    (bundle / "index.md").write_text("# Index\n")
    indexed = indexlib.reindex_paths([bundle / "concepts" / "a.md"], bundle)
    assert indexed == 1, "reindex_paths should report one page indexed"
    conn = sqlite3.connect(bundle / ".mneme" / "index.db")
    try:
        # FTS5 snippet() uses 0-based column indexing. With the schema
        # `title, description, tags, body`, `body` is column 3. The plan
        # snippet called column 4; that's out of range for a 4-column
        # virtual table. We pin column 3 to assert the body is what
        # snippet() pulls the highlight from.
        rows = conn.execute(
            "SELECT snippet(pages_fts, 3, '|', '|', '…', 8) "
            "FROM pages_fts WHERE pages_fts MATCH ?",
            ("rareword",),
        ).fetchall()
        assert rows, "snippet should match rareword in body"
        # The snippet column must contain the highlighted rareword; if
        # column 3 is wired to body, the highlight shows up here.
        snippet = rows[0][0]
        assert snippet and "rareword" in snippet, (
            f"snippet should highlight rareword from body column; got {snippet!r}"
        )
    finally:
        conn.close()