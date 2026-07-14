from __future__ import annotations

import sqlite3

import pytest

from mneme import indexlib


def _page(bundle, name: str, body: str) -> None:
    path = bundle / "concepts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntype: Concept\ntitle: Test\ntags: [test]\n---\n" + body,
        encoding="utf-8",
    )


def test_reindex_skips_invalid_pages_and_replaces_snapshot(tmp_path):
    bundle = tmp_path / "wiki"
    _page(bundle, "old.md", "old needle")
    bad = bundle / "concepts" / "bad.md"
    bad.write_text("no frontmatter", encoding="utf-8")
    assert indexlib.reindex_paths(sorted((bundle / "concepts").glob("*.md")), bundle) == 1

    (bundle / "concepts" / "old.md").unlink()
    _page(bundle, "new.md", "new needle")
    assert indexlib.reindex_paths(sorted((bundle / "concepts").glob("*.md")), bundle) == 1
    conn = sqlite3.connect(bundle / ".mneme" / "index.db")
    try:
        assert conn.execute("SELECT path FROM pages").fetchall() == [("concepts/new.md",)]
    finally:
        conn.close()


def test_search_validates_input_and_missing_index(tmp_path):
    db = tmp_path / "missing.db"
    with pytest.raises(ValueError):
        indexlib.search("", db)
    with pytest.raises(indexlib.IndexNotFoundError):
        indexlib.search("query", db)
