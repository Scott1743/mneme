from indexlib import open_index, ensure_schema, chunk_markdown


def test_open_index_creates_schema(tmp_path):
    conn = open_index(tmp_path / "index.db")
    ensure_schema(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "chunks" in tables
    assert "meta" in tables
    conn.close()


def test_chunk_markdown_splits_by_headings():
    chunks = chunk_markdown("# Title\nbody1\n## Sub\nbody2\n")
    assert len(chunks) == 2
    assert "Title" in chunks[0] and "body1" in chunks[0]
    assert "Sub" in chunks[1]


def test_chunk_markdown_no_headings_returns_one():
    assert len(chunk_markdown("just text\nmore\n")) == 1
