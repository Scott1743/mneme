import hashlib
from pathlib import Path

import pytest

from mneme.indexlib import (
    CorruptIndexError,
    Embedder,
    IndexNotFoundError,
    chunk_markdown,
    ensure_schema,
    iter_indexable_concepts,
    open_index,
    read_index_meta,
    reindex_bundle,
    remove_concept,
    search,
    search_bundle,
    upsert_concept,
)


def fake_embed(texts, dim=8):
    out = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        out.append([(byte - 128) / 128.0 for byte in (digest * 2)[:dim]])
    return out


_E = Embedder(lambda texts: fake_embed(texts, 8), model_name="test-8d")


def write_concept(root: Path, rel: str, title: str, body: str, concept_type="Concept"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntype: {concept_type}\ntitle: {title}\n---\n# {title}\n{body}\n",
        encoding="utf-8",
    )
    return path


def test_open_index_creates_schema(tmp_path):
    conn = open_index(tmp_path / "index.db")
    ensure_schema(conn)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"chunks", "meta"} <= tables
    conn.close()


def test_chunk_markdown_splits_by_headings():
    chunks = chunk_markdown("# Title\nbody1\n## Sub\nbody2\n")
    assert len(chunks) == 2
    assert "Title" in chunks[0] and "body1" in chunks[0]
    assert "Sub" in chunks[1]


def test_chunk_markdown_no_headings_returns_one():
    assert len(chunk_markdown("just text\nmore\n")) == 1


def test_upsert_replaces_and_remove_clears(tmp_path):
    conn = open_index(tmp_path / "index.db", require_vector=True)
    ensure_schema(conn)
    upsert_concept(conn, "c1", "c1.md", "T", "Concept", "# A\nx", "[]", "", _E)
    upsert_concept(conn, "c1", "c1.md", "T", "Concept", "# A\nx\n# B\ny", "[]", "", _E)
    assert conn.execute("SELECT COUNT(*) FROM chunks WHERE concept_id='c1'").fetchone()[0] == 2
    remove_concept(conn, "c1")
    assert conn.execute("SELECT COUNT(*) FROM chunks WHERE concept_id='c1'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 0
    conn.close()


def test_search_returns_ranked_chunks_and_filters_type(tmp_path):
    conn = open_index(tmp_path / "index.db", require_vector=True)
    ensure_schema(conn)
    exact = "Attention is all you need."
    upsert_concept(conn, "c1", "c1.md", "One", "Concept", exact, "[]", "", _E)
    upsert_concept(conn, "c2", "c2.md", "Two", "Reference", "Other text", "[]", "", _E)
    assert search(conn, exact, 1, _E)[0]["concept_id"] == "c1"
    assert search(conn, exact, 2, _E, concept_type="Reference")[0]["concept_id"] == "c2"
    conn.close()


@pytest.mark.parametrize("query,k", [("", 1), ("x", 0), ("x", 101)])
def test_search_validates_query_and_limit(tmp_path, query, k):
    conn = open_index(tmp_path / "index.db")
    ensure_schema(conn)
    with pytest.raises(ValueError):
        search(conn, query, k, _E)
    conn.close()


def test_index_policy_excludes_archive(tmp_path):
    write_concept(tmp_path, "concepts/current.md", "Current", "current")
    write_concept(tmp_path, "archive/old.md", "Old", "old")
    assert list(iter_indexable_concepts(tmp_path)) == ["concepts/current"]


def test_reindex_is_snapshot_and_records_metadata(tmp_path):
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    (bundle / "index.md").write_text('---\nokf_version: "0.1"\n---\n# Concepts\n')
    current = write_concept(bundle, "concepts/current.md", "Current", "current")
    write_concept(bundle, "archive/old.md", "Old", "old")
    malformed = bundle / "concepts" / "bad.md"
    malformed.write_text("no frontmatter")
    db = tmp_path / "index.db"

    result = reindex_bundle(bundle, _E, db_path=db)
    assert (result.indexed_concepts, result.skipped_concepts) == (1, 1)
    conn = open_index(db, require_vector=True)
    assert {row[0] for row in conn.execute("SELECT DISTINCT concept_id FROM chunks")} == {
        "concepts/current"
    }
    meta = read_index_meta(conn)
    assert meta["schema_version"] == "1"
    assert meta["embedding_model"] == "test-8d"
    assert meta["okf_version"] == "0.1"
    assert meta["indexed_concepts"] == "1"
    assert meta["last_sync"]
    conn.close()

    current.rename(bundle / "concepts" / "moved.md")
    reindex_bundle(bundle, _E, db_path=db)
    conn = open_index(db, require_vector=True)
    assert {row[0] for row in conn.execute("SELECT DISTINCT concept_id FROM chunks")} == {
        "concepts/moved"
    }
    conn.close()


def test_failed_reindex_preserves_previous_index(tmp_path):
    bundle = tmp_path / "wiki"
    write_concept(bundle, "concepts/good.md", "Good", "stable content")
    db = tmp_path / "index.db"
    reindex_bundle(bundle, _E, db_path=db)

    def fail(_texts):
        raise RuntimeError("embedding failed")

    with pytest.raises(RuntimeError, match="embedding failed"):
        reindex_bundle(bundle, Embedder(fail, "broken"), db_path=db)
    conn = open_index(db, require_vector=True)
    assert search(conn, "stable content", 1, _E)[0]["concept_id"] == "concepts/good"
    conn.close()


def test_search_bundle_missing_index_does_not_create_database(tmp_path):
    with pytest.raises(IndexNotFoundError):
        search_bundle(tmp_path, "anything", embed_fn=_E)
    assert not (tmp_path / ".mneme" / "index.db").exists()


def test_search_bundle_closes_and_returns_hits(tmp_path):
    bundle = tmp_path / "wiki"
    write_concept(bundle, "concepts/a.md", "A", "needle")
    reindex_bundle(bundle, _E)
    hits = search_bundle(bundle, "needle", k=1, embed_fn=_E)
    assert hits[0]["path"] == "concepts/a.md"


def test_search_bundle_empty_index_returns_no_hits_without_embedding(tmp_path, monkeypatch):
    reindex_bundle(tmp_path, _E)

    def fail():
        raise AssertionError("empty indexes must not construct an embedder")

    monkeypatch.setattr("indexlib.default_embed_fn", fail)
    assert search_bundle(tmp_path, "anything") == []


def test_corrupt_index_reports_actionable_error(tmp_path):
    db = tmp_path / "index.db"
    conn = open_index(db)
    ensure_schema(conn)
    with pytest.raises(CorruptIndexError, match="metadata"):
        search(conn, "x", 1, _E)
    conn.close()
