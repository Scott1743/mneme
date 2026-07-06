from pathlib import Path

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


from indexlib import reindex_bundle

SAMPLE = Path(__file__).parent.parent / "sample-bundle"


def test_reindex_bundle_indexes_concepts(tmp_path):
    db = tmp_path / "index.db"
    n = reindex_bundle(SAMPLE, _E, db_path=db)
    assert n >= 2  # sample-bundle has 2 concepts
    conn = open_index(db); ensure_schema(conn)
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] >= 2
    conn.close()
